from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Protocol

from app.config import Settings
from app.domain import TokenUsage, ToolCall
from app.llm import LLMProvider, LLMProviderError, OpenAICompatibleProvider

_ARABIC_DURATION = re.compile(r"(\d+)\s*(?:天|日)")
_CHINESE_DURATION = re.compile(r"([一二三四五六七八九十]{1,3})\s*(?:天|日)")
_ISO_DATE = re.compile(r"(20\d{2}-\d{2}-\d{2})")
_TASK_CREATION_MARKERS = (
    "创建任务",
    "创建提醒",
    "新增任务",
    "新建任务",
    "新建提醒",
    "添加任务",
)
_CHINESE_DIGITS = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


def extract_duration_days(message: str) -> int | None:
    """Extract a bounded trip duration from Arabic or common Chinese numerals."""

    match = _ARABIC_DURATION.search(message)
    if match:
        return max(1, min(int(match.group(1)), 60))

    match = _CHINESE_DURATION.search(message)
    if not match:
        return None
    value = match.group(1)
    if value == "十":
        number = 10
    elif "十" in value:
        tens, ones = value.split("十", 1)
        number = _CHINESE_DIGITS.get(tens, 1) * 10 + _CHINESE_DIGITS.get(ones, 0)
    else:
        number = _CHINESE_DIGITS.get(value, 0)
    return max(1, min(number, 60)) if number else None


def travel_total_request_days(message: str) -> int | None:
    """Return trip days when the request requires a policy-backed total."""

    has_travel_context = any(word in message for word in ("差旅", "报销", "出差"))
    has_total_intent = any(
        word in message for word in ("计算", "合计", "总额", "总计", "最高", "上限")
    )
    if not has_travel_context or not has_total_intent:
        return None
    return extract_duration_days(message)


def task_creation_arguments(message: str) -> dict[str, Any] | None:
    """Build safe task arguments for an explicit task/reminder creation request."""

    text = message.strip()
    marker = next((item for item in _TASK_CREATION_MARKERS if item in text), None)
    if marker is None:
        return None

    title = text.split(marker, 1)[1].lstrip("：:，, \t") or text
    due = _ISO_DATE.search(text)
    return {
        "action": "create",
        "title": title[:200],
        "due_date": due.group(1) if due else None,
    }


@dataclass
class PlannerResult:
    tool_calls: list[ToolCall] = field(default_factory=list)
    direct_answer: str = ""
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    provider: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    estimated_cost_usd: float | None = None


class Planner(Protocol):
    async def plan(
        self, message: str, tool_schemas: list[dict[str, Any]]
    ) -> PlannerResult: ...


class RuleBasedPlanner:
    """Deterministic planner for repeatable local demos and evaluation."""

    _number = re.compile(r"(-?\d+(?:\.\d+)?)")
    _date = re.compile(r"(20\d{2}-\d{2}-\d{2})")

    async def plan(
        self, message: str, tool_schemas: list[dict[str, Any]]
    ) -> PlannerResult:
        text = message.strip()
        lowered = text.lower()

        if "mcp" in lowered:
            return PlannerResult(
                tool_calls=[
                    ToolCall(
                        name="mcp_company_policy",
                        arguments={"topic": text},
                        selection_reason="The request explicitly asks for the MCP integration",
                    )
                ]
            )

        if "故障" in text or "failure" in lowered:
            return PlannerResult(
                tool_calls=[
                    ToolCall(
                        name="failure_demo",
                        arguments={"failures_before_success": 1, "delay_seconds": 0},
                        selection_reason="Demonstrate bounded retry and recovery",
                    )
                ]
            )

        task_arguments = task_creation_arguments(text)
        if task_arguments is not None:
            return PlannerResult(
                tool_calls=[
                    ToolCall(
                        name="task",
                        arguments=task_arguments,
                        selection_reason="A write operation requires the task tool",
                    )
                ]
            )

        if "差旅" in text or "报销" in text or "出差" in text:
            days = self._extract_days(text, default=3)
            calls = [
                ToolCall(
                    name="knowledge",
                    arguments={"query": text, "top_k": 5},
                    selection_reason="Travel limits are enterprise policy knowledge",
                )
            ]
            if "计算" in text or "最高" in text or "合计" in text:
                calls.append(
                    ToolCall(
                        name="calculator",
                        arguments={
                            "operation": "multiply",
                            "left": "$tool.knowledge.facts.daily_total_limit",
                            "right": days,
                        },
                        selection_reason="Multiply the retrieved daily limit by trip days",
                    )
                )
            return PlannerResult(tool_calls=calls)

        if ("年假" in text or "休假" in text) and any(
            word in text for word in ("方案", "安排", "日期")
        ):
            days = self._extract_days(text, default=3)
            start = self._date.search(text)
            return PlannerResult(
                tool_calls=[
                    ToolCall(
                        name="knowledge",
                        arguments={"query": text, "top_k": 5},
                        selection_reason="Retrieve the annual leave policy",
                    ),
                    ToolCall(
                        name="calendar",
                        arguments={
                            "start_date": start.group(1)
                            if start
                            else date.today().isoformat(),
                            "workdays": days,
                        },
                        selection_reason="Generate working dates for the leave plan",
                    ),
                ]
            )

        if "年假" in text or "公司制度" in text or "公司政策" in text:
            return PlannerResult(
                tool_calls=[
                    ToolCall(
                        name="knowledge",
                        arguments={"query": text, "top_k": 5},
                        selection_reason="The request asks for enterprise policy knowledge",
                    )
                ]
            )

        if any(word in lowered for word in ("search", "web")) or "搜索" in text:
            return PlannerResult(
                tool_calls=[
                    ToolCall(
                        name="search",
                        arguments={"query": text},
                        selection_reason="The request asks for public information",
                    )
                ]
            )

        if any(word in text for word in ("计算", "乘以", "相加", "除以")):
            numbers = [Decimal(item) for item in self._number.findall(text)]
            if len(numbers) >= 2:
                operation = "multiply"
                if "相加" in text or "+" in text:
                    operation = "add"
                elif "除以" in text or "/" in text:
                    operation = "divide"
                elif "减" in text or "-" in text:
                    operation = "subtract"
                return PlannerResult(
                    tool_calls=[
                        ToolCall(
                            name="calculator",
                            arguments={
                                "operation": operation,
                                "left": str(numbers[0]),
                                "right": str(numbers[1]),
                            },
                            selection_reason="The request is a deterministic calculation",
                        )
                    ]
                )

        return PlannerResult(
            direct_answer="当前可用工具无法可靠完成该请求，请补充企业制度、计算、日期或任务操作信息。"
        )

    def _extract_days(self, text: str, *, default: int) -> int:
        return extract_duration_days(text) or default


class OpenAICompatiblePlanner:
    prompt_version = "planner-v2"

    def __init__(self, settings: Settings, provider: LLMProvider | None = None) -> None:
        self.provider = provider or OpenAICompatibleProvider(settings)
        self.model = settings.llm_model
        self.input_cost = settings.llm_input_cost_per_million
        self.output_cost = settings.llm_output_cost_per_million

    async def plan(
        self, message: str, tool_schemas: list[dict[str, Any]]
    ) -> PlannerResult:
        response = await self.provider.complete(
            message=message,
            tools=tool_schemas,
        )
        calls = []
        call_ids: set[str] = set()
        for item in response.tool_calls:
            if item.call_id in call_ids:
                raise LLMProviderError(
                    "invalid_model_response",
                    "Model returned duplicate tool call identifiers",
                    retryable=False,
                    provider=response.provider,
                    model=response.model,
                )
            call_ids.add(item.call_id)
            try:
                arguments = json.loads(item.arguments_json or "{}")
            except json.JSONDecodeError as exc:
                raise LLMProviderError(
                    "invalid_model_response",
                    "Model returned invalid tool arguments JSON",
                    retryable=False,
                    provider=response.provider,
                    model=response.model,
                ) from exc
            if not isinstance(arguments, dict):
                raise LLMProviderError(
                    "invalid_model_response",
                    "Model tool arguments must be a JSON object",
                    retryable=False,
                    provider=response.provider,
                    model=response.model,
                )
            calls.append(
                ToolCall(
                    call_id=item.call_id,
                    name=item.name,
                    arguments=arguments,
                    selection_reason="Selected by the configured LLM",
                )
            )
        calls = self._apply_deterministic_guardrails(message, tool_schemas, calls)
        return PlannerResult(
            tool_calls=calls,
            direct_answer=response.content,
            token_usage=response.usage,
            provider=response.provider,
            model=response.model,
            prompt_version=self.prompt_version,
            estimated_cost_usd=self._estimate_cost(response.usage),
        )

    @staticmethod
    def _apply_deterministic_guardrails(
        message: str,
        tool_schemas: list[dict[str, Any]],
        calls: list[ToolCall],
    ) -> list[ToolCall]:
        available_tools = {
            item.get("function", {}).get("name") for item in tool_schemas
        }
        task_arguments = task_creation_arguments(message)
        if task_arguments is not None:
            if "task" not in available_tools:
                raise LLMProviderError(
                    "required_tool_unavailable",
                    "Task creation requires the unavailable approval-gated task tool",
                    retryable=False,
                )
            return [
                ToolCall(
                    name="task",
                    arguments=task_arguments,
                    selection_reason=(
                        "Deterministic guardrail: explicit task creation requires "
                        "the approval-gated task tool"
                    ),
                )
            ]

        days = travel_total_request_days(message)
        if days is None:
            return calls

        required_tools = {"knowledge", "calculator"}
        if not required_tools.issubset(available_tools):
            missing = ", ".join(sorted(required_tools - available_tools))
            raise LLMProviderError(
                "required_tool_unavailable",
                f"Travel total calculation requires unavailable tools: {missing}",
                retryable=False,
            )

        return [
            ToolCall(
                name="knowledge",
                arguments={"query": message, "top_k": 5},
                selection_reason=(
                    "Deterministic guardrail: retrieve the applicable travel policy"
                ),
            ),
            ToolCall(
                name="calculator",
                arguments={
                    "operation": "multiply",
                    "left": "$tool.knowledge.facts.daily_total_limit",
                    "right": days,
                },
                selection_reason=(
                    "Deterministic guardrail: multiply the retrieved daily limit "
                    "by the requested trip duration"
                ),
            ),
        ]

    def _estimate_cost(self, usage: TokenUsage) -> float | None:
        if (
            self.input_cost is None
            or self.output_cost is None
            or usage.input_tokens is None
            or usage.output_tokens is None
        ):
            return None
        return round(
            (
                usage.input_tokens * self.input_cost
                + usage.output_tokens * self.output_cost
            )
            / 1_000_000,
            8,
        )


class HybridPlanner:
    def __init__(self, settings: Settings) -> None:
        self.planner: Planner = (
            OpenAICompatiblePlanner(settings)
            if settings.planner_mode == "openai"
            else RuleBasedPlanner()
        )

    async def plan(
        self, message: str, tool_schemas: list[dict[str, Any]]
    ) -> PlannerResult:
        return await self.planner.plan(message, tool_schemas)
