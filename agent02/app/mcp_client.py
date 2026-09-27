from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


class EnterpriseMCPClient:
    def __init__(self, *, project_root: Path | None = None) -> None:
        self.project_root = project_root or Path(__file__).resolve().parents[1]

    def _parameters(self) -> StdioServerParameters:
        return StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp_server"],
            cwd=self.project_root,
        )

    async def list_tools(self) -> list[str]:
        async with stdio_client(self._parameters()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                response = await session.list_tools()
                return [tool.name for tool in response.tools]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        async with stdio_client(self._parameters()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments)
                if result.isError:
                    message = next(
                        (
                            item.text
                            for item in result.content
                            if getattr(item, "type", None) == "text"
                        ),
                        "MCP tool failed",
                    )
                    raise RuntimeError(message)
                if result.structuredContent:
                    structured = dict(result.structuredContent)
                    return dict(structured.get("result", structured))
                for item in result.content:
                    text = getattr(item, "text", None)
                    if text:
                        parsed = json.loads(text)
                        return dict(parsed.get("result", parsed))
                return {}
