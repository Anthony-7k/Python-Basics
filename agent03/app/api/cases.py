from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies import get_principal, get_session, require_roles
from app.api.schemas import (
    CaseCreate,
    CaseView,
    ComparisonView,
    DocumentView,
    ExtractionView,
    FieldCorrectionRequest,
    FieldValueView,
    JobEventView,
    JobView,
    ReviewRunView,
    RiskResolutionRequest,
    RiskView,
    SubmitResponse,
    WorkbenchPage,
)
from app.domain import CaseStatus, Role
from app.repositories import TenantRepository
from app.rules import CaseReviewService
from app.security.tokens import Principal
from app.services import CaseService, Conflict, InvalidInput, JobService, ReviewActionService

router = APIRouter(tags=["cases"])
logger = logging.getLogger(__name__)


@router.get("/workbench", response_model=WorkbenchPage)
def workbench(
    q: str = Query(default="", max_length=200),
    status: CaseStatus | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=12, ge=1, le=100),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return TenantRepository(session, principal.tenant_id).workbench(q, status, offset, limit)


@router.get("/jobs/{job_id}/history", response_model=list[JobEventView])
def job_history(
    job_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return TenantRepository(session, principal.tenant_id).list_events(job_id)


def _run_job(request: Request, tenant_id: str, actor_id: str, job_id: str) -> None:
    with request.app.state.database.session_factory() as session:
        try:
            JobService(session, tenant_id, actor_id, request.app.state.providers).run_fake(job_id)
        except Exception:
            logger.exception("eager document job failed", extra={"event": "job.failed"})


@router.post("/cases", response_model=CaseView, status_code=201)
def create_case(
    payload: CaseCreate,
    request: Request,
    principal: Principal = Depends(require_roles(Role.SUBMITTER, Role.TENANT_ADMIN)),
    session: Session = Depends(get_session),
):
    service = CaseService(session, principal.tenant_id, principal.user_id, request.app.state.providers)
    return service.create_case(payload.title, payload.description, request.state.trace_id)


@router.get("/cases", response_model=list[CaseView])
def list_cases(
    q: str = Query(default="", max_length=200),
    status: CaseStatus | None = None,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return TenantRepository(session, principal.tenant_id).list_cases(q, status)


@router.get("/cases/{case_id}/jobs", response_model=list[JobView])
def list_case_jobs(
    case_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return TenantRepository(session, principal.tenant_id).list_case_jobs(case_id)


@router.get("/cases/{case_id}", response_model=CaseView)
def get_case(
    case_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return TenantRepository(session, principal.tenant_id).get_case(case_id)


@router.get("/cases/{case_id}/risks", response_model=list[RiskView])
def get_case_risks(
    case_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return CaseReviewService(session, principal.tenant_id).latest_risks(case_id)


@router.get("/cases/{case_id}/comparison", response_model=ComparisonView)
def get_case_comparison(
    case_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return CaseReviewService(session, principal.tenant_id).comparison(case_id)


@router.post("/cases/{case_id}/review", response_model=ReviewRunView)
def rerun_case_review(
    case_id: str,
    principal: Principal = Depends(require_roles(Role.REVIEWER, Role.TENANT_ADMIN)),
    session: Session = Depends(get_session),
):
    case = TenantRepository(session, principal.tenant_id).get_case(case_id)
    if case.status != CaseStatus.REVIEW_READY:
        raise Conflict("rules can only be rerun when a case is ready for review")
    result = CaseReviewService(session, principal.tenant_id).run(case_id)
    case.version += 1
    session.commit()
    return result


@router.post("/cases/{case_id}/documents", response_model=DocumentView, status_code=201)
def upload_document(
    case_id: str,
    request: Request,
    file: UploadFile,
    principal: Principal = Depends(require_roles(Role.SUBMITTER, Role.TENANT_ADMIN)),
    session: Session = Depends(get_session),
):
    suffix = Path(file.filename or "upload").suffix
    total = 0
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as target:
        temp_path = Path(target.name)
        while chunk := file.file.read(1024 * 1024):
            total += len(chunk)
            if total > request.app.state.settings.max_upload_bytes:
                target.close()
                temp_path.unlink(missing_ok=True)
                raise InvalidInput("file exceeds the 25 MB upload limit")
            target.write(chunk)
    try:
        service = CaseService(session, principal.tenant_id, principal.user_id, request.app.state.providers)
        return service.add_document(
            case_id,
            temp_path,
            file.filename or "upload",
            file.content_type or "application/octet-stream",
            request.app.state.settings.max_upload_bytes,
            request.state.trace_id,
        )
    finally:
        temp_path.unlink(missing_ok=True)


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(
    document_id: str,
    request: Request,
    principal: Principal = Depends(require_roles(Role.SUBMITTER, Role.TENANT_ADMIN)),
    session: Session = Depends(get_session),
):
    service = CaseService(session, principal.tenant_id, principal.user_id, request.app.state.providers)
    service.delete_document(document_id, request.state.trace_id)


@router.get("/documents/{document_id}/extraction", response_model=ExtractionView)
def get_document_extraction(
    document_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return TenantRepository(session, principal.tenant_id).get_latest_extraction(document_id)


@router.patch("/fields/{field_id}", response_model=FieldValueView)
def correct_field(
    field_id: str,
    payload: FieldCorrectionRequest,
    request: Request,
    principal: Principal = Depends(require_roles(Role.REVIEWER, Role.TENANT_ADMIN)),
    session: Session = Depends(get_session),
):
    return ReviewActionService(session, principal.tenant_id, principal.user_id).correct_field(
        field_id,
        payload.expected_version,
        payload.normalized_value,
        payload.reason,
        request.state.trace_id,
    )


@router.post("/risks/{risk_id}/resolve", response_model=RiskView)
def resolve_risk(
    risk_id: str,
    payload: RiskResolutionRequest,
    request: Request,
    principal: Principal = Depends(require_roles(Role.REVIEWER, Role.TENANT_ADMIN)),
    session: Session = Depends(get_session),
):
    return ReviewActionService(session, principal.tenant_id, principal.user_id).resolve_risk(
        risk_id,
        payload.expected_version,
        payload.disposition,
        payload.reason,
        request.state.trace_id,
    )


@router.post("/cases/{case_id}/submit", response_model=SubmitResponse, status_code=202)
def submit_case(
    case_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    principal: Principal = Depends(require_roles(Role.SUBMITTER, Role.TENANT_ADMIN)),
    session: Session = Depends(get_session),
):
    service = JobService(session, principal.tenant_id, principal.user_id, request.app.state.providers)
    job, created = service.submit(case_id, idempotency_key, request.state.trace_id)
    if created and request.app.state.settings.task_queue_backend == "eager":
        background_tasks.add_task(_run_job, request, principal.tenant_id, principal.user_id, job.id)
    job_view = JobView.model_validate(job)
    return SubmitResponse(**job_view.model_dump(), replayed=not created)


@router.get("/jobs/{job_id}", response_model=JobView)
def get_job(
    job_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
):
    return TenantRepository(session, principal.tenant_id).get_job(job_id)

