from __future__ import annotations

from pydantic import BaseModel, Field

from app.mcp_client import EnterpriseMCPClient
from app.tools.base import BaseTool, ToolContext, ToolExecutionFailure


class MCPPolicyArgs(BaseModel):
    topic: str = Field(min_length=1, max_length=1000)


class MCPCompanyPolicyTool(BaseTool[MCPPolicyArgs]):
    name = "mcp_company_policy"
    description = "Call the self-hosted Enterprise Tools MCP server for company policy"
    args_model = MCPPolicyArgs

    def __init__(self, client: EnterpriseMCPClient | None = None) -> None:
        self.client = client or EnterpriseMCPClient()

    async def execute(self, arguments: MCPPolicyArgs, context: ToolContext) -> dict:
        try:
            return await self.client.call_tool(
                "get_company_policy", {"topic": arguments.topic}
            )
        except Exception as exc:
            raise ToolExecutionFailure(
                "mcp_unavailable",
                "Enterprise Tools MCP server is unavailable",
                retryable=True,
            ) from exc
