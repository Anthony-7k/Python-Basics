from __future__ import annotations

import hashlib
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Request, Response
from sqlalchemy.orm import Session

from app.api.dependencies import get_principal, get_session, require_roles
from app.api.schemas import (
    ApprovalRequest,
    ApprovalView,
    ReportRequest,
    ReportRequestView,
    ReportView,
)
from app.domain import Role
from app.repositories import TenantRepository
from app.security.tokens import Principal
from app.services import ApprovalService, Conflict, ReportService

router = APIRouter(tags=["approvals", "reports"])


@router.get("/cases/{case_id}/reports", response_model=list[ReportView])
def list_case_reports(
    case_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return TenantRepository(session, principal.tenant_id).list_case_reports(case_id)


def _run_report(request: Request, tenant_id: str, actor_id: str, report_id: str) -> None:
    with request.app.state.database.session_factory() as session:
        try:
            ReportService(
                session, tenant_id, actor_id, request.app.state.providers
            ).generate(report_id)
        except Exception:
            logging.getLogger(__name__).exception("report generation failed")


@router.post("/reports/{report_id}/retry", response_model=ReportView, status_code=202)
def retry_report(
    report_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    principal: Principal = Depends(require_roles(Role.APPROVER, Role.TENANT_ADMIN)),
    session: Session = Depends(get_session),
):
    report = ReportService(session, principal.tenant_id, principal.user_id,
        request.app.state.providers).retry(report_id, request.state.trace_id)
    if request.app.state.settings.task_queue_backend == "eager":
        background_tasks.add_task(_run_report, request, principal.tenant_id, principal.user_id, report.id)
    return ReportView.model_validate(report)


@router.post("/cases/{case_id}/approvals", response_model=ApprovalView, status_code=201)
def decide_case(
    case_id: str,
    payload: ApprovalRequest,
    request: Request,
    principal: Principal = Depends(require_roles(Role.APPROVER, Role.TENANT_ADMIN)),
    session: Session = Depends(get_session),
):
    return ApprovalService(session, principal.tenant_id, principal.user_id).decide(
        case_id,
        payload.expected_version,
        payload.decision,
        payload.reason,
        request.state.trace_id,
    )


@router.post("/cases/{case_id}/reports", response_model=ReportRequestView, status_code=202)
def request_report(
    case_id: str,
    payload: ReportRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    principal: Principal = Depends(require_roles(Role.APPROVER, Role.TENANT_ADMIN)),
    session: Session = Depends(get_session),
):
    service = ReportService(
        session, principal.tenant_id, principal.user_id, request.app.state.providers
    )
    report, created = service.request(
        case_id, payload.expected_version, idempotency_key, request.state.trace_id
    )
    if created and request.app.state.settings.task_queue_backend == "eager":
        background_tasks.add_task(
            _run_report, request, principal.tenant_id, principal.user_id, report.id
        )
    view = ReportView.model_validate(report)
    return ReportRequestView(**view.model_dump(), replayed=not created)


@router.get("/reports/{report_id}", response_model=ReportView)
def get_report(
    report_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return TenantRepository(session, principal.tenant_id).get_report(report_id)


@router.get("/reports/{report_id}/download")
def download_report(
    report_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    report = TenantRepository(session, principal.tenant_id).get_report(report_id)
    if report.status != "READY" or not report.object_key:
        raise Conflict("report is not ready for download")
    extension = "pdf" if report.content_type == "application/pdf" else "html"
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{extension}") as target:
        temp_path = Path(target.name)
    try:
        request.app.state.providers.storage.get_to(report.object_key, temp_path)
        payload = temp_path.read_bytes()
    finally:
        temp_path.unlink(missing_ok=True)
    if hashlib.sha256(payload).hexdigest() != report.content_hash:
        raise Conflict("stored report failed integrity verification")
    return Response(
        payload,
        media_type=report.content_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="docflow-report-{report.id}.{extension}"'
            ),
            "ETag": f'"{report.content_hash}"',
        },
    )
