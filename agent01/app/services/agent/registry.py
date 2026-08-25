from __future__ import annotations

from concurrent.futures import (
    ThreadPoolExecutor,
    TimeoutError as FutureTimeoutError,
)
from dataclasses import dataclass, replace
from time import perf_counter
from typing import Callable

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    KnowledgeBaseNotFoundError,
    UpstreamServiceError,
    UpstreamTimeoutError,
)
from app.core.security import AuthenticatedUser
from app.schemas.agent import (
    ToolCall,
    ToolError,
    ToolName,
    ToolResult,
    ToolStatus,
)


@dataclass(frozen=True)
class ToolExecutionContext:
    session: Session
    current_user: AuthenticatedUser
    allowed_knowledge_base_id: str
    request_id: str
    session_factory: Callable[[], Session] | None = None


@dataclass(frozen=True)
class ToolExecutionPayload:
    output: dict
    result_summary: str


class AgentToolFailure(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


ToolHandler = Callable[
    [BaseModel, ToolExecutionContext],
    ToolExecutionPayload,
]


@dataclass(frozen=True)
class ToolDefinition:
    name: ToolName
    description: str
    arguments_model: type[BaseModel]
    handler: ToolHandler


_TOOL_EXECUTOR = ThreadPoolExecutor(
    max_workers=4,
    thread_name_prefix="bounded-agent-tool",
)


class ToolRegistry:
    def __init__(
        self,
        definitions: list[ToolDefinition] | None = None,
    ) -> None:
        self._definitions: dict[
            ToolName,
            ToolDefinition,
        ] = {}
        for definition in definitions or []:
            self.register(definition)

    @property
    def names(self) -> tuple[ToolName, ...]:
        return tuple(self._definitions)

    def register(
        self,
        definition: ToolDefinition,
    ) -> None:
        if definition.name in self._definitions:
            raise ValueError(
                f"Tool already registered: {definition.name.value}"
            )
        self._definitions[definition.name] = definition

    def execute(
        self,
        call: ToolCall,
        context: ToolExecutionContext,
        timeout_seconds: float,
    ) -> ToolResult:
        started_at = perf_counter()
        definition = self._definitions.get(
            call.tool_name
        )

        if definition is None:
            return self._failure_result(
                call,
                started_at,
                code="unknown_tool",
                message="工具未注册或不在白名单中",
            )

        try:
            arguments = definition.arguments_model.model_validate(
                call.arguments
            )
        except ValidationError:
            return self._failure_result(
                call,
                started_at,
                code="invalid_tool_arguments",
                message="工具参数未通过 schema 校验",
            )

        requested_knowledge_base_id = getattr(
            arguments,
            "knowledge_base_id",
            None,
        )
        if (
            requested_knowledge_base_id
            != context.allowed_knowledge_base_id
        ):
            return self._failure_result(
                call,
                started_at,
                code="knowledge_base_scope_mismatch",
                message="工具参数超出本次请求的知识库范围",
            )

        future = _TOOL_EXECUTOR.submit(
            self._invoke_handler,
            definition,
            arguments,
            context,
        )
        try:
            payload = future.result(
                timeout=timeout_seconds
            )
        except FutureTimeoutError:
            future.cancel()
            return self._failure_result(
                call,
                started_at,
                code="tool_timeout",
                message="工具执行超时，已停止本次 Agent 流程",
                retryable=True,
            )
        except KnowledgeBaseNotFoundError:
            return self._failure_result(
                call,
                started_at,
                code="resource_not_found",
                message="目标资源不存在或无权访问",
            )
        except UpstreamTimeoutError:
            return self._failure_result(
                call,
                started_at,
                code="upstream_timeout",
                message="模型服务响应超时，请稍后重试",
                retryable=True,
            )
        except UpstreamServiceError:
            return self._failure_result(
                call,
                started_at,
                code="upstream_service_error",
                message="模型服务暂时不可用，请稍后重试",
                retryable=True,
            )
        except AgentToolFailure as exc:
            return self._failure_result(
                call,
                started_at,
                code=exc.code,
                message=exc.message,
                retryable=exc.retryable,
            )
        except Exception:
            return self._failure_result(
                call,
                started_at,
                code="tool_execution_failed",
                message="工具执行失败，请稍后重试",
            )

        return ToolResult(
            call_id=call.call_id,
            tool_name=call.tool_name,
            status=ToolStatus.SUCCEEDED,
            duration_ms=self._duration_ms(started_at),
            result_summary=payload.result_summary,
            output=payload.output,
        )

    @staticmethod
    def _invoke_handler(
        definition: ToolDefinition,
        arguments: BaseModel,
        context: ToolExecutionContext,
    ) -> ToolExecutionPayload:
        if context.session_factory is None:
            return definition.handler(
                arguments,
                context,
            )

        with context.session_factory() as session:
            worker_context = replace(
                context,
                session=session,
                session_factory=None,
            )
            return definition.handler(
                arguments,
                worker_context,
            )

    @staticmethod
    def _duration_ms(started_at: float) -> float:
        return round(
            (perf_counter() - started_at) * 1000,
            2,
        )

    def _failure_result(
        self,
        call: ToolCall,
        started_at: float,
        *,
        code: str,
        message: str,
        retryable: bool = False,
    ) -> ToolResult:
        return ToolResult(
            call_id=call.call_id,
            tool_name=call.tool_name,
            status=ToolStatus.FAILED,
            duration_ms=self._duration_ms(started_at),
            result_summary=code,
            error=ToolError(
                code=code,
                message=message,
                retryable=retryable,
            ),
        )
