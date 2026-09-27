from __future__ import annotations

import pytest

from app.domain import ToolCall
from app.tools.base import ToolContext, ToolRegistry
from app.tools.standard import CalculatorTool, FailureTool


def context(task_id: str = "task-1") -> ToolContext:
    return ToolContext(
        user_id="user-1",
        session_id="session-1",
        task_id=task_id,
        request_id="request-1",
    )


@pytest.mark.asyncio
async def test_unknown_tool_is_structured_failure():
    registry = ToolRegistry([])
    result = await registry.execute(
        ToolCall(name="missing", arguments={}),
        context(),
        timeout_seconds=0.1,
        max_retries=0,
    )
    assert result.success is False
    assert result.error.error_type == "unknown_tool"


@pytest.mark.asyncio
async def test_calculator_rejects_invalid_schema():
    registry = ToolRegistry([CalculatorTool()])
    result = await registry.execute(
        ToolCall(
            name="calculator", arguments={"operation": "hack", "left": 1, "right": 2}
        ),
        context(),
        timeout_seconds=0.1,
        max_retries=0,
    )
    assert result.success is False
    assert result.error.error_type == "invalid_arguments"


@pytest.mark.asyncio
async def test_calculator_does_not_evaluate_code():
    registry = ToolRegistry([CalculatorTool()])
    result = await registry.execute(
        ToolCall(
            name="calculator",
            arguments={"operation": "multiply", "left": "__import__('os')", "right": 2},
        ),
        context(),
        timeout_seconds=0.1,
        max_retries=0,
    )
    assert result.success is False
    assert result.error.error_type == "invalid_arguments"


@pytest.mark.asyncio
async def test_retry_is_bounded_and_recorded():
    registry = ToolRegistry([FailureTool()])
    result = await registry.execute(
        ToolCall(
            name="failure_demo",
            arguments={"failures_before_success": 2, "delay_seconds": 0},
        ),
        context(),
        timeout_seconds=0.2,
        max_retries=2,
    )
    assert result.success is True
    assert result.retry_count == 2
    assert result.data["attempt"] == 3


@pytest.mark.asyncio
async def test_timeout_is_bounded():
    registry = ToolRegistry([FailureTool()])
    result = await registry.execute(
        ToolCall(
            name="failure_demo",
            arguments={"failures_before_success": 0, "delay_seconds": 0.2},
        ),
        context(),
        timeout_seconds=0.01,
        max_retries=0,
    )
    assert result.success is False
    assert result.error.error_type == "tool_timeout"
