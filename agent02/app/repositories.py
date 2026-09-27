from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from math import ceil
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import (
    AuditEventRecord,
    CheckpointRecord,
    LLMCallRecord,
    MemoryRecord,
    TaskRecord,
    TaskStepRecord,
    ToolCallRecord,
)
from app.domain import TaskStatus, ToolCall, ToolResult, utc_now


class TaskRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        task_id: str,
        request_id: str,
        tenant_id: str,
        created_by: str,
        user_id: str,
        session_id: str,
        knowledge_base_id: str | None,
        message: str,
        max_steps: int,
        state: dict[str, Any],
    ) -> TaskRecord:
        record = TaskRecord(
            id=task_id,
            request_id=request_id,
            tenant_id=tenant_id,
            created_by=created_by,
            user_id=user_id,
            session_id=session_id,
            knowledge_base_id=knowledge_base_id,
            message=message,
            status=TaskStatus.CREATED.value,
            max_steps=max_steps,
            state_json=deepcopy(state),
        )
        self.session.add(record)
        self.session.commit()
        return record

    def get(
        self,
        task_id: str,
        user_id: str | None = None,
        tenant_id: str | None = None,
    ) -> TaskRecord | None:
        query = select(TaskRecord).where(TaskRecord.id == task_id)
        if user_id is not None:
            query = query.where(TaskRecord.user_id == user_id)
        if tenant_id is not None:
            query = query.where(TaskRecord.tenant_id == tenant_id)
        return self.session.scalar(query)

    def update_from_state(self, state: dict[str, Any]) -> TaskRecord:
        record = self.get(state["task_id"], tenant_id=state["tenant_id"])
        if record is None:
            raise LookupError(f"Task not found: {state['task_id']}")
        record.status = state.get("status", record.status)
        record.answer = state.get("answer", "")
        record.error_json = state.get("error")
        record.state_json = deepcopy(state)
        record.current_step = state.get("current_step", 0)
        usage = state.get("token_usage") or {}
        record.input_tokens = usage.get("input_tokens")
        record.output_tokens = usage.get("output_tokens")
        record.updated_at = utc_now()
        self.session.commit()
        return record

    def list_for_tenant(self, tenant_id: str, *, limit: int = 100) -> list[TaskRecord]:
        query = (
            select(TaskRecord)
            .where(TaskRecord.tenant_id == tenant_id)
            .order_by(TaskRecord.created_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(query))

    def add_step(
        self,
        task_id: str,
        tenant_id: str,
        step_number: int,
        node: str,
        status: str,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.session.add(
            TaskStepRecord(
                task_id=task_id,
                tenant_id=tenant_id,
                step_number=step_number,
                node=node,
                status=status,
                detail_json=detail or {},
            )
        )
        self.session.commit()

    def save_tool_call(
        self,
        task_id: str,
        tenant_id: str,
        call: ToolCall,
        result: ToolResult,
    ) -> None:
        record = self.session.get(ToolCallRecord, call.call_id)
        if record is None:
            record = ToolCallRecord(
                id=call.call_id,
                task_id=task_id,
                tenant_id=tenant_id,
                tool_name=call.name,
                arguments_json=call.arguments,
            )
            self.session.add(record)
        record.result_json = result.model_dump(mode="json")
        record.success = result.success
        record.retry_count = result.retry_count
        record.latency_ms = result.latency_ms
        self.session.commit()


class CheckpointRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, state: dict[str, Any], next_node: str) -> CheckpointRecord:
        current_version = self.session.scalar(
            select(func.max(CheckpointRecord.state_version)).where(
                CheckpointRecord.task_id == state["task_id"],
                CheckpointRecord.tenant_id == state["tenant_id"],
            )
        )
        checkpoint = CheckpointRecord(
            task_id=state["task_id"],
            tenant_id=state["tenant_id"],
            state_version=(current_version or 0) + 1,
            current_step=state.get("current_step", 0),
            next_node=next_node,
            state_json=deepcopy(state),
        )
        self.session.add(checkpoint)
        self.session.commit()
        return checkpoint

    def latest(
        self, task_id: str, tenant_id: str | None = None
    ) -> CheckpointRecord | None:
        query = select(CheckpointRecord).where(CheckpointRecord.task_id == task_id)
        if tenant_id is not None:
            query = query.where(CheckpointRecord.tenant_id == tenant_id)
        return self.session.scalar(
            query.order_by(CheckpointRecord.state_version.desc()).limit(1)
        )


class MemoryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save_short_term(
        self,
        user_id: str,
        session_id: str,
        key: str,
        value: dict[str, Any],
        *,
        tenant_id: str = "legacy",
    ) -> None:
        self._upsert(tenant_id, user_id, session_id, "short_term", key, value)

    def save_long_term(
        self,
        user_id: str,
        key: str,
        value: dict[str, Any],
        *,
        tenant_id: str = "legacy",
    ) -> None:
        self._upsert(tenant_id, user_id, None, "long_term", key, value)

    def _upsert(
        self,
        tenant_id: str,
        user_id: str,
        session_id: str | None,
        kind: str,
        key: str,
        value: dict[str, Any],
    ) -> None:
        query = select(MemoryRecord).where(
            MemoryRecord.tenant_id == tenant_id,
            MemoryRecord.user_id == user_id,
            MemoryRecord.kind == kind,
            MemoryRecord.key == key,
        )
        if session_id is None:
            query = query.where(MemoryRecord.session_id.is_(None))
        else:
            query = query.where(MemoryRecord.session_id == session_id)
        record = self.session.scalar(query)
        if record is None:
            record = MemoryRecord(
                tenant_id=tenant_id,
                owner_subject=user_id,
                user_id=user_id,
                session_id=session_id,
                kind=kind,
                key=key,
                value_json=deepcopy(value),
            )
            self.session.add(record)
        else:
            record.value_json = deepcopy(value)
            record.updated_at = utc_now()
        self.session.commit()

    def list_for_user(
        self,
        user_id: str,
        *,
        session_id: str | None = None,
        tenant_id: str = "legacy",
    ) -> list[MemoryRecord]:
        query = select(MemoryRecord).where(
            MemoryRecord.tenant_id == tenant_id,
            MemoryRecord.user_id == user_id,
        )
        if session_id is not None:
            query = query.where(
                (MemoryRecord.session_id == session_id)
                | (MemoryRecord.session_id.is_(None))
            )
        return list(self.session.scalars(query.order_by(MemoryRecord.id)))


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        *,
        tenant_id: str,
        actor: str,
        action: str,
        resource_type: str,
        resource_id: str | None,
        outcome: str,
        request_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEventRecord:
        event = AuditEventRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            request_id=request_id,
            metadata_json=deepcopy(metadata or {}),
        )
        self.session.add(event)
        self.session.commit()
        return event

    def list_for_tenant(
        self, tenant_id: str, *, limit: int = 100
    ) -> list[AuditEventRecord]:
        query = (
            select(AuditEventRecord)
            .where(AuditEventRecord.tenant_id == tenant_id)
            .order_by(AuditEventRecord.created_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(query))


class LLMCallRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        *,
        tenant_id: str,
        task_id: str,
        provider: str,
        model: str,
        prompt_version: str,
        input_tokens: int | None,
        output_tokens: int | None,
        estimated_cost_usd: float | None,
        latency_ms: float,
        error_type: str | None = None,
    ) -> LLMCallRecord:
        record = LLMCallRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            task_id=task_id,
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimated_cost_usd,
            latency_ms=latency_ms,
            error_type=error_type,
        )
        self.session.add(record)
        self.session.commit()
        return record


class MetricsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def summary(self, tenant_id: str, *, hours: int = 24) -> dict[str, Any]:
        since = datetime.now(UTC) - timedelta(hours=hours)
        tasks = list(
            self.session.scalars(
                select(TaskRecord).where(
                    TaskRecord.tenant_id == tenant_id,
                    TaskRecord.created_at >= since,
                )
            )
        )
        tool_calls = list(
            self.session.scalars(
                select(ToolCallRecord).where(
                    ToolCallRecord.tenant_id == tenant_id,
                    ToolCallRecord.created_at >= since,
                )
            )
        )
        llm_calls = list(
            self.session.scalars(
                select(LLMCallRecord).where(
                    LLMCallRecord.tenant_id == tenant_id,
                    LLMCallRecord.created_at >= since,
                )
            )
        )
        durations = sorted(
            max(0.0, (task.updated_at - task.created_at).total_seconds() * 1000)
            for task in tasks
        )
        terminal = [
            task
            for task in tasks
            if task.status
            in {
                TaskStatus.COMPLETED.value,
                TaskStatus.FAILED.value,
                TaskStatus.TIMEOUT.value,
            }
        ]
        completed = sum(task.status == TaskStatus.COMPLETED.value for task in terminal)
        p95_index = ceil(len(durations) * 0.95) - 1 if durations else 0
        return {
            "window_hours": hours,
            "task_count": len(tasks),
            "task_success_rate": completed / len(terminal) if terminal else None,
            "p95_task_latency_ms": round(durations[p95_index], 3)
            if durations
            else None,
            "tool_call_count": len(tool_calls),
            "tool_failure_count": sum(call.success is False for call in tool_calls),
            "tool_retry_count": sum(call.retry_count for call in tool_calls),
            "llm_call_count": len(llm_calls),
            "input_tokens": sum(call.input_tokens or 0 for call in llm_calls),
            "output_tokens": sum(call.output_tokens or 0 for call in llm_calls),
            "estimated_cost_usd": round(
                sum(call.estimated_cost_usd or 0 for call in llm_calls), 8
            ),
        }
