from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.authentication import get_current_user
from app.api.dependencies import (
    get_conversation_service,
    get_document_service,
)
from app.core.exceptions import (
    RateLimitExceededError,
)
from app.core.rate_limit import (
    InMemoryRateLimiter,
    request_limiter,
)
from app.core.security import AuthenticatedUser
from app.main import app
from app.models import IngestionJobStatus


class FakeConversationService:
    def get_or_create_conversation(
        self,
        conversation_id=None,
        knowledge_base_id=None,
    ):
        return SimpleNamespace(
            id="rate-conversation",
            knowledge_base_id="rate-kb",
        )

    def prepare_context(self, conversation_id):
        return SimpleNamespace(
            summary=None,
            history=[],
        )

    def save_exchange(self, **exchange):
        return None


class FakeDocumentService:
    def create_or_get_upload(
        self,
        content_hash,
        file_name,
        knowledge_base_id=None,
    ):
        return (
            SimpleNamespace(id=content_hash),
            SimpleNamespace(
                id="rate-upload-task",
                status=IngestionJobStatus.PENDING,
            ),
            True,
        )


def test_limiter_keeps_scopes_and_users_separate():
    limiter = InMemoryRateLimiter()
    limiter.check("chat", "alice", 1, 60)
    limiter.check("upload", "alice", 1, 60)
    limiter.check("chat", "bob", 1, 60)

    with pytest.raises(RateLimitExceededError):
        limiter.check("chat", "alice", 1, 60)


def test_chat_limit_returns_stable_429_response():
    user = AuthenticatedUser(
        email="rate-user@example.com"
    )
    request_limiter.clear()
    app.dependency_overrides[
        get_current_user
    ] = lambda: user
    app.dependency_overrides[
        get_conversation_service
    ] = lambda: FakeConversationService()

    try:
        with patch(
            "app.api.routes.chat.CHAT_RATE_LIMIT_REQUESTS",
            1,
        ), patch(
            "app.api.routes.chat.answer_question",
            return_value={
                "answer": "ok",
                "sources": [],
                "used_chunk_ids": [],
                "request_id": "rate-request",
            },
        ):
            client = TestClient(app)
            first = client.post(
                "/api/v1/chat",
                headers={
                    "Authorization": "Bearer ignored"
                },
                json={
                    "knowledge_base_id": "rate-kb",
                    "question": "first",
                },
            )
            second = client.post(
                "/api/v1/chat",
                headers={
                    "Authorization": "Bearer ignored"
                },
                json={
                    "knowledge_base_id": "rate-kb",
                    "question": "second",
                },
            )
    finally:
        app.dependency_overrides.pop(
            get_current_user,
            None,
        )
        app.dependency_overrides.pop(
            get_conversation_service,
            None,
        )
        request_limiter.clear()

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"] == (
        "rate_limit_exceeded"
    )
    assert second.json()["request_id"]
    assert int(second.headers["Retry-After"]) >= 1


def test_upload_limit_is_enforced_before_second_file(
    tmp_path,
):
    user = AuthenticatedUser(
        email="upload-rate-user@example.com"
    )
    request_limiter.clear()
    app.dependency_overrides[
        get_current_user
    ] = lambda: user
    app.dependency_overrides[
        get_document_service
    ] = lambda: FakeDocumentService()

    try:
        with patch(
            "app.api.routes.documents.UPLOAD_RATE_LIMIT_REQUESTS",
            1,
        ), patch(
            "app.services.ingestion.uploader.UPLOAD_DIR",
            tmp_path,
        ), patch(
            "app.api.routes.documents.run_ingestion_task"
        ):
            client = TestClient(app)
            first = client.post(
                "/api/v1/documents",
                headers={
                    "Authorization": "Bearer ignored"
                },
                files={
                    "file": (
                        "first.txt",
                        b"safe content",
                        "text/plain",
                    )
                },
            )
            second = client.post(
                "/api/v1/documents",
                headers={
                    "Authorization": "Bearer ignored"
                },
                files={
                    "file": (
                        "second.txt",
                        b"different content",
                        "text/plain",
                    )
                },
            )
    finally:
        app.dependency_overrides.pop(
            get_current_user,
            None,
        )
        app.dependency_overrides.pop(
            get_document_service,
            None,
        )
        request_limiter.clear()

    assert first.status_code == 202
    assert second.status_code == 429
    assert second.json()["error"] == (
        "rate_limit_exceeded"
    )
