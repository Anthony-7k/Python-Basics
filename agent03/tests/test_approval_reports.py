import hashlib
from io import BytesIO

import pymupdf
from docx import Document as WordDocument
from fastapi.testclient import TestClient

from app.database import AuditLog, Membership, Tenant, User
from app.security.passwords import hash_password


def _docx(lines: list[str]) -> bytes:
    document = WordDocument()
    for line in lines:
        document.add_paragraph(line)
    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


def _review_ready_case(client: TestClient, auth: dict[str, str], title: str = "审批案件") -> str:
    created = client.post(
        "/api/v1/cases",
        headers=auth,
        json={"title": title, "description": "报告生成验收"},
    )
    case_id = created.json()["id"]
    uploaded = client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=auth,
        files={
            "file": (
                "contract.docx",
                _docx(["采购合同", "乙方：示例供应商有限公司", "合同总额：10000.00"]),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert uploaded.status_code == 201
    submitted = client.post(
        f"/api/v1/cases/{case_id}/submit",
        headers={**auth, "Idempotency-Key": f"submit-{case_id}"},
    )
    assert submitted.status_code == 202
    return case_id


def _resolve_all_risks(client: TestClient, auth: dict[str, str], case_id: str):
    risks = client.get(f"/api/v1/cases/{case_id}/risks", headers=auth).json()
    for risk in risks:
        response = client.post(
            f"/api/v1/risks/{risk['id']}/resolve",
            headers=auth,
            json={
                "expected_version": risk["version"],
                "disposition": "ACCEPTED",
                "reason": "审批前已由业务负责人确认接受",
            },
        )
        assert response.status_code == 200


def _approve(client: TestClient, auth: dict[str, str], case_id: str):
    case = client.get(f"/api/v1/cases/{case_id}", headers=auth).json()
    response = client.post(
        f"/api/v1/cases/{case_id}/approvals",
        headers=auth,
        json={
            "expected_version": case["version"],
            "decision": "APPROVED",
            "reason": "风险均已核对，批准生成报告",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_open_high_risk_blocks_approval(client, auth):
    case_id = _review_ready_case(client, auth)
    case = client.get(f"/api/v1/cases/{case_id}", headers=auth).json()
    blocked = client.post(
        f"/api/v1/cases/{case_id}/approvals",
        headers=auth,
        json={
            "expected_version": case["version"],
            "decision": "APPROVED",
            "reason": "不应绕过高风险",
        },
    )
    assert blocked.status_code == 409
    assert "high risks" in blocked.json()["message"]
    assert client.get(f"/api/v1/cases/{case_id}", headers=auth).json()["status"] == "REVIEW_READY"


def test_approval_and_immutable_report_download(client, auth, database):
    case_id = _review_ready_case(client, auth, "报告 <script>alert(1)</script>")
    before = client.get(f"/api/v1/cases/{case_id}", headers=auth).json()
    premature = client.post(
        f"/api/v1/cases/{case_id}/reports",
        headers={**auth, "Idempotency-Key": "premature-report"},
        json={"expected_version": before["version"]},
    )
    assert premature.status_code == 409

    _resolve_all_risks(client, auth, case_id)
    approval = _approve(client, auth, case_id)
    approved_case = client.get(f"/api/v1/cases/{case_id}", headers=auth).json()
    assert approved_case["status"] == "APPROVED"
    assert approved_case["version"] == approval["case_version"] + 1

    stale = client.post(
        f"/api/v1/cases/{case_id}/approvals",
        headers=auth,
        json={
            "expected_version": approval["case_version"],
            "decision": "REJECTED",
            "reason": "陈旧审批版本",
        },
    )
    assert stale.status_code == 409

    headers = {**auth, "Idempotency-Key": "approved-report-v1"}
    requested = client.post(
        f"/api/v1/cases/{case_id}/reports",
        headers=headers,
        json={"expected_version": approved_case["version"]},
    )
    assert requested.status_code == 202, requested.text
    report_id = requested.json()["id"]
    report = client.get(f"/api/v1/reports/{report_id}", headers=auth)
    assert report.status_code == 200
    assert report.json()["status"] == "READY"
    assert report.json()["content_type"] == "application/pdf"
    assert len(report.json()["content_hash"]) == 64

    replayed = client.post(
        f"/api/v1/cases/{case_id}/reports",
        headers=headers,
        json={"expected_version": approved_case["version"]},
    )
    assert replayed.status_code == 202
    assert replayed.json()["id"] == report_id
    assert replayed.json()["replayed"] is True

    download = client.get(f"/api/v1/reports/{report_id}/download", headers=auth)
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/pdf"
    assert download.headers["content-disposition"].endswith(f'{report_id}.pdf"')
    assert hashlib.sha256(download.content).hexdigest() == report.json()["content_hash"]
    assert download.content.startswith(b"%PDF-")
    assert b"<script>alert(1)</script>" not in download.content
    with pymupdf.open(stream=download.content, filetype="pdf") as pdf:
        assert pdf.page_count >= 1
        assert "ACCEPTED" in "".join(page.get_text() for page in pdf)

    with database.session_factory() as session:
        actions = {
            item.action for item in session.query(AuditLog).filter_by(resource_id=report_id).all()
        }
        assert actions == {"report.request", "report.generate"}


def test_rejected_case_cannot_generate_report(client, auth):
    case_id = _review_ready_case(client, auth)
    case = client.get(f"/api/v1/cases/{case_id}", headers=auth).json()
    rejected = client.post(
        f"/api/v1/cases/{case_id}/approvals",
        headers=auth,
        json={
            "expected_version": case["version"],
            "decision": "REJECTED",
            "reason": "材料不完整，退回线下补充",
        },
    )
    assert rejected.status_code == 201
    detail = client.get(f"/api/v1/cases/{case_id}", headers=auth).json()
    assert detail["status"] == "REJECTED"
    report = client.post(
        f"/api/v1/cases/{case_id}/reports",
        headers={**auth, "Idempotency-Key": "rejected-report"},
        json={"expected_version": detail["version"]},
    )
    assert report.status_code == 409


def test_approval_rbac_and_report_tenant_isolation(client, auth, database):
    case_id = _review_ready_case(client, auth)
    _resolve_all_risks(client, auth, case_id)
    _approve(client, auth, case_id)
    case = client.get(f"/api/v1/cases/{case_id}", headers=auth).json()
    requested = client.post(
        f"/api/v1/cases/{case_id}/reports",
        headers={**auth, "Idempotency-Key": "tenant-isolated-report"},
        json={"expected_version": case["version"]},
    )
    report_id = requested.json()["id"]

    with database.session_factory() as session:
        own_tenant = session.query(Tenant).filter_by(name="DocFlow Demo").one()
        reviewer = User(
            email="approval-reviewer@example.com",
            display_name="Reviewer Only",
            password_hash=hash_password("Other123!"),
        )
        other_tenant = Tenant(name="Report Isolation Tenant")
        other_approver = User(
            email="report-other@example.com",
            display_name="Other Approver",
            password_hash=hash_password("Other123!"),
        )
        session.add_all([reviewer, other_tenant, other_approver])
        session.flush()
        session.add_all(
            [
                Membership(tenant_id=own_tenant.id, user_id=reviewer.id, roles="reviewer"),
                Membership(tenant_id=other_tenant.id, user_id=other_approver.id, roles="approver"),
            ]
        )
        session.commit()

    reviewer_login = client.post(
        "/api/v1/auth/login",
        json={"email": "approval-reviewer@example.com", "password": "Other123!"},
    )
    reviewer_auth = {"Authorization": f"Bearer {reviewer_login.json()['access_token']}"}
    assert (
        client.post(
            f"/api/v1/cases/{case_id}/approvals",
            headers=reviewer_auth,
            json={"expected_version": case["version"], "decision": "REJECTED", "reason": "no permission"},
        ).status_code
        == 403
    )

    other_login = client.post(
        "/api/v1/auth/login",
        json={"email": "report-other@example.com", "password": "Other123!"},
    )
    other_auth = {"Authorization": f"Bearer {other_login.json()['access_token']}"}
    assert client.get(f"/api/v1/reports/{report_id}", headers=other_auth).status_code == 404
    assert (
        client.get(f"/api/v1/reports/{report_id}/download", headers=other_auth).status_code
        == 404
    )
