from fastapi import APIRouter

from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.cases import router as cases_router
from app.api.dashboard import router as dashboard_router
from app.api.events import router as events_router
from app.api.policies import router as policies_router
from app.api.reports import router as reports_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(cases_router)
router.include_router(events_router)
router.include_router(policies_router)
router.include_router(reports_router)
router.include_router(dashboard_router)
router.include_router(audit_router)

