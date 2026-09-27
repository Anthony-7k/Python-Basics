from __future__ import annotations

import pytest

from app.agent.planner import RuleBasedPlanner


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "operation", "left", "right"),
    [
        ("计算 2 + 3", "add", "2", "3"),
        ("计算 8 除以 2", "divide", "8", "2"),
        ("计算 9 减 4", "subtract", "9", "4"),
    ],
)
async def test_rule_planner_selects_arithmetic_operation(
    message, operation, left, right
):
    result = await RuleBasedPlanner().plan(message, [])
    call = result.tool_calls[0]
    assert call.name == "calculator"
    assert call.arguments == {"operation": operation, "left": left, "right": right}


@pytest.mark.asyncio
async def test_travel_query_without_calculation_uses_only_knowledge():
    result = await RuleBasedPlanner().plan("查询上海差旅制度", [])
    assert [call.name for call in result.tool_calls] == ["knowledge"]


@pytest.mark.asyncio
async def test_task_due_date_is_extracted():
    result = await RuleBasedPlanner().plan("创建任务：2026-09-10 提交材料", [])
    assert result.tool_calls[0].arguments["due_date"] == "2026-09-10"
