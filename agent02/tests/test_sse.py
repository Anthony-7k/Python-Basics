from __future__ import annotations

import json

from tests.test_auth_tenant_v2 import authorization, token_for


def parse_sse(text: str) -> list[tuple[str, dict]]:
    events = []
    for block in text.strip().split("\n\n"):
        lines = block.splitlines()
        event = next(line[7:] for line in lines if line.startswith("event: "))
        data = next(line[6:] for line in lines if line.startswith("data: "))
        events.append((event, json.loads(data)))
    return events


def test_sse_emits_ordered_tool_execution_events(client):
    token = token_for(
        client,
        subject="stream-user",
        tenant="tenant-stream",
        roles=["operator"],
    )

    with client.stream(
        "POST",
        "/api/v2/agent/chat/stream",
        headers=authorization(token),
        json={"message": "查询公司年假制度"},
    ) as response:
        body = response.read().decode()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(body)
    names = [name for name, _ in events]
    assert names == [
        "task_created",
        "planning",
        "tool_started",
        "tool_finished",
        "completed",
    ]
    task_ids = {data.get("task_id") for _, data in events}
    assert len(task_ids) == 1


def test_sse_stops_at_approval_required(client):
    token = token_for(
        client,
        subject="stream-user",
        tenant="tenant-stream",
        roles=["operator"],
    )

    with client.stream(
        "POST",
        "/api/v2/agent/chat/stream",
        headers=authorization(token),
        json={"message": "创建任务：提交周报"},
    ) as response:
        events = parse_sse(response.read().decode())

    names = [name for name, _ in events]
    assert names == ["task_created", "planning", "approval_required"]
    assert events[-1][1]["risk_level"] == "HIGH_RISK"
