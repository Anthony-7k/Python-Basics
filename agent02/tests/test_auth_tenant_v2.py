from __future__ import annotations

from sqlalchemy import select

from app.database import TaskRecord


def token_for(client, *, subject: str, tenant: str, roles: list[str]) -> str:
    response = client.post(
        "/api/v2/auth/dev-token",
        json={"subject": subject, "tenant_id": tenant, "roles": roles},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_v2_requires_bearer_token(client):
    response = client.post(
        "/api/v2/agent/chat",
        json={"message": "查询公司年假制度"},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "missing_token"


def test_v2_identity_comes_from_token_not_request_body(client, database):
    token = token_for(
        client,
        subject="alice",
        tenant="tenant-a",
        roles=["operator"],
    )
    response = client.post(
        "/api/v2/agent/chat",
        headers=authorization(token),
        json={
            "message": "查询公司年假制度",
            "user_id": "forged-user",
            "tenant_id": "tenant-b",
        },
    )
    assert response.status_code == 200

    with database.session_factory() as session:
        record = session.scalar(
            select(TaskRecord).where(TaskRecord.id == response.json()["task_id"])
        )
    assert record is not None
    assert record.user_id == "alice"
    assert record.created_by == "alice"
    assert record.tenant_id == "tenant-a"


def test_cross_tenant_task_access_returns_404(client):
    operator = token_for(
        client,
        subject="alice",
        tenant="tenant-a",
        roles=["operator"],
    )
    created = client.post(
        "/api/v2/agent/chat",
        headers=authorization(operator),
        json={"message": "查询公司年假制度"},
    ).json()
    other_tenant_viewer = token_for(
        client,
        subject="bob",
        tenant="tenant-b",
        roles=["viewer"],
    )

    response = client.get(
        f"/api/v2/tasks/{created['task_id']}",
        headers=authorization(other_tenant_viewer),
    )

    assert response.status_code == 404
    assert response.json()["error"] == "task_not_found"


def test_viewer_cannot_create_and_denial_is_audited(client):
    viewer = token_for(
        client,
        subject="viewer-user",
        tenant="tenant-a",
        roles=["viewer"],
    )
    denied = client.post(
        "/api/v2/agent/chat",
        headers=authorization(viewer),
        json={"message": "查询公司年假制度"},
    )
    assert denied.status_code == 403

    admin = token_for(
        client,
        subject="admin-user",
        tenant="tenant-a",
        roles=["admin"],
    )
    events = client.get(
        "/api/v2/audit-events",
        headers=authorization(admin),
    ).json()
    assert any(
        event["actor"] == "viewer-user"
        and event["action"] == "task.create"
        and event["outcome"] == "denied"
        for event in events
    )


def test_only_approver_can_approve_high_risk_task(client):
    operator = token_for(
        client,
        subject="operator-user",
        tenant="tenant-a",
        roles=["operator"],
    )
    waiting = client.post(
        "/api/v2/agent/chat",
        headers=authorization(operator),
        json={"message": "创建任务：提交周报"},
    ).json()
    denied = client.post(
        f"/api/v2/tasks/{waiting['task_id']}/approve",
        headers=authorization(operator),
        json={},
    )
    assert denied.status_code == 403

    approver = token_for(
        client,
        subject="approver-user",
        tenant="tenant-a",
        roles=["approver"],
    )
    approved = client.post(
        f"/api/v2/tasks/{waiting['task_id']}/approve",
        headers=authorization(approver),
        json={},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "COMPLETED"


def test_invalid_token_is_rejected(client):
    response = client.get(
        "/api/v2/tasks",
        headers=authorization("not-a-jwt"),
    )
    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "invalid_token"
