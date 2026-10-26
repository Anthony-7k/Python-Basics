from dataclasses import replace

import pytest

from app.database import AuditLog, Job, Membership, Report, Tenant, User
from app.security.passwords import hash_password
from app.services import Conflict, JobService
from tests.test_api_flow import create_case, upload_pdf
from tests.test_approval_reports import _approve, _resolve_all_risks, _review_ready_case


def other_auth(client, database, roles="submitter"):
    with database.session_factory() as session:
        tenant = Tenant(name="Other tenant")
        user = User(email="other-operations@local.test", display_name="Other",
                    password_hash=hash_password("Other123!"))
        session.add_all([tenant, user])
        session.flush()
        session.add(Membership(tenant_id=tenant.id, user_id=user.id, roles=roles))
        session.commit()
    result = client.post("/api/v1/auth/login", json={
        "email": "other-operations@local.test", "password": "Other123!"})
    return {"Authorization": f"Bearer {result.json()['access_token']}"}


def test_search_audit_pagination_and_blank_title(client, auth, database):
    case = create_case(client, auth, "Literal 100%_contract")
    create_case(client, auth, "Other contract")
    assert len(client.get("/api/v1/cases?q=100%25_", headers=auth).json()) == 1
    assert client.get("/api/v1/cases?status=APPROVED", headers=auth).json() == []
    assert client.get("/api/v1/cases?status=INVALID", headers=auth).status_code == 422
    assert client.post("/api/v1/cases", headers=auth, json={"title": "   "}).status_code == 400
    first = client.get("/api/v1/audit-logs?action=case.create&limit=1", headers=auth).json()
    second = client.get("/api/v1/audit-logs?action=case.create&limit=1&offset=1", headers=auth).json()
    assert first["total"] == 2
    assert first["items"][0]["id"] != second["items"][0]["id"]
    assert case["id"] in {first["items"][0]["resource_id"], second["items"][0]["resource_id"]}
    assert client.get("/api/v1/audit-logs?limit=101", headers=auth).status_code == 422
    foreign = other_auth(client, database)
    assert client.get("/api/v1/audit-logs", headers=foreign).status_code == 403


def test_workbench_snapshot_is_paginated_filtered_and_tenant_scoped(client, auth, database, pdf_bytes):
    first = create_case(client, auth, "Alpha purchase")
    create_case(client, auth, "Beta purchase")
    upload_pdf(client, auth, first["id"], pdf_bytes)
    client.post(f"/api/v1/cases/{first['id']}/submit",
        headers={**auth, "Idempotency-Key": "snapshot"})
    page = client.get("/api/v1/workbench?limit=1", headers=auth).json()
    assert page["total"] == 2
    assert len(page["items"]) == 1
    next_page = client.get("/api/v1/workbench?limit=1&offset=1", headers=auth).json()
    assert next_page["items"][0]["id"] != page["items"][0]["id"]
    filtered = client.get("/api/v1/workbench?q=Alpha&status=REVIEW_READY", headers=auth).json()
    assert filtered["total"] == 1
    assert filtered["jobs"][first["id"]]["status"] == "SUCCEEDED"
    assert filtered["reports"] == {}
    assert client.get("/api/v1/workbench?offset=-1", headers=auth).status_code == 422
    foreign = other_auth(client, database)
    isolated = client.get("/api/v1/workbench", headers=foreign).json()
    assert isolated["items"] == []
    assert isolated["jobs"] == {}
    assert isolated["total"] == 0


def test_history_and_stream_are_tenant_scoped(client, auth, database, pdf_bytes):
    case = create_case(client, auth)
    upload_pdf(client, auth, case["id"], pdf_bytes)
    submitted = client.post(f"/api/v1/cases/{case['id']}/submit",
        headers={**auth, "Idempotency-Key": "history"}).json()
    job_id = submitted["id"]
    history = client.get(f"/api/v1/cases/{case['id']}/jobs", headers=auth).json()
    assert history[0]["id"] == job_id
    events = client.get(f"/api/v1/jobs/{job_id}/history", headers=auth).json()
    assert [event["sequence"] for event in events] == sorted(event["sequence"] for event in events)
    assert events[-1]["event_type"] == "job.completed"
    foreign = other_auth(client, database, "tenant_admin")
    for path in [f"/cases/{case['id']}/jobs", f"/cases/{case['id']}/reports",
                 f"/jobs/{job_id}/history", f"/jobs/{job_id}/events"]:
        assert client.get(f"/api/v1{path}", headers=foreign).status_code == 404
    assert client.get("/api/v1/audit-logs", headers=foreign).json()["items"] == []


def test_failed_report_can_recover_and_history_survives(client, auth, app, database, tmp_path):
    case_id = _review_ready_case(client, auth)
    _resolve_all_risks(client, auth, case_id)
    _approve(client, auth, case_id)
    version = client.get(f"/api/v1/cases/{case_id}", headers=auth).json()["version"]
    providers = app.state.providers

    class BrokenRenderer:
        def render(self, content):
            raise RuntimeError("renderer temporarily unavailable")

    app.state.providers = replace(providers, report_renderer=BrokenRenderer())
    requested = client.post(f"/api/v1/cases/{case_id}/reports",
        headers={**auth, "Idempotency-Key": "recovery"}, json={"expected_version": version})
    report_id = requested.json()["id"]
    failed = client.get(f"/api/v1/reports/{report_id}", headers=auth).json()
    assert failed["status"] == "FAILED"
    assert "temporarily unavailable" in failed["error_message"]
    assert client.get(f"/api/v1/reports/{report_id}/download", headers=auth).status_code == 409
    app.state.providers = providers
    assert client.post(f"/api/v1/reports/{report_id}/retry", headers=auth).status_code == 202
    history = client.get(f"/api/v1/cases/{case_id}/reports", headers=auth).json()
    assert len(history) == 1
    assert history[0]["status"] == "READY"
    snapshot = client.get("/api/v1/workbench", headers=auth).json()
    assert snapshot["reports"][case_id]["id"] == report_id
    assert client.post(f"/api/v1/reports/{report_id}/retry", headers=auth).status_code == 409
    assert client.post(f"/api/v1/cases/{case_id}/review", headers=auth).status_code == 409
    with database.session_factory() as session:
        report = session.get(Report, report_id)
        corrupted = tmp_path / "corrupted.pdf"
        corrupted.write_bytes(b"corrupted")
        providers.storage.put(corrupted, report.object_key)
    assert client.get(f"/api/v1/reports/{report_id}/download", headers=auth).status_code == 409


def test_failed_document_reprocessing_preserves_old_attempt(client, auth, app, database, pdf_bytes):
    case = create_case(client, auth)
    upload_pdf(client, auth, case["id"], pdf_bytes)
    providers = app.state.providers

    class BrokenStorage:
        def get_to(self, key, path):
            raise RuntimeError("storage temporarily unavailable")

    app.state.providers = replace(providers, storage=BrokenStorage())
    first = client.post(f"/api/v1/cases/{case['id']}/submit",
        headers={**auth, "Idempotency-Key": "failed-first"}).json()
    assert client.get(f"/api/v1/jobs/{first['id']}", headers=auth).json()["status"] == "FAILED"
    events = client.get(f"/api/v1/jobs/{first['id']}/history", headers=auth).json()
    assert events[-1]["payload"]["stage"] == "parsing"
    app.state.providers = providers
    second = client.post(f"/api/v1/cases/{case['id']}/submit",
        headers={**auth, "Idempotency-Key": "recovered-second"}).json()
    jobs = client.get(f"/api/v1/cases/{case['id']}/jobs", headers=auth).json()
    assert len(jobs) == 2
    assert jobs[0]["id"] == second["id"]
    assert jobs[0]["status"] == "SUCCEEDED"
    with database.session_factory() as session:
        assert session.query(Job).count() == 2
        assert session.query(AuditLog).filter_by(action="case.submit").count() == 2
        previous = session.get(Job, first["id"])
        with pytest.raises(Conflict):
            JobService(session, previous.tenant_id, "worker", providers).run_fake(previous.id)
    assert client.get(f"/api/v1/cases/{case['id']}", headers=auth).json()["status"] == "REVIEW_READY"
