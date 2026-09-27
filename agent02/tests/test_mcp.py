from __future__ import annotations

import pytest

from app.mcp_client import EnterpriseMCPClient


@pytest.mark.asyncio
async def test_mcp_server_lists_and_calls_tools():
    client = EnterpriseMCPClient()
    tools = await client.list_tools()
    assert "get_company_policy" in tools
    assert "calculate_workdays" in tools
    result = await client.call_tool("get_company_policy", {"topic": "年假制度"})
    assert "10 天" in result["answer"]
    assert result["sources"][0]["source_id"] == "MCP1"


def test_agent_can_select_mcp_tool(client):
    response = client.post(
        "/api/v1/agent/chat",
        json={
            "message": "通过 MCP 查询年假制度",
            "user_id": "user-1",
            "session_id": "mcp-session",
        },
    )
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert [call["name"] for call in data["tool_calls"]] == ["mcp_company_policy"]
    assert data["sources"][0]["source_id"] == "MCP1"
