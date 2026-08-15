from fastapi.testclient import TestClient

from app.main import app

from unittest.mock import patch

from app.services.ingestion.ingestion_service import run_ingestion_task
from app.services.ingestion.task_manager import create_task, get_task

client = TestClient(app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200

    assert response.json()["status"] == "ok"


def test_ready():
    response = client.get("/ready")

    assert response.status_code == 200

    assert response.json()["status"] == "ready"


def test_chat_validation_error():
    response = client.post(
        "/api/v1/chat",
        json={
            "question": ""
        },
    )

    assert response.status_code == 422


def test_chat_success():
    fake_response = {
        "answer": "测试答案",
        "sources": [],
        "used_chunk_ids": [],
        "request_id": "test-request-id",
    }

    with patch(
        "app.api.routes.chat.answer_question",
        return_value=fake_response,
    ):
        response = client.post(
            "/api/v1/chat",
            json={
                "question": "测试问题"
            },
        )

    assert response.status_code == 200

    data = response.json()

    assert data["answer"] == "测试答案"
    assert "request_id" in data

def test_upload_rejects_unsupported_extension():
    response = client.post(
        "/api/v1/documents",
        files={
            "file": (
                "malware.exe",
                b"not-a-valid-document",
                "application/octet-stream",
            )
        },
    )

    assert response.status_code == 400
    assert "Unsupported file extension" in response.json()["detail"]

def test_upload_rejects_oversized_file():
    with patch(
        "app.services.ingestion.uploader.MAX_UPLOAD_SIZE_BYTES",
        10,
    ):
        response = client.post(
            "/api/v1/documents",
            files={
                "file": (
                    "large.txt",
                    b"a" * 11,
                    "text/plain",
                )
            },
        )

    assert response.status_code == 400
    assert "File exceeds the maximum size" in response.json()["detail"]

def test_upload_document_and_get_status(tmp_path):
    with patch(
        "app.services.ingestion.uploader.UPLOAD_DIR",
        tmp_path,
    ), patch(
        "app.api.routes.documents.run_ingestion_task"
    ) as mocked_ingestion:
        upload_response = client.post(
            "/api/v1/documents",
            files={
                "file": (
                    "example.txt",
                    b"Day 9 upload test",
                    "text/plain",
                )
            },
        )

    assert upload_response.status_code == 202

    upload_data = upload_response.json()

    assert len(upload_data["document_id"]) == 64
    assert upload_data["task_id"]
    assert upload_data["status"] == "pending"
    mocked_ingestion.assert_called_once()

    status_response = client.get(
        f"/api/v1/ingestion/{upload_data['task_id']}"
    )

    assert status_response.status_code == 200

    status_data = status_response.json()

    assert status_data["task_id"] == upload_data["task_id"]
    assert status_data["document_id"] == upload_data["document_id"]
    assert status_data["status"] == "pending"
    assert status_data["error"] is None

def test_duplicate_upload_is_idempotent(tmp_path):
    file_content = b"Day 9 idempotency test"

    with patch(
        "app.services.ingestion.uploader.UPLOAD_DIR",
        tmp_path,
    ), patch(
        "app.api.routes.documents.run_ingestion_task"
    ) as mocked_ingestion:
        first_response = client.post(
            "/api/v1/documents",
            files={
                "file": (
                    "first.txt",
                    file_content,
                    "text/plain",
                )
            },
        )

        second_response = client.post(
            "/api/v1/documents",
            files={
                "file": (
                    "second.txt",
                    file_content,
                    "text/plain",
                )
            },
        )

    assert first_response.status_code == 202
    assert second_response.status_code == 202

    first_data = first_response.json()
    second_data = second_response.json()

    assert second_data["document_id"] == first_data["document_id"]
    assert second_data["task_id"] == first_data["task_id"]
    mocked_ingestion.assert_called_once()

def test_upload_rejects_mime_mismatch():
    response = client.post(
        "/api/v1/documents",
        files={
            "file": (
                "fake.pdf",
                b"not-a-real-pdf",
                "text/plain",
            )
        },
    )

    assert response.status_code == 400
    assert "Unsupported MIME type" in response.json()["detail"]

def test_ingestion_task_succeeds():
    task = create_task(
        "background-success-document"
    )

    with patch(
        "app.services.ingestion.ingestion_service.ingest_file"
    ) as mocked_ingest:
        run_ingestion_task(
            task.task_id,
            "fake-file.txt",
        )

    saved_task = get_task(task.task_id)

    assert saved_task is not None
    assert saved_task.status.value == "succeeded"
    assert saved_task.error is None

    mocked_ingest.assert_called_once_with(
        "fake-file.txt"
    )

def test_ingestion_task_fails():
    task = create_task(
        "background-failure-document"
    )

    with patch(
        "app.services.ingestion.ingestion_service.ingest_file",
        side_effect=RuntimeError("ingestion failed"),
    ):
        run_ingestion_task(
            task.task_id,
            "broken-file.txt",
        )

    saved_task = get_task(task.task_id)

    assert saved_task is not None
    assert saved_task.status.value == "failed"
    assert saved_task.error == "ingestion failed"