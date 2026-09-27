from __future__ import annotations

from tests.test_auth_tenant_v2 import authorization, token_for


def test_prometheus_endpoint_records_http_agent_and_tool_metrics(client):
    token = token_for(
        client,
        subject="metrics-operator",
        tenant="metrics-tenant",
        roles=["operator"],
    )
    response = client.post(
        "/api/v2/agent/chat",
        headers=authorization(token),
        json={"message": "查询公司年假制度"},
    )
    assert response.status_code == 200

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "agent_http_requests_total" in metrics.text
    assert "agent_tasks_total" in metrics.text
    assert 'agent_tool_calls_total{outcome="success",tool="knowledge"}' in metrics.text
    assert "metrics-tenant" not in metrics.text


def test_metrics_summary_is_tenant_scoped_and_role_protected(client):
    operator = token_for(
        client,
        subject="operator",
        tenant="summary-tenant",
        roles=["operator"],
    )
    client.post(
        "/api/v2/agent/chat",
        headers=authorization(operator),
        json={"message": "查询公司年假制度"},
    )
    summary = client.get("/api/v2/metrics/summary", headers=authorization(operator))
    assert summary.status_code == 200
    body = summary.json()
    assert body["window_hours"] == 24
    assert body["task_count"] == 1
    assert body["task_success_rate"] == 1.0
    assert body["tool_call_count"] == 1

    viewer = token_for(
        client,
        subject="viewer",
        tenant="summary-tenant",
        roles=["viewer"],
    )
    denied = client.get("/api/v2/metrics/summary", headers=authorization(viewer))
    assert denied.status_code == 403


def test_metrics_endpoint_can_be_disabled(app, client):
    app.state.settings.prometheus_enabled = False
    response = client.get("/metrics")
    assert response.status_code == 404
