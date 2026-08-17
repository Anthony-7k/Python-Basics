from types import SimpleNamespace
from unittest.mock import (
    MagicMock,
    call,
    patch,
)

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_conversation_service,
    get_document_service,
)
from app.core.exceptions import (
    ConversationNotFoundError,
    UpstreamServiceError,
    UpstreamTimeoutError,
)
from app.main import app
from app.models import (
    DocumentStatus,
    IngestionJobStatus,
)
from app.services.ingestion.ingestion_service import (
    run_ingestion_task,
)


client = TestClient(app)

class FakeConversationService:
    def __init__(self):
        self.saved_exchanges = []
        self.messages = []

    def get_or_create_conversation(
        self,
        conversation_id=None,
        knowledge_base_id=None,
    ):
        return SimpleNamespace(
            id=(
                conversation_id
                or "test-conversation-id"
            )
        )

    def save_exchange(
        self,
        **exchange,
    ):
        self.saved_exchanges.append(
            exchange
        )

    def get_messages(
        self,
        conversation_id,
    ):
        return self.messages


class FakeDocumentService:
    def __init__(self):
        self.documents = {}
        self.jobs = {}

    def create_or_get_upload(
        self,
        document_id,
        file_name,
        knowledge_base_id=None,
    ):
        existing = self.documents.get(
            document_id
        )

        if existing is not None:
            job = self.jobs[
                existing.task_id
            ]

            return (
                existing.document,
                job,
                False,
            )

        document = SimpleNamespace(
            id=document_id,
            file_name=file_name,
            status=DocumentStatus.PENDING,
        )

        job = SimpleNamespace(
            id=f"task-{document_id[:12]}",
            document_id=document_id,
            status=(
                IngestionJobStatus.PENDING
            ),
            error=None,
        )

        record = SimpleNamespace(
            document=document,
            task_id=job.id,
        )

        self.documents[
            document_id
        ] = record

        self.jobs[job.id] = job

        return document, job, True

    def get_ingestion_job(
        self,
        task_id,
    ):
        return self.jobs.get(task_id)


    def delete_document(
        self,
        document_id,
    ):
        record = self.documents.get(
            document_id
        )

        if record is None:
            return None

        record.document.status = (
            DocumentStatus.DELETED
        )

        return record.document

@pytest.fixture(autouse=True)
def fake_document_service():
    service = FakeDocumentService()

    app.dependency_overrides[
        get_document_service
    ] = lambda: service

    yield service

    app.dependency_overrides.pop(
        get_document_service,
        None,
    )

@pytest.fixture(autouse=True)
def fake_conversation_service():
    service = FakeConversationService()

    app.dependency_overrides[
        get_conversation_service
    ] = lambda: service

    yield service

    app.dependency_overrides.pop(
        get_conversation_service,
        None,
    )


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

def test_chat_rejects_empty_context_ids():
    for field_name in (
        "conversation_id",
        "knowledge_base_id",
    ):
        response = client.post(
            "/api/v1/chat",
            json={
                "question": "测试问题",
                field_name: "",
            },
        )

        assert response.status_code == 422


def test_chat_success(
    fake_conversation_service,
):
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
    assert "latency_ms" in data
    assert isinstance(data["latency_ms"], float)
    assert data["latency_ms"] >= 0
    assert (
        data["conversation_id"]
        == "test-conversation-id"
    )

    assert len(
        fake_conversation_service
        .saved_exchanges
    ) == 1

    saved_exchange = (
        fake_conversation_service
        .saved_exchanges[0]
    )

    assert (
        saved_exchange["user_content"]
        == "测试问题"
    )

    assert (
        saved_exchange[
            "assistant_content"
        ]
        == "测试答案"
    )

    assert saved_exchange[
        "source_summary"
    ] == {
        "sources": []
    }

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
    fake_service = MagicMock()

    fake_service\
        .update_ingestion_status\
        .return_value = SimpleNamespace(
            id="task-success"
        )

    with patch(
        "app.services.ingestion."
        "ingestion_service.SessionLocal"
    ) as mocked_session_local, patch(
        "app.services.ingestion."
        "ingestion_service.DocumentService",
        return_value=fake_service,
    ), patch(
        "app.services.ingestion."
        "ingestion_service.ingest_file"
    ) as mocked_ingest:
        run_ingestion_task(
            "task-success",
            "fake-file.txt",
        )

    assert (
        fake_service
        .update_ingestion_status
        .call_args_list
        == [
            call(
                task_id="task-success",
                status=(
                    IngestionJobStatus.RUNNING
                ),
            ),
            call(
                task_id="task-success",
                status=(
                    IngestionJobStatus
                    .SUCCEEDED
                ),
            ),
        ]
    )

    mocked_ingest.assert_called_once_with(
        "fake-file.txt"
    )

    mocked_session_local\
        .return_value.close\
        .assert_called_once()


def test_ingestion_task_fails():
    fake_service = MagicMock()

    fake_service\
        .update_ingestion_status\
        .return_value = SimpleNamespace(
            id="task-failure"
        )

    with patch(
        "app.services.ingestion."
        "ingestion_service.SessionLocal"
    ) as mocked_session_local, patch(
        "app.services.ingestion."
        "ingestion_service.DocumentService",
        return_value=fake_service,
    ), patch(
        "app.services.ingestion."
        "ingestion_service.ingest_file",
        side_effect=RuntimeError(
            "ingestion failed"
        ),
    ):
        run_ingestion_task(
            "task-failure",
            "broken-file.txt",
        )

    assert (
        fake_service
        .update_ingestion_status
        .call_args_list
        == [
            call(
                task_id="task-failure",
                status=(
                    IngestionJobStatus.RUNNING
                ),
            ),
            call(
                task_id="task-failure",
                status=(
                    IngestionJobStatus.FAILED
                ),
                error="ingestion failed",
            ),
        ]
    )

    mocked_session_local\
        .return_value.close\
        .assert_called_once()

def test_chat_upstream_timeout():
    with patch(
        "app.api.routes.chat.answer_question",
        side_effect=UpstreamTimeoutError("模型调用超时"),
    ):
        response = client.post(
            "/api/v1/chat",
            json={
                "question": "测试问题",
            },
        )

    assert response.status_code == 504

    data = response.json()

    assert data["error"] == "upstream_timeout"
    assert data["message"] == "上游服务响应超时，请稍后重试"
    assert data["request_id"]
    assert response.headers["X-Request-ID"] == data["request_id"]


def test_chat_upstream_service_error():
    with patch(
        "app.api.routes.chat.answer_question",
        side_effect=UpstreamServiceError("上游返回敏感错误"),
    ):
        response = client.post(
            "/api/v1/chat",
            json={
                "question": "测试问题",
            },
        )

    assert response.status_code == 502

    data = response.json()

    assert data["error"] == "upstream_service_error"
    assert data["message"] == "上游服务暂时不可用，请稍后重试"
    assert data["request_id"]
    assert "上游返回敏感错误" not in response.text
    assert response.headers["X-Request-ID"] == data["request_id"]


def test_get_conversation_messages(
    fake_conversation_service,
):
    fake_conversation_service.messages = [
        {
            "id": "message-1",
            "sequence_number": 1,
            "role": "user",
            "content": "员工有多少天年假？",
            "source_summary": None,
            "created_at": (
                "2026-08-17T10:00:00"
            ),
        },
        {
            "id": "message-2",
            "sequence_number": 2,
            "role": "assistant",
            "content": (
                "员工年假根据工龄确定。[S1]"
            ),
            "source_summary": {
                "sources": [
                    {
                        "source_id": "S1",
                        "chunk_id": "chunk-1",
                    }
                ]
            },
            "created_at": (
                "2026-08-17T10:00:01"
            ),
        },
    ]

    response = client.get(
        "/api/v1/conversations/"
        "test-conversation-id/messages"
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["conversation_id"]
        == "test-conversation-id"
    )

    assert len(data["messages"]) == 2

    assert [
        message["role"]
        for message in data["messages"]
    ] == [
        "user",
        "assistant",
    ]


def test_get_missing_conversation(
    fake_conversation_service,
    monkeypatch,
):
    def raise_not_found(
        conversation_id,
    ):
        raise ConversationNotFoundError(
            "Conversation not found"
        )

    monkeypatch.setattr(
        fake_conversation_service,
        "get_messages",
        raise_not_found,
    )

    response = client.get(
        "/api/v1/conversations/"
        "missing-conversation/messages"
    )

    assert response.status_code == 404

    data = response.json()

    assert (
        data["error"]
        == "conversation_not_found"
    )

    assert data["request_id"]

    assert (
        response.headers["X-Request-ID"]
        == data["request_id"]
    )


def test_delete_document(
    fake_document_service,
):
    document_id = "9" * 64

    fake_document_service\
        .create_or_get_upload(
            document_id=document_id,
            file_name="delete-api.txt",
        )

    response = client.delete(
        f"/api/v1/documents/{document_id}"
    )

    assert response.status_code == 200

    assert response.json() == {
        "document_id": document_id,
        "status": "deleted",
    }


def test_delete_missing_document(
    fake_document_service,
):
    response = client.delete(
        "/api/v1/documents/"
        + ("8" * 64)
    )

    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == "Document not found"
    )