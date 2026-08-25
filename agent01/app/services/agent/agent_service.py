from __future__ import annotations

from time import perf_counter

from sqlalchemy.orm import Session, sessionmaker

from app.core.logging_config import get_logger
from app.core.security import AuthenticatedUser
from app.core.settings import (
    AGENT_MAX_TOOL_STEPS,
    AGENT_REQUEST_BUDGET_SECONDS,
    AGENT_TOOL_TIMEOUT_SECONDS,
)
from app.schemas.agent import (
    AgentRequest,
    AgentResponse,
    AgentStatus,
    AgentTrace,
    ToolError,
    ToolStatus,
)
from app.services.agent.registry import (
    ToolExecutionContext,
    ToolRegistry,
)
from app.services.agent.router import (
    DeterministicAgentRouter,
)
from app.services.agent.tools import (
    build_default_tool_registry,
)


logger = get_logger(__name__)


class BoundedAgentService:
    def __init__(
        self,
        session: Session,
        current_user: AuthenticatedUser,
        *,
        registry: ToolRegistry | None = None,
        router: DeterministicAgentRouter | None = None,
        max_steps: int = AGENT_MAX_TOOL_STEPS,
        tool_timeout_seconds: float = (
            AGENT_TOOL_TIMEOUT_SECONDS
        ),
        request_budget_seconds: float = (
            AGENT_REQUEST_BUDGET_SECONDS
        ),
    ) -> None:
        self.session = session
        self.current_user = current_user
        self.registry = (
            registry or build_default_tool_registry()
        )
        self.router = (
            router or DeterministicAgentRouter()
        )
        self.max_steps = max_steps
        self.tool_timeout_seconds = (
            tool_timeout_seconds
        )
        self.request_budget_seconds = (
            request_budget_seconds
        )
        self.session_factory = (
            sessionmaker(
                bind=session.get_bind(),
                class_=Session,
                expire_on_commit=False,
            )
            if isinstance(session, Session)
            else None
        )

    def run(
        self,
        request: AgentRequest,
        request_id: str,
    ) -> AgentResponse:
        started_at = perf_counter()
        plan = self.router.route(request)

        if plan.status != AgentStatus.SUCCEEDED:
            return AgentResponse(
                status=plan.status,
                answer=plan.message,
                error=plan.error,
                trace=AgentTrace(
                    request_id=request_id,
                    step_count=0,
                    stop_reason=plan.status.value,
                ),
            )

        if len(plan.tool_calls) > self.max_steps:
            error = ToolError(
                code="step_limit_exceeded",
                message="Agent 工具步数超过配置上限",
            )
            return AgentResponse(
                status=AgentStatus.FAILED,
                answer=error.message,
                error=error,
                trace=AgentTrace(
                    request_id=request_id,
                    step_count=0,
                    stop_reason=error.code,
                    tool_calls=plan.tool_calls,
                ),
            )

        results = []
        answer = plan.message
        error = None
        stop_reason = "completed"

        context = ToolExecutionContext(
            session=self.session,
            current_user=self.current_user,
            allowed_knowledge_base_id=(
                request.knowledge_base_id
            ),
            request_id=request_id,
            session_factory=self.session_factory,
        )

        for call in plan.tool_calls:
            elapsed = perf_counter() - started_at
            remaining_budget = (
                self.request_budget_seconds - elapsed
            )
            if remaining_budget <= 0:
                error = ToolError(
                    code="request_budget_exceeded",
                    message="Agent 请求已超过总时间预算",
                )
                stop_reason = error.code
                break

            result = self.registry.execute(
                call,
                context,
                timeout_seconds=min(
                    self.tool_timeout_seconds,
                    remaining_budget,
                ),
            )
            results.append(result)
            self._log_result(
                request,
                call,
                result,
                request_id,
            )

            if result.status == ToolStatus.FAILED:
                error = result.error
                answer = (
                    result.error.message
                    if result.error is not None
                    else "工具执行失败"
                )
                stop_reason = (
                    result.error.code
                    if result.error is not None
                    else "tool_failed"
                )
                break

            answer = str(
                (result.output or {}).get(
                    "answer",
                    result.result_summary,
                )
            )

        status = (
            AgentStatus.FAILED
            if error is not None
            else AgentStatus.SUCCEEDED
        )
        return AgentResponse(
            status=status,
            answer=answer,
            error=error,
            trace=AgentTrace(
                request_id=request_id,
                step_count=len(results),
                stop_reason=stop_reason,
                tool_calls=plan.tool_calls,
                tool_results=results,
            ),
        )

    def _log_result(
        self,
        request: AgentRequest,
        call,
        result,
        request_id: str,
    ) -> None:
        resource_ids = {
            key: value
            for key, value in call.arguments.items()
            if key.endswith("_id")
        }
        logger.info(
            "agent tool call completed",
            extra={
                "event": "agent_tool_call",
                "request_id": request_id,
                "actor_id": self.current_user.audit_id,
                "knowledge_base_id": (
                    request.knowledge_base_id
                ),
                "tool_call_id": call.call_id,
                "tool_name": call.tool_name.value,
                "selection_reason_summary": (
                    call.selection_reason
                ),
                "resource_ids": resource_ids,
                "duration_ms": result.duration_ms,
                "status": result.status.value,
                "error_code": (
                    result.error.code
                    if result.error is not None
                    else None
                ),
                "result_summary": (
                    result.result_summary
                ),
            },
        )
