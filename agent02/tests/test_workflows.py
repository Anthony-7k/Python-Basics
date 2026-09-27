from __future__ import annotations

import pytest

from app.agent.planner import PlannerResult
from app.domain import AgentRequest, ToolCall
from app.service import AgentService
from tests.conftest import chat_payload


def test_single_knowledge_tool_returns_sources(client):
    response = client.post("/api/v1/agent/chat", json=chat_payload("查询公司年假制度"))
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert [call["name"] for call in data["tool_calls"]] == ["knowledge"]
    assert data["sources"][0]["source_id"] == "S1"
    assert "年假" in data["answer"]


def test_multi_tool_uses_knowledge_then_calculator(client):
    response = client.post(
        "/api/v1/agent/chat",
        json=chat_payload("查询上海差旅标准并计算 3 天最高报销金额"),
    )
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert [call["name"] for call in data["tool_calls"]] == [
        "knowledge",
        "calculator",
    ]
    assert data["tool_results"][1]["data"]["result"] == 2250
    assert "2250" in data["answer"]


def test_five_day_travel_total_includes_formula(client):
    response = client.post(
        "/api/v1/agent/chat",
        json=chat_payload("查询上海差旅标准并计算 5 天最高报销金额"),
    )
    data = response.json()

    assert data["status"] == "COMPLETED"
    assert [call["name"] for call in data["tool_calls"]] == [
        "knowledge",
        "calculator",
    ]
    assert data["tool_results"][1]["data"]["result"] == 3750
    assert "750 × 5 = 3750" in data["answer"]


@pytest.mark.asyncio
async def test_travel_total_cannot_complete_without_calculator(settings, database):
    class IncompletePlanner:
        async def plan(self, message, tool_schemas):
            return PlannerResult(
                tool_calls=[ToolCall(name="knowledge", arguments={"query": message})]
            )

    session = database.session_factory()
    service = AgentService(session, settings, planner=IncompletePlanner())

    response = await service.run(
        AgentRequest(
            message="查询上海差旅标准并计算五天最高报销金额",
            user_id="validation-user",
            session_id="validation-session",
        ),
        "req-incomplete-plan",
    )

    assert response.status.value == "FAILED"
    assert response.error is not None
    assert response.error.error_type == "incomplete_tool_plan"
    assert "五天" not in response.answer
    assert "5 天差旅总额" in response.answer


@pytest.mark.asyncio
async def test_task_creation_cannot_complete_with_calendar(settings, database):
    class IncorrectPlanner:
        async def plan(self, message, tool_schemas):
            return PlannerResult(
                tool_calls=[
                    ToolCall(
                        name="calendar",
                        arguments={"start_date": "2025-01-06", "workdays": 5},
                    )
                ]
            )

    session = database.session_factory()
    service = AgentService(session, settings, planner=IncorrectPlanner())

    response = await service.run(
        AgentRequest(
            message="创建任务：周五前提交预算复盘",
            user_id="validation-user",
            session_id="validation-session",
        ),
        "req-task-calendar-plan",
    )

    assert response.status.value == "FAILED"
    assert response.error is not None
    assert response.error.error_type == "incomplete_tool_plan"
    assert "人工审批" in response.answer


def test_multi_step_leave_plan_uses_calendar(client):
    response = client.post(
        "/api/v1/agent/chat",
        json=chat_payload("根据年假制度从 2026-09-07 安排 3 天休假方案"),
    )
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert [call["name"] for call in data["tool_calls"]] == [
        "knowledge",
        "calendar",
    ]
    assert data["tool_results"][1]["data"]["workdays"] == [
        "2026-09-07",
        "2026-09-08",
        "2026-09-09",
    ]


def test_unanswerable_request_stops_without_tool(client):
    response = client.post(
        "/api/v1/agent/chat", json=chat_payload("写一首关于宇宙的长诗")
    )
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["tool_calls"] == []
    assert "无法可靠完成" in data["answer"]


def test_max_steps_stops_loop_before_second_tool(client):
    payload = chat_payload("查询上海差旅标准并计算 3 天最高报销金额")
    payload["max_steps"] = 1
    response = client.post("/api/v1/agent/chat", json=payload)
    data = response.json()
    assert data["status"] == "FAILED"
    assert data["current_step"] == 1
    assert data["error"]["error_type"] == "max_steps_exceeded"
