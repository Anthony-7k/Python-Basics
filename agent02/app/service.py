from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

from sqlalchemy.orm import Session

from app.agent.planner import HybridPlanner, Planner
from app.agent.workflow import AgentWorkflow, EventSink
from app.config import Settings
from app.domain import (
    AgentRequest,
    AgentResponse,
    AgentV2Request,
    TaskStatus,
    TaskView,
    TokenUsage,
    ToolCall,
    ToolError,
    ToolResult,
    WorkflowState,
)
from app.memory import MemoryService
from app.repositories import (
    CheckpointRepository,
    LLMCallRepository,
    MemoryRepository,
    TaskRepository,
)
from app.security.models import UserContext
from app.tools import ToolRegistry, build_tool_registry


class TaskNotFoundError(LookupError):
    pass


class TaskAccessError(PermissionError):
    pass


class InvalidTaskStateError(RuntimeError):
    pass


class AgentService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        *,
        registry: ToolRegistry | None = None,
        planner: Planner | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.tasks = TaskRepository(session)
        self.checkpoints = CheckpointRepository(session)
        self.memories = MemoryRepository(session)
        self.llm_calls = LLMCallRepository(session)
        self.registry = registry or build_tool_registry(settings)
        self.planner = planner or HybridPlanner(settings)

    def _workflow(self, event_sink: EventSink | None = None) -> AgentWorkflow:
        return AgentWorkflow(
            settings=self.settings,
            planner=self.planner,
            registry=self.registry,
            tasks=self.tasks,
            checkpoints=self.checkpoints,
            llm_calls=self.llm_calls,
            memory=MemoryService(self.memories),
            event_sink=event_sink,
        )

    async def run(self, request: AgentRequest, request_id: str) -> AgentResponse:
        return await self._run_common(
            message=request.message,
            session_id=request.session_id,
            knowledge_base_id=request.knowledge_base_id,
            max_steps=request.max_steps,
            identity=UserContext(
                subject=request.user_id,
                tenant_id="legacy",
                roles=frozenset({"operator"}),
            ),
            request_id=request_id,
        )

    async def run_as(
        self,
        request: AgentV2Request,
        identity: UserContext,
        request_id: str,
        event_sink: EventSink | None = None,
    ) -> AgentResponse:
        return await self._run_common(
            message=request.message,
            session_id=request.session_id,
            knowledge_base_id=request.knowledge_base_id,
            max_steps=request.max_steps,
            identity=identity,
            request_id=request_id,
            event_sink=event_sink,
        )

    async def _run_common(
        self,
        *,
        message: str,
        session_id: str,
        knowledge_base_id: str | None,
        max_steps: int | None,
        identity: UserContext,
        request_id: str,
        event_sink: EventSink | None = None,
    ) -> AgentResponse:
        task_id = str(uuid4())
        resolved_max_steps = max_steps or self.settings.agent_max_steps
        state: WorkflowState = {
            "messages": [{"role": "user", "content": message}],
            "user_id": identity.subject,
            "tenant_id": identity.tenant_id,
            "session_id": session_id,
            "task_id": task_id,
            "request_id": request_id,
            "knowledge_base_id": knowledge_base_id,
            "current_step": 0,
            "max_steps": resolved_max_steps,
            "planned_calls": [],
            "tool_results": [],
            "status": TaskStatus.CREATED.value,
            "error": None,
            "token_usage": TokenUsage().model_dump(mode="json"),
            "pending_call": None,
            "approved_call_id": None,
            "resume_approved": False,
            "resume_from_checkpoint": False,
            "next_action": "agent",
            "answer": "",
            "sources": [],
        }
        self.tasks.create(
            task_id=task_id,
            request_id=request_id,
            tenant_id=identity.tenant_id,
            created_by=identity.subject,
            user_id=identity.subject,
            session_id=session_id,
            knowledge_base_id=knowledge_base_id,
            message=message,
            max_steps=resolved_max_steps,
            state=state,
        )
        if event_sink:
            await event_sink(
                "task_created",
                {"task_id": task_id, "request_id": request_id},
            )
        final = await self._workflow(event_sink).run(state)
        return self._response(final)

    async def approve(
        self,
        task_id: str,
        user_id: str | None,
        modified_payload: dict | None = None,
        *,
        tenant_id: str | None = None,
    ) -> AgentResponse:
        record = self._require_task(task_id, user_id, tenant_id=tenant_id)
        if record.status != TaskStatus.WAITING_APPROVAL.value:
            raise InvalidTaskStateError("Task is not waiting for approval")
        checkpoint = self.checkpoints.latest(task_id, tenant_id)
        if checkpoint is None:
            raise InvalidTaskStateError("Task has no recoverable checkpoint")
        state = deepcopy(checkpoint.state_json)
        pending = state.get("pending_call")
        if not pending:
            raise InvalidTaskStateError("Pending tool call is missing")
        if modified_payload is not None:
            pending["arguments"] = modified_payload
            planned = state.get("planned_calls", [])
            planned[state.get("current_step", 0)] = pending
            state["planned_calls"] = planned
        state["approved_call_id"] = pending["call_id"]
        state["resume_approved"] = True
        state["status"] = TaskStatus.RUNNING.value
        final = await self._workflow().run(state)
        return self._response(final)

    def reject(
        self,
        task_id: str,
        user_id: str | None,
        reason: str,
        *,
        tenant_id: str | None = None,
    ) -> AgentResponse:
        record = self._require_task(task_id, user_id, tenant_id=tenant_id)
        if record.status != TaskStatus.WAITING_APPROVAL.value:
            raise InvalidTaskStateError("Task is not waiting for approval")
        state = deepcopy(record.state_json)
        state["status"] = TaskStatus.FAILED.value
        state["error"] = ToolError(
            error_type="approval_rejected", message=reason, retryable=False
        ).model_dump(mode="json")
        state["answer"] = reason
        state["next_action"] = "finish"
        self.tasks.update_from_state(state)
        self.checkpoints.save(state, "finish")
        return self._response(state)

    async def resume(
        self,
        task_id: str,
        user_id: str | None,
        *,
        tenant_id: str | None = None,
    ) -> AgentResponse:
        record = self._require_task(task_id, user_id, tenant_id=tenant_id)
        if record.status not in {TaskStatus.FAILED.value, TaskStatus.TIMEOUT.value}:
            raise InvalidTaskStateError("Only failed or timed-out tasks can be resumed")
        checkpoint = self.checkpoints.latest(task_id, tenant_id)
        if checkpoint is None:
            raise InvalidTaskStateError("Task has no recoverable checkpoint")
        state = deepcopy(checkpoint.state_json)
        state["resume_from_checkpoint"] = True
        state["status"] = TaskStatus.RUNNING.value
        state["error"] = None
        final = await self._workflow().run(state)
        return self._response(final)

    def get(
        self,
        task_id: str,
        user_id: str | None,
        *,
        tenant_id: str | None = None,
    ) -> TaskView:
        record = self._require_task(task_id, user_id, tenant_id=tenant_id)
        state = record.state_json
        response = self._response(state)
        return TaskView(
            **response.model_dump(),
            user_id=record.user_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def _require_task(
        self,
        task_id: str,
        user_id: str | None,
        *,
        tenant_id: str | None = None,
    ):
        record = self.tasks.get(task_id, tenant_id=tenant_id)
        if record is None:
            raise TaskNotFoundError(task_id)
        if user_id is not None and record.user_id != user_id:
            raise TaskAccessError(task_id)
        return record

    def _response(self, state: dict) -> AgentResponse:
        return AgentResponse(
            request_id=state["request_id"],
            task_id=state["task_id"],
            session_id=state["session_id"],
            status=TaskStatus(state["status"]),
            answer=state.get("answer", ""),
            sources=state.get("sources", []),
            tool_calls=[
                ToolCall.model_validate(item) for item in state.get("planned_calls", [])
            ],
            tool_results=[
                ToolResult.model_validate(item)
                for item in state.get("tool_results", [])
            ],
            current_step=state.get("current_step", 0),
            max_steps=state.get("max_steps", self.settings.agent_max_steps),
            error=ToolError.model_validate(state["error"])
            if state.get("error")
            else None,
            token_usage=TokenUsage.model_validate(state.get("token_usage") or {}),
        )
