import json
import logging
import time
from unittest.mock import MagicMock

from pydantic import BaseModel

from app.core.logging_config import JsonLogFormatter
from app.core.exceptions import UpstreamTimeoutError
from app.core.security import AuthenticatedUser
from app.schemas.agent import (
    AgentRequest,
    AgentStatus,
    SearchKnowledgeArguments,
    ToolCall,
    ToolName,
    ToolStatus,
)
from app.services.agent import (
    AgentRoutePlan,
    BoundedAgentService,
    ToolDefinition,
    ToolExecutionContext,
    ToolExecutionPayload,
    ToolRegistry,
    build_default_tool_registry,
)


def _context() -> ToolExecutionContext:
    return ToolExecutionContext(
        session=MagicMock(),
        current_user=AuthenticatedUser(
            email="agent@example.com"
        ),
        allowed_knowledge_base_id="kb-a",
        request_id="request-a",
    )


def _search_call(**arguments) -> ToolCall:
    values = {
        "knowledge_base_id": "kb-a",
        "query": "年假是多少？",
        "top_k": 5,
    }
    values.update(arguments)
    return ToolCall(
        tool_name=ToolName.SEARCH_KNOWLEDGE,
        selection_reason="test_route",
        arguments=values,
    )


def test_default_registry_contains_only_three_whitelisted_tools():
    assert set(build_default_tool_registry().names) == {
        ToolName.SEARCH_KNOWLEDGE,
        ToolName.SUMMARIZE_DOCUMENT,
        ToolName.COMPARE_DOCUMENTS,
    }


def test_registry_rejects_unknown_invalid_and_cross_scope_calls():
    handler = MagicMock(
        return_value=ToolExecutionPayload(
            output={"answer": "ok"},
            result_summary="ok",
        )
    )
    definition = ToolDefinition(
        name=ToolName.SEARCH_KNOWLEDGE,
        description="test",
        arguments_model=SearchKnowledgeArguments,
        handler=handler,
    )

    unknown = ToolRegistry().execute(
        _search_call(),
        _context(),
        timeout_seconds=1,
    )
    invalid = ToolRegistry([definition]).execute(
        _search_call(query=""),
        _context(),
        timeout_seconds=1,
    )
    cross_scope = ToolRegistry([definition]).execute(
        _search_call(knowledge_base_id="kb-b"),
        _context(),
        timeout_seconds=1,
    )

    assert unknown.error.code == "unknown_tool"
    assert invalid.error.code == "invalid_tool_arguments"
    assert cross_scope.error.code == (
        "knowledge_base_scope_mismatch"
    )
    handler.assert_not_called()


def test_registry_returns_structured_timeout_without_retry_loop():
    calls = 0

    def slow_handler(
        arguments: BaseModel,
        context: ToolExecutionContext,
    ) -> ToolExecutionPayload:
        nonlocal calls
        calls += 1
        time.sleep(0.05)
        return ToolExecutionPayload(
            output={"answer": "late"},
            result_summary="late",
        )

    registry = ToolRegistry(
        [
            ToolDefinition(
                name=ToolName.SEARCH_KNOWLEDGE,
                description="slow test",
                arguments_model=(
                    SearchKnowledgeArguments
                ),
                handler=slow_handler,
            )
        ]
    )
    result = registry.execute(
        _search_call(),
        _context(),
        timeout_seconds=0.001,
    )

    assert result.status == ToolStatus.FAILED
    assert result.error.code == "tool_timeout"
    assert result.error.retryable is True
    assert calls == 1


def test_registry_maps_upstream_timeout_to_readable_error():
    def timeout_handler(arguments, context):
        raise UpstreamTimeoutError("private upstream detail")

    registry = ToolRegistry(
        [
            ToolDefinition(
                name=ToolName.SEARCH_KNOWLEDGE,
                description="timeout test",
                arguments_model=(
                    SearchKnowledgeArguments
                ),
                handler=timeout_handler,
            )
        ]
    )

    result = registry.execute(
        _search_call(),
        _context(),
        timeout_seconds=1,
    )

    assert result.error.code == "upstream_timeout"
    assert result.error.retryable is True
    assert "private upstream detail" not in (
        result.error.message
    )


def test_agent_enforces_step_limit_before_execution():
    calls = [_search_call() for _ in range(3)]

    class ThreeStepRouter:
        def route(self, request):
            return AgentRoutePlan(
                status=AgentStatus.SUCCEEDED,
                message="three steps",
                tool_calls=calls,
            )

    service = BoundedAgentService(
        MagicMock(),
        AuthenticatedUser(email="agent@example.com"),
        registry=ToolRegistry(),
        router=ThreeStepRouter(),
        max_steps=2,
    )
    response = service.run(
        AgentRequest(
            knowledge_base_id="kb-a",
            instruction="普通问题",
        ),
        request_id="step-limit",
    )

    assert response.status == AgentStatus.FAILED
    assert response.error.code == "step_limit_exceeded"
    assert response.trace.step_count == 0


def test_agent_trace_log_does_not_include_question_or_token(caplog):
    sensitive_instruction = (
        "年假是多少？ token=super-secret-token"
    )

    def safe_handler(arguments, context):
        return ToolExecutionPayload(
            output={"answer": "安全答案"},
            result_summary="answered_with_1_sources",
        )

    registry = ToolRegistry(
        [
            ToolDefinition(
                name=ToolName.SEARCH_KNOWLEDGE,
                description="test",
                arguments_model=(
                    SearchKnowledgeArguments
                ),
                handler=safe_handler,
            )
        ]
    )
    service = BoundedAgentService(
        MagicMock(),
        AuthenticatedUser(email="agent@example.com"),
        registry=registry,
    )
    caplog.set_level(logging.INFO)

    response = service.run(
        AgentRequest(
            knowledge_base_id="kb-a",
            instruction=sensitive_instruction,
        ),
        request_id="log-test",
    )

    record = next(
        item
        for item in caplog.records
        if getattr(item, "event", None)
        == "agent_tool_call"
    )
    serialized = JsonLogFormatter().format(record)
    payload = json.loads(serialized)

    assert response.status == AgentStatus.SUCCEEDED
    assert payload["tool_name"] == "search_knowledge"
    assert "年假是多少" not in serialized
    assert "super-secret-token" not in serialized
    assert "安全答案" not in serialized
