from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domain import (
    AgentRequest,
    AgentResponse,
    ApprovalRequest,
    RejectRequest,
    ResumeRequest,
    TaskView,
)
from app.service import AgentService

router = APIRouter(prefix="/api/v1")


def get_session(request: Request):
    session = request.app.state.database.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_service(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> AgentService:
    return AgentService(
        session,
        request.app.state.settings,
        registry=request.app.state.registry,
        planner=request.app.state.planner,
    )


@router.get("/health")
def health(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "request_id": request.state.request_id,
        "database": "ok",
    }


@router.post("/agent/chat", response_model=AgentResponse)
async def chat(
    payload: AgentRequest,
    request: Request,
    service: Annotated[AgentService, Depends(get_service)],
) -> AgentResponse:
    return await service.run(payload, request.state.request_id)


@router.get("/tasks/{task_id}", response_model=TaskView)
def get_task(
    task_id: str,
    service: Annotated[AgentService, Depends(get_service)],
    user_id: Annotated[str, Query(min_length=1, max_length=100)],
) -> TaskView:
    return service.get(task_id, user_id)


@router.post("/tasks/{task_id}/approve", response_model=AgentResponse)
async def approve_task(
    task_id: str,
    payload: ApprovalRequest,
    service: Annotated[AgentService, Depends(get_service)],
) -> AgentResponse:
    return await service.approve(task_id, payload.user_id, payload.modified_payload)


@router.post("/tasks/{task_id}/reject", response_model=AgentResponse)
def reject_task(
    task_id: str,
    payload: RejectRequest,
    service: Annotated[AgentService, Depends(get_service)],
) -> AgentResponse:
    return service.reject(task_id, payload.user_id, payload.reason)


@router.post("/tasks/{task_id}/resume", response_model=AgentResponse)
async def resume_task(
    task_id: str,
    payload: ResumeRequest,
    service: Annotated[AgentService, Depends(get_service)],
) -> AgentResponse:
    return await service.resume(task_id, payload.user_id)
