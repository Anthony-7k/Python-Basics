from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_principal, get_session
from app.api.schemas import DashboardSummary
from app.security.tokens import Principal
from app.services import DashboardService

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(
    start: date | None = None,
    end: date | None = None,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return DashboardService(session, principal.tenant_id).summary(start, end)
