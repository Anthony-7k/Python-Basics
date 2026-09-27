from __future__ import annotations

from app.config import Settings
from app.tools.base import ToolRegistry
from app.tools.knowledge import (
    Agent01HttpKnowledgeBackend,
    FallbackKnowledgeBackend,
    KnowledgeTool,
    SampleKnowledgeBackend,
)
from app.tools.mcp_tool import MCPCompanyPolicyTool
from app.tools.standard import (
    CalculatorTool,
    CalendarTool,
    FailureTool,
    SearchTool,
    TaskTool,
)


def build_tool_registry(settings: Settings) -> ToolRegistry:
    sample = SampleKnowledgeBackend()
    if (
        settings.knowledge_backend == "agent01"
        and settings.agent01_bearer_token
        and settings.agent01_knowledge_base_id
    ):
        primary = Agent01HttpKnowledgeBackend(
            settings.agent01_base_url,
            settings.agent01_bearer_token.get_secret_value(),
            settings.agent01_knowledge_base_id,
            timeout_seconds=settings.tool_timeout_seconds,
        )
        backend = (
            FallbackKnowledgeBackend(primary, sample)
            if settings.knowledge_fallback_to_sample
            else primary
        )
    else:
        backend = sample
    return ToolRegistry(
        [
            KnowledgeTool(backend),
            CalculatorTool(),
            SearchTool(),
            CalendarTool(),
            TaskTool(),
            FailureTool(),
            MCPCompanyPolicyTool(),
        ]
    )
