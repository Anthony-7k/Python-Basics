from types import SimpleNamespace
from datetime import datetime, timezone
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
    get_knowledge_base_service,
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
            ),
            knowledge_base_id=(
                knowledge_base_id
                or "test-kb-id"
            ),
        )

    def save_exchange(
        self,
        **exchange,
    ):
        self.saved_exchanges.append(
            exchange
        )

    def prepare_context(
        self,
        conversation_id,
    ):
        return SimpleNamespace(
            summary=None,
            history=[],
            estimated_tokens=0,
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
        content_hash,
        file_name,
        knowledge_base_id=None,
    ):
        knowledge_base_id = (
            knowledge_base_id
            or "test-kb-id"
        )
        document_id = content_hash
        key = (
            knowledge_base_id,
            content_hash,
        )
        existing = self.documents.get(
            key
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
            knowledge_base_id=(
                knowledge_base_id
            ),
            file_name=file_name,
            content_hash=content_hash,
            status=DocumentStatus.PENDING,
            created_at=datetime.now(
                timezone.utc
            ),
            updated_at=datetime.now(
                timezone.utc
            ),
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
            key
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
        knowledge_base_id,
        document_id,
    ):
        record = next(
            (
                value
                for key, value
                in self.documents.items()
                if key[0] == knowledge_base_id
                and value.document.id
                == document_id
            ),
            None,
        )

        if record is None:
            return None

        record.document.status = (
            DocumentStatus.DELETED
        )

        return record.document

    def list_documents(
        self,
        knowledge_base_id,
        include_deleted=False,
    ):
        return [
            record.document
            for key, record
            in self.documents.items()
            if key[0] == knowledge_base_id
            and (
                include_deleted
                or record.document.status
                != DocumentStatus.DELETED
            )
        ]

    def get_document(
        self,
        knowledge_base_id,
        document_id,
    ):
        for key, record in self.documents.items():
            if (
                key[0] == knowledge_base_id
                and record.document.id
                == document_id
            ):
                return record.document
        return None

    def request_reindex(
        self,
        knowledge_base_id,
        document_id,
    ):
        document = self.get_document(
            knowledge_base_id,
            document_id,
        )
        if document is None:
            return None
        job = SimpleNamespace(
            id=f"reindex-{document_id[:12]}",
            document_id=document_id,
            status=IngestionJobStatus.PENDING,
        )
        self.jobs[job.id] = job
        return document, job, True


class FakeKnowledgeBaseService:
    def __init__(self):
        self.items = {}

    def create(self, name, description=None):
        knowledge_base = SimpleNamespace(
            id=f"kb-{len(self.items) + 1}",
            name=name,
            description=description,
            created_at=datetime.now(
                timezone.utc
            ),
            updated_at=datetime.now(
                timezone.utc
            ),
        )
        self.items[knowledge_base.id] = (
            knowledge_base
        )
        return knowledge_base

    def list(self):
        return list(self.items.values())

    def get(self, knowledge_base_id):
        return self.items[knowledge_base_id]

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


@pytest.fixture(autouse=True)
def fake_knowledge_base_service():
    service = FakeKnowledgeBaseService()
    app.dependency_overrides[
        get_knowledge_base_service
    ] = lambda: service
    yield service
    app.dependency_overrides.pop(
        get_knowledge_base_service,
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


def test_chat_uses_rewritten_question_for_rag(
    fake_conversation_service,
):
    fake_conversation_service.prepare_context = (
        lambda conversation_id: SimpleNamespace(
            summary="上一轮讨论年假",
            history=[
                {
                    "role": "assistant",
                    "content": "年假按工龄计算",
                }
            ],
            estimated_tokens=20,
        )
    )
    fake_response = {
        "answer": "正式员工按工龄享有年假。[S1]",
        "sources": [],
        "used_chunk_ids": [],
        "request_id": "rewrite-request-id",
    }

    with patch(
        "app.api.routes.chat.condense_question",
        return_value=(
            "正式员工的年假规定是什么？"
        ),
    ) as mocked_condense, patch(
        "app.api.routes.chat.answer_question",
        return_value=fake_response,
    ) as mocked_answer:
        response = client.post(
            "/api/v1/chat",
            json={
                "question": "正式员工呢？"
            },
        )

    assert response.status_code == 200
    assert (
        mocked_condense.call_args.kwargs[
            "current_question"
        ]
        == "正式员工呢？"
    )
    answer_kwargs = (
        mocked_answer.call_args.kwargs
    )

    assert answer_kwargs[
        "original_question"
    ] == "正式员工呢？"
    assert answer_kwargs[
        "standalone_question"
    ] == "正式员工的年假规定是什么？"
    assert answer_kwargs[
        "knowledge_base_id"
    ] == "test-kb-id"
    assert answer_kwargs["request_id"]

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
            id="task-success",
            document_id="document-success",
        )
    fake_service.document_repository\
        .get_document.return_value = (
            SimpleNamespace(
                id="document-success",
                knowledge_base_id="kb-a",
            )
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
        "fake-file.txt",
        document_id="document-success",
        knowledge_base_id="kb-a",
    )

    mocked_session_local\
        .return_value.close\
        .assert_called_once()


def test_ingestion_task_fails():
    fake_service = MagicMock()

    fake_service\
        .update_ingestion_status\
        .return_value = SimpleNamespace(
            id="task-failure",
            document_id="document-failure",
        )
    fake_service.document_repository\
        .get_document.return_value = (
            SimpleNamespace(
                id="document-failure",
                knowledge_base_id="kb-a",
            )
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
            content_hash=document_id,
            file_name="delete-api.txt",
            knowledge_base_id="test-kb-id",
        )

    response = client.delete(
        f"/api/v1/documents/{document_id}",
        params={
            "knowledge_base_id": "test-kb-id"
        },
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
        + ("8" * 64),
        params={
            "knowledge_base_id": "test-kb-id"
        },
    )

    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == "Document not found"
    )


def test_delete_requires_knowledge_base_id():
    response = client.delete(
        "/api/v1/documents/"
        + ("7" * 64)
    )
    assert response.status_code == 422


def test_knowledge_base_create_list_and_detail(
    fake_knowledge_base_service,
):
    created = client.post(
        "/api/v1/knowledge-bases",
        json={
            "name": "HR Policies",
            "description": "Human resources",
        },
    )
    assert created.status_code == 201
    knowledge_base_id = created.json()["id"]

    listed = client.get(
        "/api/v1/knowledge-bases"
    )
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1

    detail = client.get(
        "/api/v1/knowledge-bases/"
        + knowledge_base_id
    )
    assert detail.status_code == 200
    assert detail.json()["name"] == (
        "HR Policies"
    )


def test_document_list_is_scoped_to_knowledge_base(
    fake_document_service,
):
    content_hash = "6" * 64
    fake_document_service.create_or_get_upload(
        content_hash=content_hash,
        file_name="a.txt",
        knowledge_base_id="kb-a",
    )
    fake_document_service.create_or_get_upload(
        content_hash="5" * 64,
        file_name="b.txt",
        knowledge_base_id="kb-b",
    )

    response = client.get(
        "/api/v1/knowledge-bases/kb-a/documents"
    )
    assert response.status_code == 200
    assert [
        item["id"]
        for item in response.json()["items"]
    ] == [content_hash]


def test_reindex_creates_background_job(
    fake_document_service,
    tmp_path,
):
    content_hash = "4" * 64
    document, _, _ = (
        fake_document_service
        .create_or_get_upload(
            content_hash=content_hash,
            file_name="reindex.txt",
            knowledge_base_id="kb-a",
        )
    )
    source_path = tmp_path / "source.txt"
    source_path.write_text(
        "reindex source",
        encoding="utf-8",
    )

    with patch(
        "app.api.routes.documents."
        "get_uploaded_file_path",
        return_value=source_path,
    ), patch(
        "app.api.routes.documents."
        "run_ingestion_task"
    ) as mocked_ingestion:
        response = client.post(
            "/api/v1/knowledge-bases/kb-a/"
            f"documents/{document.id}/reindex"
        )

    assert response.status_code == 202
    assert response.json()["task_id"].startswith(
        "reindex-"
    )
    mocked_ingestion.assert_called_once()
