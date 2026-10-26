from __future__ import annotations

import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api import get_service, get_session
from app.domain import (
    AgentResponse,
    AgentV2Request,
    ApprovalV2Request,
    AuditEventView,
    DevTokenRequest,
    RejectV2Request,
    TaskView,
    TokenResponse,
)
from app.repositories import AuditRepository, MetricsRepository
from app.security.auth import JWTService, get_current_user
from app.security.models import UserContext
from app.security.permissions import Permission, Role, has_permission
from app.service import AgentService, TaskNotFoundError

router = APIRouter(prefix="/api/v2")


def _audit(
    session: Session,
    request: Request,
    identity: UserContext,
    *,
    action: str,
    resource_type: str,
    resource_id: str | None,
    outcome: str,
    metadata: dict | None = None,
) -> None:
    AuditRepository(session).record(
        tenant_id=identity.tenant_id,
        actor=identity.subject,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        request_id=request.state.request_id,
        metadata=metadata,
    )


def _authorize(
    session: Session,
    request: Request,
    identity: UserContext,
    permission: Permission,
    *,
    action: str,
    resource_type: str = "task",
    resource_id: str | None = None,
) -> None:
    if has_permission(identity, permission):
        return
    _audit(
        session,
        request,
        identity,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome="denied",
        metadata={"required_permission": permission.value},
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": "permission_denied",
            "required_permission": permission.value,
        },
    )


@router.post("/auth/dev-token", response_model=TokenResponse)
def issue_dev_token(payload: DevTokenRequest, request: Request) -> TokenResponse:
    invalid_roles = sorted(set(payload.roles) - {role.value for role in Role})
    if invalid_roles:
        raise HTTPException(
            status_code=422,
            detail={"error": "invalid_roles", "roles": invalid_roles},
        )
    service = JWTService(request.app.state.settings)
    try:
        token = service.issue_dev_token(
            subject=payload.subject,
            tenant_id=payload.tenant_id,
            roles=payload.roles,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc
    return TokenResponse(
        access_token=token,
        expires_in=request.app.state.settings.jwt_token_ttl_seconds,
    )


@router.get("/workspace")
def workspace(
    request: Request,
    identity: Annotated[UserContext, Depends(get_current_user)],
) -> dict:
    """Display the verified identity and non-secret runtime capabilities."""
    settings = request.app.state.settings
    return {
        "subject": identity.subject,
        "tenant_id": identity.tenant_id,
        "roles": sorted(identity.roles),
        "permissions": sorted(
            permission.value
            for permission in Permission
            if has_permission(identity, permission)
        ),
        "environment": settings.app_env,
        "planner_mode": settings.planner_mode,
        "knowledge_backend": settings.knowledge_backend,
    }


@router.post("/agent/chat", response_model=AgentResponse)
async def chat(
    payload: AgentV2Request,
    request: Request,
    identity: Annotated[UserContext, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[AgentService, Depends(get_service)],
) -> AgentResponse:
    _authorize(
        session,
        request,
        identity,
        Permission.TASK_CREATE,
        action="task.create",
    )
    response = await service.run_as(payload, identity, request.state.request_id)
    _audit(
        session,
        request,
        identity,
        action="task.create",
        resource_type="task",
        resource_id=response.task_id,
        outcome="allowed",
    )
    return response


@router.post("/agent/chat/stream")
async def chat_stream(
    payload: AgentV2Request,
    request: Request,
    identity: Annotated[UserContext, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[AgentService, Depends(get_service)],
) -> StreamingResponse:
    _authorize(
        session,
        request,
        identity,
        Permission.TASK_CREATE,
        action="task.create",
    )

    async def stream():
        queue: asyncio.Queue[tuple[str, dict] | None] = asyncio.Queue()

        async def event_sink(event: str, data: dict) -> None:
            await queue.put((event, data))

        async def run_agent() -> None:
            try:
                response = await service.run_as(
                    payload,
                    identity,
                    request.state.request_id,
                    event_sink=event_sink,
                )
                _audit(
                    session,
                    request,
                    identity,
                    action="task.create",
                    resource_type="task",
                    resource_id=response.task_id,
                    outcome="allowed",
                    metadata={"stream": True},
                )
            except Exception:
                await queue.put(
                    (
                        "failed",
                        {
                            "request_id": request.state.request_id,
                            "error": {"error_type": "internal_server_error"},
                        },
                    )
                )
            finally:
                await queue.put(None)

        task = asyncio.create_task(run_agent())
        while True:
            item = await queue.get()
            if item is None:
                break
            event, data = item
            yield (
                f"event: {event}\n"
                f"data: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"
            )
        await task

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/tasks", response_model=list[TaskView])
def list_tasks(
    request: Request,
    identity: Annotated[UserContext, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[AgentService, Depends(get_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[TaskView]:
    _authorize(
        session,
        request,
        identity,
        Permission.TASK_READ,
        action="task.list",
    )
    records = service.tasks.list_for_tenant(identity.tenant_id, limit=limit)
    return [
        service.get(record.id, None, tenant_id=identity.tenant_id) for record in records
    ]


@router.get("/tasks/{task_id}", response_model=TaskView)
def get_task(
    task_id: str,
    request: Request,
    identity: Annotated[UserContext, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[AgentService, Depends(get_service)],
) -> TaskView:
    _authorize(
        session,
        request,
        identity,
        Permission.TASK_READ,
        action="task.read",
        resource_id=task_id,
    )
    try:
        response = service.get(task_id, None, tenant_id=identity.tenant_id)
    except TaskNotFoundError:
        _audit(
            session,
            request,
            identity,
            action="task.read",
            resource_type="task",
            resource_id=task_id,
            outcome="denied",
        )
        raise
    _audit(
        session,
        request,
        identity,
        action="task.read",
        resource_type="task",
        resource_id=task_id,
        outcome="allowed",
    )
    return response


@router.post("/tasks/{task_id}/approve", response_model=AgentResponse)
async def approve_task(
    task_id: str,
    payload: ApprovalV2Request,
    request: Request,
    identity: Annotated[UserContext, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[AgentService, Depends(get_service)],
) -> AgentResponse:
    _authorize(
        session,
        request,
        identity,
        Permission.TASK_APPROVE,
        action="task.approve",
        resource_id=task_id,
    )
    response = await service.approve(
        task_id,
        None,
        payload.modified_payload,
        tenant_id=identity.tenant_id,
    )
    _audit(
        session,
        request,
        identity,
        action="task.approve",
        resource_type="task",
        resource_id=task_id,
        outcome="allowed",
        metadata={"payload_modified": payload.modified_payload is not None},
    )
    return response


@router.post("/tasks/{task_id}/reject", response_model=AgentResponse)
def reject_task(
    task_id: str,
    payload: RejectV2Request,
    request: Request,
    identity: Annotated[UserContext, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[AgentService, Depends(get_service)],
) -> AgentResponse:
    _authorize(
        session,
        request,
        identity,
        Permission.TASK_APPROVE,
        action="task.reject",
        resource_id=task_id,
    )
    response = service.reject(
        task_id,
        None,
        payload.reason,
        tenant_id=identity.tenant_id,
    )
    _audit(
        session,
        request,
        identity,
        action="task.reject",
        resource_type="task",
        resource_id=task_id,
        outcome="allowed",
    )
    return response


@router.post("/tasks/{task_id}/resume", response_model=AgentResponse)
async def resume_task(
    task_id: str,
    request: Request,
    identity: Annotated[UserContext, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    service: Annotated[AgentService, Depends(get_service)],
) -> AgentResponse:
    _authorize(
        session,
        request,
        identity,
        Permission.TASK_RESUME,
        action="task.resume",
        resource_id=task_id,
    )
    response = await service.resume(
        task_id,
        None,
        tenant_id=identity.tenant_id,
    )
    _audit(
        session,
        request,
        identity,
        action="task.resume",
        resource_type="task",
        resource_id=task_id,
        outcome="allowed",
    )
    return response


@router.get("/audit-events", response_model=list[AuditEventView])
def list_audit_events(
    request: Request,
    identity: Annotated[UserContext, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[AuditEventView]:
    _authorize(
        session,
        request,
        identity,
        Permission.AUDIT_READ,
        action="audit.list",
        resource_type="audit_event",
    )
    records = AuditRepository(session).list_for_tenant(identity.tenant_id, limit=limit)
    return [
        AuditEventView.model_validate(record, from_attributes=True)
        for record in records
    ]


@router.get("/metrics/summary")
def metrics_summary(
    request: Request,
    identity: Annotated[UserContext, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    _authorize(
        session,
        request,
        identity,
        Permission.METRICS_READ,
        action="metrics.read",
        resource_type="metrics",
    )
    return MetricsRepository(session).summary(identity.tenant_id)
