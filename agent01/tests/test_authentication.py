from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.authentication import (
    get_current_user,
)
from app.api.dependencies import (
    get_conversation_service,
)
from app.core.rate_limit import request_limiter
from app.main import app


client = TestClient(app)


class FakeConversationService:
    def get_or_create_conversation(
        self,
        conversation_id=None,
        knowledge_base_id=None,
    ):
        return SimpleNamespace(
            id="auth-conversation",
            knowledge_base_id=(
                knowledge_base_id or "auth-kb"
            ),
        )

    def prepare_context(self, conversation_id):
        return SimpleNamespace(
            summary=None,
            history=[],
        )

    def save_exchange(self, **exchange):
        return None


def test_health_remains_public():
    response = client.get("/health")
    assert response.status_code == 200


def test_protected_route_rejects_missing_and_bad_token():
    for headers in (
        {},
        {"Authorization": "Bearer wrong-token"},
    ):
        response = client.get(
            "/api/v1/knowledge-bases",
            headers=headers,
        )
        assert response.status_code == 401
        assert response.json()["detail"] == (
            "Missing or invalid credentials"
        )
        assert (
            response.headers["WWW-Authenticate"]
            == "Bearer"
        )
        assert "wrong-token" not in response.text


def test_valid_bearer_token_creates_request_identity():
    request_limiter.clear()
    service = FakeConversationService()
    app.dependency_overrides[
        get_conversation_service
    ] = lambda: service

    try:
        with patch.dict(
            "app.api.authentication.DEMO_AUTH_USERS",
            {"valid-demo-token": "alice@example.com"},
            clear=True,
        ), patch(
            "app.api.routes.chat.answer_question",
            return_value={
                "answer": "安全回答",
                "sources": [],
                "used_chunk_ids": [],
                "request_id": "auth-request",
            },
        ):
            response = client.post(
                "/api/v1/chat",
                headers={
                    "Authorization": (
                        "Bearer valid-demo-token"
                    )
                },
                json={
                    "knowledge_base_id": "auth-kb",
                    "question": "认证测试",
                },
            )
    finally:
        app.dependency_overrides.pop(
            get_conversation_service,
            None,
        )
        app.dependency_overrides.pop(
            get_current_user,
            None,
        )
        request_limiter.clear()

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
