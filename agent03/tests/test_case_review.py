from io import BytesIO

from docx import Document as WordDocument
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import (
    AuditLog,
    Document,
    DocumentLink,
    FieldCorrection,
    Membership,
    ReviewCase,
    RiskFinding,
    RuleRun,
    Tenant,
    User,
)
from app.security.passwords import hash_password


def _docx(lines: list[str]) -> bytes:
    document = WordDocument()
    for line in lines:
        document.add_paragraph(line)
    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


def _create_case(client: TestClient, auth: dict[str, str]) -> str:
    response = client.post(
        "/api/v1/cases",
        headers=auth,
        json={"title": "三单审查", "description": "规则引擎验收"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _upload(client: TestClient, auth: dict[str, str], case_id: str, name: str, lines: list[str]):
    response = client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=auth,
        files={
            "file": (
                name,
                _docx(lines),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 201, response.text


def _three_documents(client, auth, case_id, *, seller="示例供应商有限公司", invoice="9000.00"):
    _upload(
        client,
        auth,
        case_id,
        "contract.docx",
        [
            "采购服务合同",
            "合同编号：HT-001",
            "甲方：示例采购有限公司",
            "乙方：示例供应商有限公司",
            "合同总额：10000.00",
            "生效日期：2026年9月1日",
        ],
    )
    _upload(
        client,
        auth,
        case_id,
        "purchase-order.docx",
        ["采购单", "订单号：PO-001", "供应商：示例供应商有限公司", "含税总额：9500.00"],
    )
    _upload(
        client,
        auth,
        case_id,
        "invoice.docx",
        ["增值税发票", "发票号码：FP-001", f"销售方：{seller}", f"价税合计：{invoice}", "开票日期：2026年9月20日"],
    )


def _submit(client, auth, case_id, key):
    response = client.post(
        f"/api/v1/cases/{case_id}/submit",
        headers={**auth, "Idempotency-Key": key},
    )
    assert response.status_code == 202, response.text
    assert client.get(f"/api/v1/jobs/{response.json()['id']}", headers=auth).json()["status"] == "SUCCEEDED"


def test_three_way_match_creates_links_and_no_risks(client, auth, database):
    case_id = _create_case(client, auth)
    _three_documents(client, auth, case_id)
    _submit(client, auth, case_id, "three-way-pass")

    comparison = client.get(f"/api/v1/cases/{case_id}/comparison", headers=auth)
    assert comparison.status_code == 200
    columns = {item["document_type"]: item for item in comparison.json()["columns"]}
    assert set(columns) == {"contract", "purchase_order", "invoice"}
    assert columns["contract"]["fields"]["total_amount"]["value"] == "10000.00"
    assert columns["invoice"]["fields"]["seller"]["evidence_id"]
    assert all(column["match_status"] == "MATCHED" for column in columns.values())
    assert all(len(column["candidates"]) == 1 for column in columns.values())
    assert client.get(f"/api/v1/cases/{case_id}/risks", headers=auth).json() == []

    with database.session_factory() as session:
        assert len(session.scalars(select(DocumentLink).where(DocumentLink.case_id == case_id)).all()) == 2
        outcomes = session.scalars(select(RuleRun.outcome).where(RuleRun.case_id == case_id)).all()
        assert outcomes == ["PASS", "PASS", "PASS", "PASS"]


def test_review_reports_supplier_and_amount_risks(client, auth):
    case_id = _create_case(client, auth)
    _three_documents(client, auth, case_id, seller="异常销售方有限公司", invoice="9900.00")
    _submit(client, auth, case_id, "three-way-risk")

    response = client.get(f"/api/v1/cases/{case_id}/risks", headers=auth)
    assert response.status_code == 200
    risks = {risk["risk_type"]: risk for risk in response.json()}
    assert set(risks) == {"SUPPLIER_MATCH", "AMOUNT_HIERARCHY"}
    assert risks["SUPPLIER_MATCH"]["severity"] == "HIGH"
    assert risks["AMOUNT_HIERARCHY"]["evidence_ids"]


def test_multiple_invoices_require_manual_matching(client, auth, database):
    case_id = _create_case(client, auth)
    _three_documents(client, auth, case_id)
    _upload(client, auth, case_id, "second-invoice.docx", [
        "增值税发票", "发票号码：FP-002", "销售方：示例供应商有限公司",
        "价税合计：9000.00", "开票日期：2026年9月20日",
    ])
    _submit(client, auth, case_id, "ambiguous-invoices")
    risks = client.get(f"/api/v1/cases/{case_id}/risks", headers=auth).json()
    assert [risk["risk_type"] for risk in risks] == ["AMBIGUOUS_DOCUMENT_SET"]
    assert risks[0]["severity"] == "HIGH"
    comparison = client.get(f"/api/v1/cases/{case_id}/comparison", headers=auth).json()
    invoice = next(column for column in comparison["columns"] if column["document_type"] == "invoice")
    assert invoice["document_id"] is None
    assert invoice["match_status"] == "AMBIGUOUS"
    assert len(invoice["candidates"]) == 2
    assert {item["original_name"] for item in invoice["candidates"]} == {
        "invoice.docx", "second-invoice.docx",
    }
    assert invoice["fields"] == {}
    with database.session_factory() as session:
        assert session.query(DocumentLink).filter_by(case_id=case_id).count() == 0
    case = client.get(f"/api/v1/cases/{case_id}", headers=auth).json()
    approval = client.post(f"/api/v1/cases/{case_id}/approvals", headers=auth, json={
        "expected_version": case["version"], "decision": "APPROVED", "reason": "验证歧义阻断",
    })
    assert approval.status_code == 409


def test_missing_documents_and_manual_rerun_are_append_only(client, auth, database):
    case_id = _create_case(client, auth)
    _upload(client, auth, case_id, "contract.docx", ["合同", "乙方：示例供应商有限公司"])
    _submit(client, auth, case_id, "missing-documents")

    risks = client.get(f"/api/v1/cases/{case_id}/risks", headers=auth).json()
    assert [risk["risk_type"] for risk in risks] == ["REQUIRED_DOCUMENTS"]
    comparison = client.get(f"/api/v1/cases/{case_id}/comparison", headers=auth).json()
    invoice = next(column for column in comparison["columns"] if column["document_type"] == "invoice")
    assert invoice["match_status"] == "MISSING"
    assert invoice["candidates"] == []
    rerun = client.post(f"/api/v1/cases/{case_id}/review", headers=auth)
    assert rerun.status_code == 200
    assert rerun.json()["rules"] == 1
    assert rerun.json()["risks"] == 1

    with database.session_factory() as session:
        groups = session.scalars(
            select(RuleRun.run_group_id).where(RuleRun.case_id == case_id).distinct()
        ).all()
        assert len(groups) == 2
        assert session.query(RiskFinding).filter_by(case_id=case_id).count() == 2


def test_review_resources_are_hidden_from_other_tenants(client, auth, database):
    case_id = _create_case(client, auth)
    _upload(client, auth, case_id, "contract.docx", ["合同", "乙方：示例供应商有限公司"])
    _submit(client, auth, case_id, "tenant-review-isolation")
    case = client.get(f"/api/v1/cases/{case_id}", headers=auth).json()
    extraction = client.get(
        f"/api/v1/documents/{case['documents'][0]['id']}/extraction", headers=auth
    ).json()
    field_id = extraction["fields"][0]["id"]
    risk_id = client.get(f"/api/v1/cases/{case_id}/risks", headers=auth).json()[0]["id"]

    with database.session_factory() as session:
        tenant = Tenant(name="Review Isolation Tenant")
        user = User(
            email="review-isolation@example.com",
            display_name="Other Reviewer",
            password_hash=hash_password("Other123!"),
        )
        session.add_all([tenant, user])
        session.flush()
        session.add(Membership(tenant_id=tenant.id, user_id=user.id, roles="reviewer"))
        session.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "review-isolation@example.com", "password": "Other123!"},
    )
    other_auth = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.get(f"/api/v1/cases/{case_id}/risks", headers=other_auth).status_code == 404
    assert client.get(f"/api/v1/cases/{case_id}/comparison", headers=other_auth).status_code == 404
    assert client.post(f"/api/v1/cases/{case_id}/review", headers=other_auth).status_code == 404
    assert (
        client.patch(
            f"/api/v1/fields/{field_id}",
            headers=other_auth,
            json={"expected_version": 1, "normalized_value": "x", "reason": "not allowed"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/risks/{risk_id}/resolve",
            headers=other_auth,
            json={"expected_version": 1, "disposition": "RESOLVED", "reason": "not allowed"},
        ).status_code
        == 404
    )


def test_human_field_correction_recalculates_rules_and_audits(client, auth, database):
    case_id = _create_case(client, auth)
    _three_documents(client, auth, case_id, seller="异常销售方有限公司")
    _submit(client, auth, case_id, "field-correction")
    case = client.get(f"/api/v1/cases/{case_id}", headers=auth).json()
    invoice = next(item for item in case["documents"] if item["classification"] == "invoice")
    extraction = client.get(
        f"/api/v1/documents/{invoice['id']}/extraction", headers=auth
    ).json()
    seller = next(field for field in extraction["fields"] if field["field_name"] == "seller")

    response = client.patch(
        f"/api/v1/fields/{seller['id']}",
        headers=auth,
        json={
            "expected_version": 1,
            "normalized_value": "示例供应商有限公司",
            "reason": "人工核对发票原件后修正",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["version"] == 2
    assert response.json()["source"] == "HUMAN"
    assert client.get(f"/api/v1/cases/{case_id}/risks", headers=auth).json() == []

    stale = client.patch(
        f"/api/v1/fields/{seller['id']}",
        headers=auth,
        json={
            "expected_version": 1,
            "normalized_value": "另一个值",
            "reason": "验证并发冲突",
        },
    )
    assert stale.status_code == 409
    with database.session_factory() as session:
        correction = session.query(FieldCorrection).filter_by(field_value_id=seller["id"]).one()
        assert correction.previous_value == "异常销售方有限公司"
        assert correction.corrected_value == "示例供应商有限公司"
        audit = session.query(AuditLog).filter_by(action="field.correct").one()
        assert audit.before["version"] == 1
        assert audit.after["version"] == 2


def test_corrected_latest_review_can_approve_and_generate_report(client, auth, database):
    case_id = _create_case(client, auth)
    _three_documents(client, auth, case_id, seller="异常销售方有限公司")
    _submit(client, auth, case_id, "correct-then-approve")
    old_risk = client.get(f"/api/v1/cases/{case_id}/risks", headers=auth).json()[0]
    case = client.get(f"/api/v1/cases/{case_id}", headers=auth).json()
    invoice = next(doc for doc in case["documents"] if doc["classification"] == "invoice")
    fields = client.get(f"/api/v1/documents/{invoice['id']}/extraction", headers=auth).json()["fields"]
    seller = next(field for field in fields if field["field_name"] == "seller")
    corrected = client.patch(f"/api/v1/fields/{seller['id']}", headers=auth, json={
        "expected_version": seller["version"], "normalized_value": "示例供应商有限公司",
        "reason": "核对原文后修正演示字段",
    })
    assert corrected.status_code == 200
    assert client.get(f"/api/v1/cases/{case_id}/risks", headers=auth).json() == []
    with database.session_factory() as session:
        assert session.get(RiskFinding, old_risk["id"]).status == "OPEN"
    stale = client.post(f"/api/v1/risks/{old_risk['id']}/resolve", headers=auth, json={
        "expected_version": old_risk["version"], "disposition": "ACCEPTED", "reason": "历史风险不可再处置",
    })
    assert stale.status_code == 409
    case = client.get(f"/api/v1/cases/{case_id}", headers=auth).json()
    approved = client.post(f"/api/v1/cases/{case_id}/approvals", headers=auth, json={
        "expected_version": case["version"], "decision": "APPROVED", "reason": "当前审查无风险",
    })
    assert approved.status_code == 201, approved.text
    case = client.get(f"/api/v1/cases/{case_id}", headers=auth).json()
    report = client.post(f"/api/v1/cases/{case_id}/reports", headers={**auth, "Idempotency-Key": "corrected-report"},
                         json={"expected_version": case["version"]})
    assert report.status_code == 202
    report_id = report.json()["id"]
    assert client.get(f"/api/v1/reports/{report_id}", headers=auth).json()["status"] == "READY"
    assert client.get(f"/api/v1/reports/{report_id}/download", headers=auth).status_code == 200


def test_rerun_resolved_risk_is_open_again_and_blocks_approval(client, auth):
    case_id = _create_case(client, auth)
    _three_documents(client, auth, case_id, seller="异常销售方有限公司")
    _submit(client, auth, case_id, "rerun-still-risky")
    risk = client.get(f"/api/v1/cases/{case_id}/risks", headers=auth).json()[0]
    assert client.post(f"/api/v1/risks/{risk['id']}/resolve", headers=auth, json={
        "expected_version": risk["version"], "disposition": "ACCEPTED", "reason": "仅接受本轮风险",
    }).status_code == 200
    assert client.post(f"/api/v1/cases/{case_id}/review", headers=auth).status_code == 200
    case = client.get(f"/api/v1/cases/{case_id}", headers=auth).json()
    assert client.post(f"/api/v1/cases/{case_id}/approvals", headers=auth, json={
        "expected_version": case["version"], "decision": "APPROVED", "reason": "不能复用旧处置",
    }).status_code == 409


def test_approval_fails_closed_without_review_results(client, auth, database):
    case_id = _create_case(client, auth)
    # Simulate inconsistent legacy state: ready status without a review must not mean safe.
    with database.session_factory() as session:
        session.get(ReviewCase, case_id).status = "REVIEW_READY"
        session.commit()
    case = client.get(f"/api/v1/cases/{case_id}", headers=auth).json()
    response = client.post(f"/api/v1/cases/{case_id}/approvals", headers=auth, json={
        "expected_version": case["version"], "decision": "APPROVED", "reason": "无审查结果不能放行",
    })
    assert response.status_code == 409
    assert "no completed review" in response.json()["message"]


def test_uploaded_document_without_extraction_is_unavailable_not_missing(client, auth, database):
    case_id = _create_case(client, auth)
    _upload(client, auth, case_id, "contract.docx", ["采购合同", "合同编号：HT-123"])
    with database.session_factory() as session:
        document = session.query(Document).filter_by(case_id=case_id).one()
        document.classification = "contract"
        session.commit()
    columns = client.get(f"/api/v1/cases/{case_id}/comparison", headers=auth).json()["columns"]
    contract = next(column for column in columns if column["document_type"] == "contract")
    assert contract["match_status"] == "UNAVAILABLE"
    assert len(contract["candidates"]) == 1
    assert contract["fields"] == {}


def test_risk_resolution_requires_current_version_and_reason(client, auth, database):
    case_id = _create_case(client, auth)
    _upload(client, auth, case_id, "contract.docx", ["合同", "乙方：示例供应商有限公司"])
    _submit(client, auth, case_id, "risk-resolution")
    risk = client.get(f"/api/v1/cases/{case_id}/risks", headers=auth).json()[0]

    response = client.post(
        f"/api/v1/risks/{risk['id']}/resolve",
        headers=auth,
        json={
            "expected_version": risk["version"],
            "disposition": "ACCEPTED",
            "reason": "业务确认本案允许缺少采购单与发票",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ACCEPTED"
    assert response.json()["version"] == 2
    assert response.json()["resolved_by"]
    assert response.json()["resolved_at"]

    replay = client.post(
        f"/api/v1/risks/{risk['id']}/resolve",
        headers=auth,
        json={
            "expected_version": risk["version"],
            "disposition": "RESOLVED",
            "reason": "重复处置应被拒绝",
        },
    )
    assert replay.status_code == 409
    with database.session_factory() as session:
        audit = session.query(AuditLog).filter_by(action="risk.resolve").one()
        assert audit.after["status"] == "ACCEPTED"
