from fastapi.testclient import TestClient


def create_case(client: TestClient, auth: dict[str, str], title: str = "采购审查") -> dict:
    response = client.post("/api/v1/cases", headers=auth, json={"title": title, "description": "测试案件"})
    assert response.status_code == 201
    return response.json()


def upload_pdf(client: TestClient, auth: dict[str, str], case_id: str, pdf_bytes: bytes, name: str = "contract.pdf") -> dict:
    response = client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=auth,
        files={"file": (name, pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_end_to_end_local_flow(client: TestClient, auth, pdf_bytes):
    case = create_case(client, auth)
    document = upload_pdf(client, auth, case["id"], pdf_bytes)
    assert document["scan_status"] == "CLEAN"
    assert document["sha256"]

    submitted = client.post(
        f"/api/v1/cases/{case['id']}/submit",
        headers={**auth, "Idempotency-Key": "e2e-case-1"},
    )
    assert submitted.status_code == 202, submitted.text
    job_id = submitted.json()["id"]

    job = client.get(f"/api/v1/jobs/{job_id}", headers=auth)
    assert job.status_code == 200
    assert job.json()["status"] == "SUCCEEDED"
    assert job.json()["progress"] == 100

    detail = client.get(f"/api/v1/cases/{case['id']}", headers=auth)
    assert detail.json()["status"] == "REVIEW_READY"

    events = client.get(f"/api/v1/jobs/{job_id}/events", headers=auth)
    assert events.status_code == 200
    assert "event: job.queued" in events.text
    assert "event: job.completed" in events.text
    assert '"schema_version": "1.0"' in events.text


def test_idempotent_submit_replays_same_job(client: TestClient, auth, pdf_bytes):
    case = create_case(client, auth)
    upload_pdf(client, auth, case["id"], pdf_bytes)
    headers = {**auth, "Idempotency-Key": "same-key"}
    first = client.post(f"/api/v1/cases/{case['id']}/submit", headers=headers)
    second = client.post(f"/api/v1/cases/{case['id']}/submit", headers=headers)
    assert first.status_code == second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["replayed"] is True


def test_idempotency_key_payload_conflict(client: TestClient, auth, pdf_bytes):
    first_case = create_case(client, auth, "一号")
    second_case = create_case(client, auth, "二号")
    upload_pdf(client, auth, first_case["id"], pdf_bytes, "one.pdf")
    upload_pdf(client, auth, second_case["id"], pdf_bytes, "two.pdf")
    headers = {**auth, "Idempotency-Key": "collision"}
    assert client.post(f"/api/v1/cases/{first_case['id']}/submit", headers=headers).status_code == 202
    response = client.post(f"/api/v1/cases/{second_case['id']}/submit", headers=headers)
    assert response.status_code == 409


def test_upload_rejects_forged_and_duplicate_files(client: TestClient, auth, pdf_bytes):
    case = create_case(client, auth)
    forged = client.post(
        f"/api/v1/cases/{case['id']}/documents",
        headers=auth,
        files={"file": ("fake.pdf", b"not a pdf", "application/pdf")},
    )
    assert forged.status_code == 400
    upload_pdf(client, auth, case["id"], pdf_bytes)
    duplicate = client.post(
        f"/api/v1/cases/{case['id']}/documents",
        headers=auth,
        files={"file": ("again.pdf", pdf_bytes, "application/pdf")},
    )
    assert duplicate.status_code == 409


def test_upload_rejects_infected_signature(client: TestClient, auth):
    case = create_case(client, auth)
    infected = b"%PDF-1.4 EICAR test signature\n%%EOF"
    response = client.post(
        f"/api/v1/cases/{case['id']}/documents",
        headers=auth,
        files={"file": ("infected.pdf", infected, "application/pdf")},
    )
    assert response.status_code == 400
    assert "virus scanner" in response.json()["message"]


def test_requires_document_before_submit(client: TestClient, auth):
    case = create_case(client, auth)
    response = client.post(
        f"/api/v1/cases/{case['id']}/submit",
        headers={**auth, "Idempotency-Key": "empty"},
    )
    assert response.status_code == 400


def test_document_can_only_be_deleted_from_draft(client: TestClient, auth, pdf_bytes):
    case = create_case(client, auth)
    document = upload_pdf(client, auth, case["id"], pdf_bytes)
    response = client.delete(f"/api/v1/documents/{document['id']}", headers=auth)
    assert response.status_code == 204
    assert client.get(f"/api/v1/cases/{case['id']}", headers=auth).json()["documents"] == []


def test_document_cannot_be_deleted_after_submission(client: TestClient, auth, pdf_bytes):
    case = create_case(client, auth)
    document = upload_pdf(client, auth, case["id"], pdf_bytes)
    client.post(
        f"/api/v1/cases/{case['id']}/submit",
        headers={**auth, "Idempotency-Key": "locked-document"},
    )
    response = client.delete(f"/api/v1/documents/{document['id']}", headers=auth)
    assert response.status_code == 409


def test_health_and_metrics(client: TestClient):
    assert client.get("/health/live").json() == {"status": "alive"}
    assert client.get("/health/ready").status_code == 200
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "docflow_http_requests_total" in metrics.text


def test_database_flush_failure_records_failed_job(client, auth, pdf_bytes, monkeypatch):
    from app.database import ExtractionRun
    from app.document_ai import DocumentIntelligenceService

    def fail_flush(service, document):
        service.session.add(ExtractionRun(tenant_id=document.tenant_id, document_id=None))
        service.session.flush()

    monkeypatch.setattr(DocumentIntelligenceService, "process", fail_flush)
    case = create_case(client, auth)
    upload_pdf(client, auth, case["id"], pdf_bytes)
    submitted = client.post(f"/api/v1/cases/{case['id']}/submit",
                            headers={**auth, "Idempotency-Key": "flush-failure"})
    assert submitted.status_code == 202
    job_id = submitted.json()["id"]
    job = client.get(f"/api/v1/jobs/{job_id}", headers=auth).json()
    assert job["status"] == "FAILED"
    assert job["error_code"] == "IntegrityError"
    assert job["trace_id"]
    assert client.get(f"/api/v1/cases/{case['id']}", headers=auth).json()["status"] == "FAILED"
    events = client.get(f"/api/v1/jobs/{job_id}/history", headers=auth).json()
    assert events[-1]["event_type"] == "job.failed"
    assert events[-1]["payload"]["stage"] == "parsing"


def test_readiness_rejects_outdated_schema(client, database):
    from sqlalchemy import text

    with database.engine.begin() as connection:
        connection.execute(text("ALTER TABLE field_values DROP COLUMN source"))
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["database"] == "schema_outdated"


def test_structured_logs_keep_exception_traceback():
    import json
    import logging
    import sys

    from app.logging_config import JsonFormatter

    try:
        raise RuntimeError("test worker failure")
    except RuntimeError:
        record = logging.LogRecord("worker", logging.ERROR, __file__, 1, "failed", (), sys.exc_info())
    payload = json.loads(JsonFormatter().format(record))
    assert "RuntimeError: test worker failure" in payload["exception"]

