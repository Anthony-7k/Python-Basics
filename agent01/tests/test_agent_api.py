from fastapi.testclient import TestClient

from app.api.authentication import get_current_user
from app.api.dependencies import get_agent_service
from app.core.rate_limit import request_limiter
from app.core.security import AuthenticatedUser
from app.main import app
from app.schemas.agent import (
    AgentResponse,
    AgentStatus,
    AgentTrace,
)


client = TestClient(app)


class FakeAgentService:
    def run(self, request, request_id):
        return AgentResponse(
            status=AgentStatus.SUCCEEDED,
            answer="受控总结",
            trace=AgentTrace(
                request_id=request_id,
                step_count=1,
                stop_reason="completed",
            ),
        )


def test_agent_route_requires_bearer_authentication():
    response = client.post(
        "/api/v1/agent/run",
        json={
            "knowledge_base_id": "kb-a",
            "instruction": "年假是多少？",
        },
    )

    assert response.status_code == 401


def test_agent_route_returns_request_trace():
    current_user = AuthenticatedUser(
        email="agent@example.com"
    )
    request_limiter.clear()
    app.dependency_overrides[
        get_current_user
    ] = lambda: current_user
    app.dependency_overrides[
        get_agent_service
    ] = lambda: FakeAgentService()

    try:
        response = client.post(
            "/api/v1/agent/run",
            headers={
                "Authorization": "Bearer ignored"
            },
            json={
                "knowledge_base_id": "kb-a",
                "instruction": "总结这份文档",
                "document_ids": ["doc-a"],
            },
        )
    finally:
        app.dependency_overrides.pop(
            get_current_user,
            None,
        )
        app.dependency_overrides.pop(
            get_agent_service,
            None,
        )
        request_limiter.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "受控总结"
    assert payload["trace"]["step_count"] == 1
    assert payload["trace"]["request_id"] == (
        response.headers["X-Request-ID"]
    )
