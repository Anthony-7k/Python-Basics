from __future__ import annotations

from collections.abc import Awaitable, Callable
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from time import perf_counter
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agent.planner import (
    Planner,
    task_creation_arguments,
    travel_total_request_days,
)
from app.config import Settings
from app.domain import (
    RiskLevel,
    TaskStatus,
    ToolCall,
    ToolError,
    ToolResult,
    WorkflowState,
)
from app.llm import LLMProviderError
from app.logging_config import get_logger
from app.memory import MemoryService
from app.observability import metrics
from app.repositories import CheckpointRepository, LLMCallRepository, TaskRepository
from app.tools import ToolContext, ToolRegistry

logger = get_logger(__name__)
EventSink = Callable[[str, dict[str, Any]], Awaitable[None]]


class AgentWorkflow:
    def __init__(
        self,
        *,
        settings: Settings,
        planner: Planner,
        registry: ToolRegistry,
        tasks: TaskRepository,
        checkpoints: CheckpointRepository,
        llm_calls: LLMCallRepository,
        memory: MemoryService,
        event_sink: EventSink | None = None,
    ) -> None:
        self.settings = settings
        self.planner = planner
        self.registry = registry
        self.tasks = tasks
        self.checkpoints = checkpoints
        self.llm_calls = llm_calls
        self.memory = memory
        self.event_sink = event_sink
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(WorkflowState)
        builder.add_node("agent", self._agent_node)
        builder.add_node("tool", self._tool_node)
        builder.add_node("approval", self._approval_node)
        builder.add_node("finish", self._finish_node)
        builder.add_edge(START, "agent")
        builder.add_conditional_edges(
            "agent", self._route, {"tool": "tool", "finish": "finish"}
        )
        builder.add_conditional_edges(
            "tool",
            self._route,
            {"tool": "tool", "approval": "approval", "finish": "finish"},
        )
        builder.add_edge("approval", END)
        builder.add_edge("finish", END)
        return builder.compile()

    async def run(self, state: WorkflowState) -> WorkflowState:
        return await self.graph.ainvoke(state)

    def _route(self, state: WorkflowState) -> str:
        return state.get("next_action", "finish")

    async def _agent_node(self, state: WorkflowState) -> WorkflowState:
        state = deepcopy(state)
        planner_latency_ms = 0.0
        if state.get("resume_approved") or state.get("resume_from_checkpoint"):
            state["resume_approved"] = False
            state["resume_from_checkpoint"] = False
            state["status"] = TaskStatus.RUNNING.value
            state["error"] = None
            state["next_action"] = "tool"
        else:
            state["status"] = TaskStatus.RUNNING.value
            message = state["messages"][-1]["content"]
            await self._emit(
                "planning",
                state,
                {"step": state.get("current_step", 0)},
            )
            planner_started = perf_counter()
            try:
                result = await self.planner.plan(message, self.registry.schemas())
            except LLMProviderError as exc:
                planner_latency_ms = (perf_counter() - planner_started) * 1000
                self.llm_calls.record(
                    tenant_id=state["tenant_id"],
                    task_id=state["task_id"],
                    provider=exc.provider,
                    model=exc.model or self.settings.llm_model,
                    prompt_version="planner-v2",
                    input_tokens=None,
                    output_tokens=None,
                    estimated_cost_usd=None,
                    latency_ms=planner_latency_ms,
                    error_type=exc.error_type,
                )
                metrics.observe_llm(
                    exc.provider,
                    exc.model or self.settings.llm_model,
                    planner_latency_ms,
                    input_tokens=None,
                    output_tokens=None,
                    cost_usd=None,
                    error_type=exc.error_type,
                )
                state["status"] = TaskStatus.FAILED.value
                state["error"] = ToolError(
                    error_type=exc.error_type,
                    message=exc.message,
                    retryable=exc.retryable,
                ).model_dump(mode="json")
                state["answer"] = "模型服务暂时无法完成请求。"
                state["next_action"] = "finish"
                self.tasks.add_step(
                    state["task_id"],
                    state["tenant_id"],
                    state.get("current_step", 0),
                    "agent",
                    state["status"],
                    {"error_type": exc.error_type},
                )
                self._persist(state, "finish")
                return state
            planner_latency_ms = (perf_counter() - planner_started) * 1000
            state["planned_calls"] = [
                call.model_dump(mode="json") for call in result.tool_calls
            ]
            state["token_usage"] = result.token_usage.model_dump(mode="json")
            state["answer"] = result.direct_answer
            state["next_action"] = "tool" if result.tool_calls else "finish"
            if result.provider:
                self.llm_calls.record(
                    tenant_id=state["tenant_id"],
                    task_id=state["task_id"],
                    provider=result.provider,
                    model=result.model or self.settings.llm_model,
                    prompt_version=result.prompt_version or "unknown",
                    input_tokens=result.token_usage.input_tokens,
                    output_tokens=result.token_usage.output_tokens,
                    estimated_cost_usd=result.estimated_cost_usd,
                    latency_ms=planner_latency_ms,
                )
                metrics.observe_llm(
                    result.provider,
                    result.model or self.settings.llm_model,
                    planner_latency_ms,
                    input_tokens=result.token_usage.input_tokens,
                    output_tokens=result.token_usage.output_tokens,
                    cost_usd=result.estimated_cost_usd,
                )
        self.tasks.add_step(
            state["task_id"],
            state["tenant_id"],
            state.get("current_step", 0),
            "agent",
            state["status"],
            {"next_action": state["next_action"]},
        )
        self._persist(state, state["next_action"])
        usage = state.get("token_usage") or {}
        self._log(
            "agent_planner",
            state,
            llm_latency_ms=round(planner_latency_ms, 3),
            token_input=usage.get("input_tokens"),
            token_output=usage.get("output_tokens"),
        )
        return state

    async def _tool_node(self, state: WorkflowState) -> WorkflowState:
        state = deepcopy(state)
        step = state.get("current_step", 0)
        calls = state.get("planned_calls", [])
        if step >= state.get("max_steps", self.settings.agent_max_steps):
            state["status"] = TaskStatus.FAILED.value
            limit_error = ToolError(
                error_type="max_steps_exceeded",
                message="Agent exceeded the configured step limit",
            )
            state["error"] = limit_error.model_dump(mode="json")
            state["answer"] = limit_error.message
            state["next_action"] = "finish"
            self._persist(state, "finish")
            return state
        if step >= len(calls):
            state["next_action"] = "finish"
            return state

        call = ToolCall.model_validate(calls[step])
        tool = self.registry.get(call.name)
        if tool and tool.risk_level == RiskLevel.HIGH_RISK:
            if state.get("approved_call_id") != call.call_id:
                state["pending_call"] = call.model_dump(mode="json")
                state["status"] = TaskStatus.WAITING_APPROVAL.value
                state["next_action"] = "approval"
                self._persist(state, "approval")
                self._log("approval_required", state, tool_name=call.name)
                await self._emit(
                    "approval_required",
                    state,
                    {
                        "risk_level": tool.risk_level.value,
                        "tool_name": call.name,
                        "payload": call.arguments,
                    },
                )
                return state

        try:
            call.arguments = self._resolve_references(
                call.arguments, state.get("tool_results", [])
            )
        except (KeyError, ValueError) as exc:
            result = ToolResult(
                call_id=call.call_id,
                tool_name=call.name,
                success=False,
                error=ToolError(
                    error_type="reference_resolution_failed",
                    message=str(exc),
                    retryable=False,
                ),
            )
        else:
            state["status"] = TaskStatus.WAITING_TOOL.value
            self._persist(state, "tool")
            await self._emit(
                "tool_started",
                state,
                {"tool_name": call.name, "call_id": call.call_id},
            )
            context = ToolContext(
                user_id=state["user_id"],
                tenant_id=state["tenant_id"],
                session_id=state["session_id"],
                task_id=state["task_id"],
                request_id=state["request_id"],
                knowledge_base_id=state.get("knowledge_base_id"),
                idempotency_key=f"{state['task_id']}:{call.call_id}",
            )
            result = await self.registry.execute(
                call,
                context,
                timeout_seconds=self.settings.tool_timeout_seconds,
                max_retries=self.settings.tool_max_retries,
            )

        results = list(state.get("tool_results", []))
        results.append(result.model_dump(mode="json"))
        state["tool_results"] = results
        self.tasks.save_tool_call(state["task_id"], state["tenant_id"], call, result)
        metrics.observe_tool(
            call.name,
            result.success,
            result.retry_count,
            result.latency_ms,
        )
        await self._emit(
            "tool_finished",
            state,
            {
                "tool_name": call.name,
                "call_id": call.call_id,
                "success": result.success,
                "latency_ms": result.latency_ms,
                "retry_count": result.retry_count,
            },
        )
        if not result.success:
            state["error"] = (
                result.error.model_dump(mode="json") if result.error else None
            )
            state["answer"] = (
                result.error.message if result.error else "Tool execution failed"
            )
            state["status"] = (
                TaskStatus.TIMEOUT.value
                if result.error and result.error.error_type == "tool_timeout"
                else TaskStatus.FAILED.value
            )
            state["next_action"] = "finish"
        else:
            state["current_step"] = step + 1
            state["approved_call_id"] = None
            state["pending_call"] = None
            state["status"] = TaskStatus.RUNNING.value
            state["next_action"] = (
                "tool" if state["current_step"] < len(calls) else "finish"
            )
        self.tasks.add_step(
            state["task_id"],
            state["tenant_id"],
            state.get("current_step", step),
            "tool",
            state["status"],
            {
                "tool_name": call.name,
                "success": result.success,
                "retry_count": result.retry_count,
                "latency_ms": result.latency_ms,
            },
        )
        self._persist(state, state["next_action"])
        self._log(
            "tool_result",
            state,
            tool_name=call.name,
            success=result.success,
            retry_count=result.retry_count,
            tool_latency_ms=round(result.latency_ms, 3),
        )
        return state

    async def _approval_node(self, state: WorkflowState) -> WorkflowState:
        state = deepcopy(state)
        self.tasks.add_step(
            state["task_id"],
            state["tenant_id"],
            state.get("current_step", 0),
            "approval",
            TaskStatus.WAITING_APPROVAL.value,
        )
        self._persist(state, "approval")
        return state

    async def _finish_node(self, state: WorkflowState) -> WorkflowState:
        state = deepcopy(state)
        if state.get("status") not in {
            TaskStatus.FAILED.value,
            TaskStatus.TIMEOUT.value,
        }:
            completion_error = self._validate_completion(state)
            if completion_error:
                state["status"] = TaskStatus.FAILED.value
                state["error"] = completion_error.model_dump(mode="json")
                state["answer"] = completion_error.message
            else:
                state["status"] = TaskStatus.COMPLETED.value
                state["answer"] = self._compose_answer(state)
        state["sources"] = [
            source
            for result in state.get("tool_results", [])
            for source in result.get("sources", [])
        ]
        state["next_action"] = "finish"
        self.memory.save_session_state(state)
        self.memory.consider_long_term(
            state["user_id"],
            state["messages"][-1]["content"],
            tenant_id=state["tenant_id"],
        )
        self.tasks.add_step(
            state["task_id"],
            state["tenant_id"],
            state.get("current_step", 0),
            "finish",
            state["status"],
        )
        self._persist(state, "finish")
        metrics.observe_task(state["status"])
        usage = state.get("token_usage") or {}
        self._log(
            "agent_finish",
            state,
            steps=state.get("current_step", 0),
            tool_calls=len(state.get("tool_results", [])),
            retry_count=sum(
                item.get("retry_count", 0) for item in state.get("tool_results", [])
            ),
            token_input=usage.get("input_tokens"),
            token_output=usage.get("output_tokens"),
        )
        event_name = (
            "completed" if state["status"] == TaskStatus.COMPLETED.value else "failed"
        )
        await self._emit(
            event_name,
            state,
            {
                "answer": state.get("answer", ""),
                "sources": state.get("sources", []),
                "usage": state.get("token_usage", {}),
                "error": state.get("error"),
            },
        )
        return state

    def _persist(self, state: WorkflowState, next_node: str) -> None:
        self.tasks.update_from_state(state)
        self.checkpoints.save(state, next_node)

    def _log(self, event: str, state: WorkflowState, **extra: Any) -> None:
        logger.info(
            event,
            extra={
                "event": event,
                "request_id": state.get("request_id"),
                "task_id": state.get("task_id"),
                "session_id": state.get("session_id"),
                "tenant_id": state.get("tenant_id"),
                "current_step": state.get("current_step"),
                "status": state.get("status"),
                **extra,
            },
        )

    async def _emit(
        self,
        event: str,
        state: WorkflowState,
        payload: dict[str, Any],
    ) -> None:
        if self.event_sink is None:
            return
        await self.event_sink(
            event,
            {
                "task_id": state.get("task_id"),
                "request_id": state.get("request_id"),
                **payload,
            },
        )

    def _resolve_references(self, value: Any, results: list[dict[str, Any]]) -> Any:
        if isinstance(value, dict):
            return {
                key: self._resolve_references(item, results)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._resolve_references(item, results) for item in value]
        if not isinstance(value, str) or not value.startswith("$tool."):
            return value
        parts = value.split(".")
        if len(parts) < 3:
            raise ValueError(f"Invalid tool reference: {value}")
        tool_name = parts[1]
        matching = [item for item in results if item.get("tool_name") == tool_name]
        if not matching:
            raise KeyError(f"No result is available for tool {tool_name}")
        current: Any = matching[-1].get("data", {})
        for part in parts[2:]:
            if not isinstance(current, dict) or part not in current:
                raise KeyError(f"Missing path in tool result: {value}")
            current = current[part]
        return current

    def _compose_answer(self, state: WorkflowState) -> str:
        results = state.get("tool_results", [])
        if not results:
            return state.get("answer", "")
        by_name = {item["tool_name"]: item for item in results if item.get("success")}
        if "calculator" in by_name and "knowledge" in by_name:
            value = by_name["calculator"]["data"].get("result")
            message = state["messages"][-1]["content"]
            days = travel_total_request_days(message)
            knowledge_data = by_name["knowledge"]["data"]
            daily_limit = knowledge_data.get("facts", {}).get("daily_total_limit")
            if days is not None and daily_limit is not None:
                policy = knowledge_data.get("answer", "根据企业差旅标准")
                return (
                    f"{policy} 按 {days} 天计算，最高报销金额为 "
                    f"{daily_limit} × {days} = {value} 元。"
                )
            return f"根据企业差旅标准，计算结果为 {value} 元。"
        if "calendar" in by_name and "knowledge" in by_name:
            dates = by_name["calendar"]["data"].get("workdays", [])
            policy = by_name["knowledge"]["data"].get("answer", "")
            return f"{policy} 建议休假日期：{'、'.join(dates)}。"
        for name in (
            "task",
            "failure_demo",
            "knowledge",
            "mcp_company_policy",
            "search",
        ):
            if name in by_name:
                data = by_name[name]["data"]
                if name == "task":
                    return f"任务已创建：{data.get('title', '')}"
                return str(data.get("answer", data))
        return str(results[-1].get("data", {}))

    def _validate_completion(self, state: WorkflowState) -> ToolError | None:
        message = state["messages"][-1]["content"]
        successful = {
            item["tool_name"]: item
            for item in state.get("tool_results", [])
            if item.get("success")
        }
        if task_creation_arguments(message) is not None and "task" not in successful:
            return ToolError(
                error_type="incomplete_tool_plan",
                message="请求要求创建任务，但未执行需要人工审批的任务创建步骤。",
                retryable=False,
            )

        days = travel_total_request_days(message)
        if days is None:
            return None

        if "knowledge" not in successful or "calculator" not in successful:
            return ToolError(
                error_type="incomplete_tool_plan",
                message=(
                    f"请求需要计算 {days} 天差旅总额，但未完成制度查询和计算步骤。"
                ),
                retryable=False,
            )

        knowledge_data = successful["knowledge"].get("data", {})
        calculator_data = successful["calculator"].get("data", {})
        daily_limit = knowledge_data.get("facts", {}).get("daily_total_limit")
        total = calculator_data.get("result")
        try:
            expected = Decimal(str(daily_limit)) * Decimal(days)
            actual = Decimal(str(total))
        except (InvalidOperation, TypeError, ValueError):
            return ToolError(
                error_type="answer_validation_failed",
                message="差旅总额缺少可验证的单日标准或计算结果。",
                retryable=False,
            )
        if actual != expected:
            return ToolError(
                error_type="answer_validation_failed",
                message="差旅总额计算结果与制度中的单日标准不一致。",
                retryable=False,
            )
        return None
