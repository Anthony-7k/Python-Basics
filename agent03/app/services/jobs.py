from __future__ import annotations

import hashlib
from uuid import uuid4

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import AuditLog, Job, JobEvent, ReviewCase
from app.document_ai import DocumentIntelligenceService
from app.domain import CaseStatus, JobStatus, transition_case
from app.providers import ProviderBundle
from app.repositories import TenantRepository
from app.rules import CaseReviewService
from app.services.errors import Conflict, InvalidInput


class JobService:
    def __init__(self, session: Session, tenant_id: str, actor_id: str, providers: ProviderBundle):
        self.session = session
        self.tenant_id = tenant_id
        self.actor_id = actor_id
        self.providers = providers
        self.repo = TenantRepository(session, tenant_id)

    def submit(self, case_id: str, idempotency_key: str, trace_id: str) -> tuple[Job, bool]:
        if not idempotency_key.strip() or len(idempotency_key) > 200:
            raise InvalidInput("Idempotency-Key must contain 1 to 200 characters")
        request_hash = hashlib.sha256(f"submit:{case_id}".encode()).hexdigest()
        existing = self.repo.find_job_by_idempotency(idempotency_key)
        if existing:
            if existing.request_hash != request_hash:
                raise Conflict("idempotency key was already used for a different request")
            return existing, False
        case = self.repo.get_case(case_id)
        if not case.documents:
            raise InvalidInput("at least one document is required before submission")
        try:
            case.status = transition_case(case.status, CaseStatus.QUEUED).value
        except ValueError as exc:
            raise Conflict(str(exc)) from exc
        claimed = self.session.execute(update(ReviewCase).where(
            ReviewCase.id == case.id, ReviewCase.tenant_id == self.tenant_id,
            ReviewCase.version == case.version,
            ReviewCase.status.in_([CaseStatus.DRAFT.value, CaseStatus.FAILED.value]),
        ).values(status=CaseStatus.QUEUED.value, version=case.version + 1),
            execution_options={"autoflush": False})
        if claimed.rowcount != 1:
            self.session.rollback()
            raise Conflict("case submission conflict; refresh and try again")
        self.session.expire(case)
        job = Job(
            tenant_id=self.tenant_id,
            case_id=case.id,
            status=JobStatus.QUEUED.value,
            stage="queued",
            progress=0,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            trace_id=trace_id,
        )
        self.session.add(job)
        self.session.flush()
        self._event(job, "job.queued", {"stage": "queued", "progress": 0})
        self.session.add(
            AuditLog(
                tenant_id=self.tenant_id,
                actor_id=self.actor_id,
                action="case.submit",
                resource_type="case",
                resource_id=case.id,
                outcome="success",
                trace_id=trace_id,
                after={"version": case.version, "job_id": job.id},
            )
        )
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raced = self.repo.find_job_by_idempotency(idempotency_key)
            if raced and raced.request_hash == request_hash:
                return raced, False
            raise Conflict("idempotency key conflict") from exc
        self.providers.queue.enqueue(job.id)
        return job, True

    def run_fake(self, job_id: str) -> Job:
        job = self.repo.get_job(job_id)
        if JobStatus(job.status) == JobStatus.SUCCEEDED:
            return job
        if JobStatus(job.status) not in {JobStatus.QUEUED, JobStatus.FAILED}:
            raise Conflict("job is already processing")
        case = self.repo.get_case(job.case_id)
        latest_jobs = self.repo.list_case_jobs(case.id)
        if latest_jobs[0].id != job.id or case.status not in {"QUEUED", "FAILED"}:
            raise Conflict("job no longer owns the active case processing attempt")
        claimed = self.session.execute(update(Job).where(
            Job.id == job.id, Job.tenant_id == self.tenant_id,
            Job.status.in_(["QUEUED", "FAILED"])
        ).values(status="PROCESSING"))
        if claimed.rowcount != 1:
            self.session.rollback()
            raise Conflict("job is already processing")
        failed_stage = "parsing"
        try:
            if CaseStatus(case.status) == CaseStatus.FAILED:
                case.status = transition_case(case.status, CaseStatus.QUEUED).value
            case.status = transition_case(case.status, CaseStatus.PROCESSING).value
            job.status = JobStatus.PROCESSING.value
            job.error_code = None
            job.error_message = None
            job.stage = "parsing"
            job.progress = 10
            self._event(job, "job.started", {"stage": job.stage, "progress": job.progress})
            self.session.commit()
            intelligence = DocumentIntelligenceService(
                self.session, self.tenant_id, self.providers
            )
            results = [intelligence.process(document) for document in case.documents]
            job.stage = "running_rules"
            failed_stage = "running_rules"
            job.progress = 90
            self._event(job, "job.progress", {"stage": job.stage, "progress": job.progress})
            review = CaseReviewService(self.session, self.tenant_id).run(case.id)
            case.status = transition_case(case.status, CaseStatus.REVIEW_READY).value
            case.version += 1
            job.status = JobStatus.SUCCEEDED.value
            job.stage = "review_ready"
            job.progress = 100
            self._event(
                job,
                "job.completed",
                {
                    "stage": job.stage,
                    "progress": 100,
                    "documents": results,
                    "review_run_group_id": review.run_group_id,
                    "rule_count": review.rules,
                    "risk_count": review.risks,
                },
            )
            self.session.commit()
            return job
        except Exception as exc:
            self.session.rollback()
            job = self.repo.get_job(job_id)
            case = self.repo.get_case(job.case_id)
            if CaseStatus(case.status) in {CaseStatus.QUEUED, CaseStatus.PROCESSING}:
                case.status = transition_case(case.status, CaseStatus.FAILED).value
            for document in case.documents:
                if document.parse_status != "COMPLETED":
                    document.parse_status = "FAILED"
            job.status = JobStatus.FAILED.value
            job.stage = "failed"
            job.error_code = type(exc).__name__
            job.error_message = str(exc)[:1000]
            self._event(job, "job.failed", {"stage": failed_stage, "message": job.error_message})
            self.session.commit()
            raise

    def _event(self, job: Job, event_type: str, payload: dict) -> JobEvent:
        event = JobEvent(
            id=str(uuid4()),
            tenant_id=self.tenant_id,
            case_id=job.case_id,
            job_id=job.id,
            sequence=self.repo.next_event_sequence(job.id),
            event_type=event_type,
            trace_id=job.trace_id,
            payload=payload,
        )
        self.session.add(event)
        return event

