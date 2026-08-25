from fastapi import APIRouter, Depends, Request

from app.api.authentication import get_current_user
from app.api.dependencies import get_agent_service
from app.core.rate_limit import request_limiter
from app.core.security import AuthenticatedUser
from app.core.settings import (
    CHAT_RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
)
from app.schemas.agent import (
    AgentRequest,
    AgentResponse,
)
from app.services.agent import BoundedAgentService


router = APIRouter(
    prefix="/api/v1",
    tags=["agent"],
)


@router.post(
    "/agent/run",
    response_model=AgentResponse,
)
def run_agent(
    request: AgentRequest,
    http_request: Request,
    agent_service: BoundedAgentService = Depends(
        get_agent_service
    ),
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
):
    request_limiter.check(
        scope="agent",
        actor_id=current_user.audit_id,
        limit=CHAT_RATE_LIMIT_REQUESTS,
        window_seconds=RATE_LIMIT_WINDOW_SECONDS,
    )
    return agent_service.run(
        request,
        request_id=http_request.state.request_id,
    )
