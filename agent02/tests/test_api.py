from __future__ import annotations

from tests.conftest import chat_payload


def test_health_returns_request_id(client):
    response = client.get("/api/v1/health", headers={"X-Request-ID": "req-health"})
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "request_id": "req-health",
        "database": "ok",
    }
    assert response.headers["X-Request-ID"] == "req-health"


def test_liveness_does_not_require_database_query(client):
    response = client.get("/live", headers={"X-Request-ID": "req-live"})
    assert response.status_code == 200
    assert response.json() == {
        "status": "alive",
        "request_id": "req-live",
    }


def test_readiness_checks_database(client):
    response = client.get("/ready", headers={"X-Request-ID": "req-ready"})
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "request_id": "req-ready",
        "database": "ok",
    }


def test_chat_rejects_blank_message(client):
    response = client.post("/api/v1/agent/chat", json=chat_payload("   "))
    assert response.status_code == 422


def test_get_task_enforces_user_isolation(client):
    created = client.post(
        "/api/v1/agent/chat", json=chat_payload("查询公司年假制度")
    ).json()
    task_id = created["task_id"]
    denied = client.get(f"/api/v1/tasks/{task_id}", params={"user_id": "another-user"})
    assert denied.status_code == 403
    allowed = client.get(f"/api/v1/tasks/{task_id}", params={"user_id": "user-1"})
    assert allowed.status_code == 200
    assert allowed.json()["session_id"] == "session-1"


def test_missing_task_returns_404(client):
    response = client.get("/api/v1/tasks/missing", params={"user_id": "user-1"})
    assert response.status_code == 404
    assert response.json()["error"] == "task_not_found"
