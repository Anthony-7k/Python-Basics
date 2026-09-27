from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from app.domain import RiskLevel, ToolCall, ToolError, ToolResult

ArgsT = TypeVar("ArgsT", bound=BaseModel)


class EmptyArgs(BaseModel):
    pass


@dataclass
class ToolContext:
    user_id: str
    session_id: str
    task_id: str
    request_id: str
    tenant_id: str = "legacy"
    knowledge_base_id: str | None = None
    idempotency_key: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolExecutionFailure(RuntimeError):
    def __init__(self, error_type: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.message = message
        self.retryable = retryable


class BaseTool(ABC, Generic[ArgsT]):
    name: str
    description: str
    risk_level: RiskLevel = RiskLevel.READ_ONLY
    args_model: type[ArgsT]

    def function_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_model.model_json_schema(),
            },
        }

    @abstractmethod
    async def execute(self, arguments: ArgsT, context: ToolContext) -> dict[str, Any]:
        raise NotImplementedError


class ToolRegistry:
    def __init__(self, tools: list[BaseTool[Any]] | None = None) -> None:
        self._tools: dict[str, BaseTool[Any]] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: BaseTool[Any]) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Duplicate tool name: {tool.name}")
        if not tool.name.strip():
            raise ValueError("Tool name must not be blank")
        tool.args_model.model_json_schema()
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool[Any] | None:
        return self._tools.get(name)

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.function_schema() for tool in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools)

    async def execute(
        self,
        call: ToolCall,
        context: ToolContext,
        *,
        timeout_seconds: float,
        max_retries: int,
    ) -> ToolResult:
        tool = self.get(call.name)
        if tool is None:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.name,
                success=False,
                error=ToolError(
                    error_type="unknown_tool",
                    message=f"Unknown tool: {call.name}",
                    retryable=False,
                ),
            )
        try:
            arguments = tool.args_model.model_validate(call.arguments)
        except ValidationError as exc:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.name,
                success=False,
                error=ToolError(
                    error_type="invalid_arguments",
                    message=str(exc),
                    retryable=False,
                ),
            )

        started = perf_counter()
        retry_count = 0
        while True:
            try:
                data = await asyncio.wait_for(
                    tool.execute(arguments, context), timeout=timeout_seconds
                )
                return ToolResult(
                    call_id=call.call_id,
                    tool_name=call.name,
                    success=True,
                    data=data,
                    sources=list(data.get("sources", [])),
                    latency_ms=(perf_counter() - started) * 1000,
                    retry_count=retry_count,
                )
            except TimeoutError:
                failure = ToolExecutionFailure(
                    "tool_timeout",
                    f"Tool exceeded {timeout_seconds:g} seconds",
                    retryable=True,
                )
            except ToolExecutionFailure as exc:
                failure = exc
            except Exception as exc:  # defensive boundary for third-party tools
                failure = ToolExecutionFailure(
                    "tool_execution_error", str(exc), retryable=False
                )

            if not failure.retryable or retry_count >= max_retries:
                return ToolResult(
                    call_id=call.call_id,
                    tool_name=call.name,
                    success=False,
                    error=ToolError(
                        error_type=failure.error_type,
                        message=failure.message,
                        retryable=failure.retryable,
                    ),
                    latency_ms=(perf_counter() - started) * 1000,
                    retry_count=retry_count,
                )
            retry_count += 1
            await asyncio.sleep(min(0.05 * (2 ** (retry_count - 1)), 0.2))
