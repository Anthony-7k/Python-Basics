from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_session, require_roles
from app.api.schemas import AuditPage
from app.domain import Role
from app.repositories import TenantRepository
from app.security.tokens import Principal

router = APIRouter(tags=["audit"])


@router.get("/audit-logs", response_model=AuditPage)
def list_audit_logs(
    action: str | None = Query(default=None, max_length=100),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    principal: Principal = Depends(require_roles(Role.TENANT_ADMIN)),
    session: Session = Depends(get_session),
):
    return TenantRepository(session, principal.tenant_id).list_audit_logs(action, offset, limit)
