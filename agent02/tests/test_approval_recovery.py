from __future__ import annotations

from tests.conftest import chat_payload


def test_high_risk_tool_waits_then_executes_once(client, app):
    waiting = client.post(
        "/api/v1/agent/chat", json=chat_payload("创建任务：提交周报")
    ).json()
    assert waiting["status"] == "WAITING_APPROVAL"
    assert waiting["tool_results"] == []
    task_tool = app.state.registry.get("task")
    assert task_tool.created_tasks == {}

    approved = client.post(
        f"/api/v1/tasks/{waiting['task_id']}/approve",
        json={"user_id": "user-1"},
    ).json()
    assert approved["status"] == "COMPLETED"
    assert len(task_tool.created_tasks) == 1

    replay = client.post(
        f"/api/v1/tasks/{waiting['task_id']}/approve",
        json={"user_id": "user-1"},
    )
    assert replay.status_code == 409
    assert len(task_tool.created_tasks) == 1


def test_approval_demo_prompt_waits_for_approval(client):
    waiting = client.post(
        "/api/v1/agent/chat",
        json=chat_payload("创建任务：周五前提交预算复盘"),
    ).json()

    assert waiting["status"] == "WAITING_APPROVAL"
    assert waiting["tool_results"] == []
    assert [call["name"] for call in waiting["tool_calls"]] == ["task"]
    assert waiting["tool_calls"][0]["arguments"] == {
        "action": "create",
        "title": "周五前提交预算复盘",
        "due_date": None,
    }


def test_approval_can_modify_payload_and_revalidates(client):
    waiting = client.post(
        "/api/v1/agent/chat", json=chat_payload("创建任务：原始标题")
    ).json()
    approved = client.post(
        f"/api/v1/tasks/{waiting['task_id']}/approve",
        json={
            "user_id": "user-1",
            "modified_payload": {
                "action": "create",
                "title": "修改后的标题",
                "due_date": "2026-09-10",
            },
        },
    ).json()
    assert approved["status"] == "COMPLETED"
    assert approved["tool_results"][0]["data"]["title"] == "修改后的标题"


def test_reject_prevents_side_effect(client, app):
    waiting = client.post(
        "/api/v1/agent/chat", json=chat_payload("创建提醒：发送材料")
    ).json()
    rejected = client.post(
        f"/api/v1/tasks/{waiting['task_id']}/reject",
        json={"user_id": "user-1", "reason": "不需要执行"},
    ).json()
    assert rejected["status"] == "FAILED"
    assert rejected["error"]["error_type"] == "approval_rejected"
    assert app.state.registry.get("task").created_tasks == {}


def test_failed_tool_can_resume_from_checkpoint(client):
    client.app.state.settings.tool_max_retries = 0
    failed = client.post("/api/v1/agent/chat", json=chat_payload("演示故障恢复")).json()
    assert failed["status"] == "FAILED"
    resumed = client.post(
        f"/api/v1/tasks/{failed['task_id']}/resume",
        json={"user_id": "user-1"},
    ).json()
    assert resumed["status"] == "COMPLETED"
    assert resumed["tool_results"][-1]["data"]["attempt"] == 2
    assert "恢复成功" in resumed["answer"]
