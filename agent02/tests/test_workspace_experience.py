from __future__ import annotations

import pytest

from app.agent.planner import OpenAICompatiblePlanner
from app.domain import AgentRequest, TaskStatus
from app.llm import FakeProvider, LLMProviderError, ProviderResponse, ProviderToolCall
from app.service import AgentService
from tests.test_auth_tenant_v2 import authorization, token_for


def test_workspace_requires_verified_identity(client):
    assert client.get("/api/v2/workspace").status_code == 401


def test_workspace_displays_real_identity_and_effective_permissions(client):
    token = token_for(
        client, subject="reviewer", tenant="custom-workspace", roles=["viewer"]
    )
    response = client.get("/api/v2/workspace", headers=authorization(token))
    assert response.status_code == 200
    assert response.json() == {
        "subject": "reviewer",
        "tenant_id": "custom-workspace",
        "roles": ["viewer"],
        "permissions": ["task:read"],
        "environment": "development",
        "planner_mode": "rule_based",
        "knowledge_backend": "sample",
    }
    assert "secret" not in response.text.lower()
    assert "api_key" not in response.text.lower()


def test_task_history_preserves_request_instead_of_using_answer_as_title(client):
    token = token_for(
        client, subject="operator", tenant="task-titles", roles=["operator"]
    )
    message = "查询上海差旅标准并计算 5 天最高报销金额"
    created = client.post(
        "/api/v2/agent/chat", headers=authorization(token), json={"message": message}
    ).json()
    detail = client.get(
        f"/api/v2/tasks/{created['task_id']}", headers=authorization(token)
    ).json()
    history = client.get("/api/v2/tasks", headers=authorization(token)).json()
    assert detail["message"] == message
    assert history[0]["message"] == message
    assert "3750" in detail["answer"]
    assert detail["message"] != detail["answer"]


@pytest.mark.asyncio
async def test_resume_replans_after_provider_failure_before_any_tools(
    settings, database
):
    provider = FakeProvider(
        error=LLMProviderError("llm_timeout", "timed out", retryable=True)
    )
    planner = OpenAICompatiblePlanner(settings, provider)
    with database.session_factory() as session:
        service = AgentService(session, settings, planner=planner)
        failed = await service.run(
            AgentRequest(message="计算 2 + 3", user_id="user", session_id="recovery"),
            "req-resume-planner",
        )
        assert failed.status == TaskStatus.FAILED
        assert failed.tool_calls == []
        provider.error = None
        provider.response = ProviderResponse(
            tool_calls=[
                ProviderToolCall(
                    call_id="addition",
                    name="calculator",
                    arguments_json='{"operation":"add","left":2,"right":3}',
                )
            ],
            provider="fake",
            model="test-model",
        )
        resumed = await service.resume(failed.task_id, "user")
        assert resumed.status == TaskStatus.COMPLETED
        assert len(provider.requests) == 2
        assert resumed.tool_results[0].data["result"] == 5


@pytest.mark.asyncio
async def test_resume_can_replan_to_direct_answer(settings, database):
    provider = FakeProvider(
        error=LLMProviderError("llm_rate_limited", "busy", retryable=True)
    )
    with database.session_factory() as session:
        service = AgentService(
            session, settings, planner=OpenAICompatiblePlanner(settings, provider)
        )
        failed = await service.run(
            AgentRequest(message="你好", user_id="user", session_id="direct"),
            "req-direct",
        )
        provider.error = None
        provider.response = ProviderResponse(content="你好，我可以帮助你处理企业任务。")
        resumed = await service.resume(failed.task_id, "user")
        assert resumed.status == TaskStatus.COMPLETED
        assert resumed.answer == "你好，我可以帮助你处理企业任务。"
