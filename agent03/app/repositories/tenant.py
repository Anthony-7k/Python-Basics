from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.database import (
    AuditLog,
    Document,
    ExtractionRun,
    FieldValue,
    Job,
    JobEvent,
    Report,
    ReviewCase,
    RiskFinding,
)


class NotFound(LookupError):
    pass


class TenantRepository:
    """Repository that always binds business queries to one tenant."""

    def __init__(self, session: Session, tenant_id: str):
        if not tenant_id:
            raise ValueError("tenant_id is required")
        self.session = session
        self.tenant_id = tenant_id

    def list_cases(self, query: str = "", status: str | None = None) -> list[ReviewCase]:
        statement = (
            select(ReviewCase)
            .where(ReviewCase.tenant_id == self.tenant_id)
            .options(selectinload(ReviewCase.documents))
            .order_by(ReviewCase.created_at.desc())
        )
        if query.strip():
            statement = statement.where(ReviewCase.title.icontains(query.strip(), autoescape=True))
        if status:
            statement = statement.where(ReviewCase.status == status)
        return list(self.session.scalars(statement))

    def list_case_jobs(self, case_id: str) -> list[Job]:
        self.get_case(case_id)
        return list(self.session.scalars(select(Job).where(
            Job.tenant_id == self.tenant_id, Job.case_id == case_id
        ).order_by(Job.created_at.desc(), Job.id)))

    def workbench(self, query: str, status: str | None, offset: int, limit: int) -> dict:
        filters = [ReviewCase.tenant_id == self.tenant_id]
        if query.strip():
            filters.append(ReviewCase.title.icontains(query.strip(), autoescape=True))
        if status:
            filters.append(ReviewCase.status == status)
        total = self.session.scalar(select(func.count()).select_from(ReviewCase).where(*filters))
        cases = list(self.session.scalars(select(ReviewCase).where(*filters)
            .options(selectinload(ReviewCase.documents))
            .order_by(ReviewCase.created_at.desc(), ReviewCase.id).offset(offset).limit(limit)))
        ids = [case.id for case in cases]
        jobs = {}
        reports = {}
        for model, target in [(Job, jobs), (Report, reports)]:
            for item in self.session.scalars(select(model).where(
                model.tenant_id == self.tenant_id, model.case_id.in_(ids)
            ).order_by(model.created_at.desc(), model.id)):
                target.setdefault(item.case_id, item)
        return {"items": cases, "jobs": jobs, "reports": reports,
                "total": total, "offset": offset, "limit": limit}

    def list_case_reports(self, case_id: str) -> list[Report]:
        self.get_case(case_id)
        return list(self.session.scalars(select(Report).where(
            Report.tenant_id == self.tenant_id, Report.case_id == case_id
        ).order_by(Report.created_at.desc(), Report.id)))

    def list_audit_logs(self, action: str | None, offset: int, limit: int) -> dict:
        filters = [AuditLog.tenant_id == self.tenant_id]
        if action:
            filters.append(AuditLog.action == action)
        total = self.session.scalar(select(func.count()).select_from(AuditLog).where(*filters))
        items = list(self.session.scalars(select(AuditLog).where(*filters)
            .order_by(AuditLog.created_at.desc(), AuditLog.id).offset(offset).limit(limit)))
        return {"items": items, "total": total, "offset": offset, "limit": limit}

    def get_case(self, case_id: str, *, with_documents: bool = True) -> ReviewCase:
        statement = select(ReviewCase).where(
            ReviewCase.id == case_id,
            ReviewCase.tenant_id == self.tenant_id,
        )
        if with_documents:
            statement = statement.options(selectinload(ReviewCase.documents))
        case = self.session.scalar(statement)
        if case is None:
            raise NotFound("case not found")
        return case

    def get_document(self, document_id: str) -> Document:
        document = self.session.scalar(
            select(Document).where(
                Document.id == document_id,
                Document.tenant_id == self.tenant_id,
            )
        )
        if document is None:
            raise NotFound("document not found")
        return document

    def get_latest_extraction(self, document_id: str) -> ExtractionRun:
        self.get_document(document_id)
        statement = (
            select(ExtractionRun)
            .where(
                ExtractionRun.document_id == document_id,
                ExtractionRun.tenant_id == self.tenant_id,
            )
            .options(joinedload(ExtractionRun.fields).joinedload(FieldValue.evidence))
            .order_by(ExtractionRun.created_at.desc())
        )
        run = self.session.scalars(statement).unique().first()
        if run is None:
            raise NotFound("extraction not found")
        return run

    def find_document_hash(self, case_id: str, sha256: str) -> Document | None:
        return self.session.scalar(
            select(Document).where(
                Document.case_id == case_id,
                Document.tenant_id == self.tenant_id,
                Document.sha256 == sha256,
            )
        )

    def get_field(self, field_id: str) -> FieldValue:
        field = self.session.scalar(
            select(FieldValue)
            .where(FieldValue.id == field_id, FieldValue.tenant_id == self.tenant_id)
            .options(joinedload(FieldValue.evidence))
        )
        if field is None:
            raise NotFound("field not found")
        return field

    def get_risk(self, risk_id: str) -> RiskFinding:
        risk = self.session.scalar(
            select(RiskFinding).where(
                RiskFinding.id == risk_id,
                RiskFinding.tenant_id == self.tenant_id,
            )
        )
        if risk is None:
            raise NotFound("risk not found")
        return risk

    def get_report(self, report_id: str) -> Report:
        report = self.session.scalar(
            select(Report).where(
                Report.id == report_id,
                Report.tenant_id == self.tenant_id,
            )
        )
        if report is None:
            raise NotFound("report not found")
        return report

    def find_report_by_idempotency(self, key: str) -> Report | None:
        return self.session.scalar(
            select(Report).where(
                Report.tenant_id == self.tenant_id,
                Report.idempotency_key == key,
            )
        )

    def get_job(self, job_id: str) -> Job:
        job = self.session.scalar(
            select(Job).where(Job.id == job_id, Job.tenant_id == self.tenant_id)
        )
        if job is None:
            raise NotFound("job not found")
        return job

    def find_job_by_idempotency(self, key: str) -> Job | None:
        return self.session.scalar(
            select(Job).where(Job.tenant_id == self.tenant_id, Job.idempotency_key == key)
        )

    def list_events(self, job_id: str, after_sequence: int = 0) -> list[JobEvent]:
        self.get_job(job_id)
        statement = (
            select(JobEvent)
            .where(
                JobEvent.tenant_id == self.tenant_id,
                JobEvent.job_id == job_id,
                JobEvent.sequence > after_sequence,
            )
            .order_by(JobEvent.sequence)
        )
        return list(self.session.scalars(statement))

    def next_event_sequence(self, job_id: str) -> int:
        value = self.session.scalar(
            select(func.max(JobEvent.sequence)).where(
                JobEvent.tenant_id == self.tenant_id,
                JobEvent.job_id == job_id,
            )
        )
        return int(value or 0) + 1

