from __future__ import annotations

import pytest
from pydantic import SecretStr
from sqlalchemy import select

from app.agent.planner import OpenAICompatiblePlanner
from app.database import LLMCallRecord
from app.domain import AgentRequest, TokenUsage
from app.llm import (
    FakeProvider,
    LLMProviderError,
    ProviderResponse,
    ProviderToolCall,
)
from app.service import AgentService
from app.tools import build_tool_registry


def live_settings(settings):
    return settings.model_copy(
        update={
            "planner_mode": "openai",
            "llm_api_key": SecretStr("test-key"),
            "llm_model": "test-model",
            "llm_input_cost_per_million": 1.0,
            "llm_output_cost_per_million": 2.0,
        }
    )


@pytest.mark.asyncio
async def test_fake_provider_parses_calls_and_estimates_cost(settings):
    provider = FakeProvider(
        ProviderResponse(
            tool_calls=[
                ProviderToolCall(
                    call_id="call-1",
                    name="calculator",
                    arguments_json='{"operation":"add","left":2,"right":3}',
                )
            ],
            usage=TokenUsage(input_tokens=100, output_tokens=50),
            provider="fake",
            model="test-model",
        )
    )
    planner = OpenAICompatiblePlanner(live_settings(settings), provider)

    result = await planner.plan("计算 2 + 3", [])

    assert result.tool_calls[0].name == "calculator"
    assert result.tool_calls[0].arguments["left"] == 2
    assert result.estimated_cost_usd == 0.0002
    assert provider.requests[0]["message"] == "计算 2 + 3"


@pytest.mark.asyncio
async def test_invalid_tool_json_is_rejected(settings):
    provider = FakeProvider(
        ProviderResponse(
            tool_calls=[
                ProviderToolCall(
                    call_id="call-1",
                    name="calculator",
                    arguments_json="not-json",
                )
            ],
            provider="fake",
            model="test-model",
        )
    )
    planner = OpenAICompatiblePlanner(live_settings(settings), provider)

    with pytest.raises(LLMProviderError, match="invalid tool arguments") as exc:
        await planner.plan("calculate", [])
    assert exc.value.error_type == "invalid_model_response"


@pytest.mark.parametrize("duration", ["5 天", "五天"])
@pytest.mark.asyncio
async def test_travel_total_guardrail_repairs_incomplete_live_model_plan(
    settings, duration
):
    provider = FakeProvider(
        ProviderResponse(
            tool_calls=[
                ProviderToolCall(
                    call_id="call-policy",
                    name="mcp_company_policy",
                    arguments_json='{"topic":"上海差旅标准"}',
                ),
                ProviderToolCall(
                    call_id="call-knowledge",
                    name="knowledge",
                    arguments_json='{"query":"上海差旅标准"}',
                ),
            ],
            usage=TokenUsage(input_tokens=120, output_tokens=30),
            provider="fake",
            model="test-model",
        )
    )
    guarded_settings = live_settings(settings)
    planner = OpenAICompatiblePlanner(guarded_settings, provider)

    result = await planner.plan(
        f"查询上海差旅标准并计算 {duration}最高报销金额",
        build_tool_registry(guarded_settings).schemas(),
    )

    assert [call.name for call in result.tool_calls] == ["knowledge", "calculator"]
    assert result.tool_calls[1].arguments == {
        "operation": "multiply",
        "left": "$tool.knowledge.facts.daily_total_limit",
        "right": 5,
    }
    assert result.token_usage.total_tokens == 150


@pytest.mark.asyncio
async def test_task_creation_guardrail_replaces_calendar_plan(settings):
    provider = FakeProvider(
        ProviderResponse(
            tool_calls=[
                ProviderToolCall(
                    call_id="call-calendar",
                    name="calendar",
                    arguments_json='{"start_date":"2025-01-06","workdays":5}',
                )
            ],
            usage=TokenUsage(input_tokens=80, output_tokens=20),
            provider="fake",
            model="test-model",
        )
    )
    guarded_settings = live_settings(settings)
    planner = OpenAICompatiblePlanner(guarded_settings, provider)

    result = await planner.plan(
        "创建任务：周五前提交预算复盘",
        build_tool_registry(guarded_settings).schemas(),
    )

    assert [call.name for call in result.tool_calls] == ["task"]
    assert result.tool_calls[0].arguments == {
        "action": "create",
        "title": "周五前提交预算复盘",
        "due_date": None,
    }
    assert result.token_usage.total_tokens == 100


@pytest.mark.asyncio
async def test_provider_error_becomes_stable_task_failure_and_is_recorded(
    settings, database
):
    provider = FakeProvider(
        error=LLMProviderError(
            "llm_timeout",
            "provider timed out",
            retryable=True,
            provider="fake",
            model="test-model",
        )
    )
    planner = OpenAICompatiblePlanner(live_settings(settings), provider)
    session = database.session_factory()
    service = AgentService(session, live_settings(settings), planner=planner)

    response = await service.run(
        AgentRequest(
            message="使用真实模型",
            user_id="user-1",
            session_id="session-1",
        ),
        "req-llm-timeout",
    )

    assert response.status.value == "FAILED"
    assert response.error is not None
    assert response.error.error_type == "llm_timeout"
    record = session.scalar(select(LLMCallRecord))
    assert record is not None
    assert record.error_type == "llm_timeout"
    assert record.provider == "fake"


@pytest.mark.asyncio
async def test_usage_and_null_cost_are_persisted_without_fabrication(
    settings, database
):
    provider = FakeProvider(
        ProviderResponse(
            content="模型直接回答",
            usage=TokenUsage(input_tokens=12, output_tokens=7),
            provider="fake",
            model="test-model",
        )
    )
    no_price_settings = live_settings(settings).model_copy(
        update={
            "llm_input_cost_per_million": None,
            "llm_output_cost_per_million": None,
        }
    )
    planner = OpenAICompatiblePlanner(no_price_settings, provider)
    session = database.session_factory()
    service = AgentService(session, no_price_settings, planner=planner)

    response = await service.run(
        AgentRequest(
            message="模型直接回答",
            user_id="user-1",
            session_id="session-1",
        ),
        "req-llm-usage",
    )

    assert response.status.value == "COMPLETED"
    assert response.token_usage.total_tokens == 19
    record = session.scalar(select(LLMCallRecord))
    assert record is not None
    assert record.input_tokens == 12
    assert record.output_tokens == 7
    assert record.estimated_cost_usd is None
