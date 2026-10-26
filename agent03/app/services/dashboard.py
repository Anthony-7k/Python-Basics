from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import (
    Approval,
    Document,
    FieldCorrection,
    Job,
    Report,
    ReviewCase,
    RiskFinding,
    RuleRun,
)
from app.services.errors import InvalidInput


class DashboardService:
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id

    def summary(self, start: date | None = None, end: date | None = None) -> dict:
        if start and end and start > end:
            raise InvalidInput("start date cannot be later than end date")
        statement = select(ReviewCase).where(ReviewCase.tenant_id == self.tenant_id)
        if start:
            statement = statement.where(
                ReviewCase.created_at >= datetime.combine(start, time.min, tzinfo=UTC)
            )
        if end:
            statement = statement.where(
                ReviewCase.created_at <= datetime.combine(end, time.max, tzinfo=UTC)
            )
        cases = list(self.session.scalars(statement))
        case_ids = [case.id for case in cases]
        empty = {
            "period": {"start": start, "end": end},
            "total_cases": 0,
            "status_counts": {},
            "total_documents": 0,
            "total_jobs": 0,
            "job_success_rate": 0.0,
            "average_processing_seconds": 0.0,
            "manual_review_rate": 0.0,
            "rule_hit_rate": 0.0,
            "risk_by_severity": {},
            "risk_by_status": {},
            "approval_counts": {},
            "ready_reports": 0,
        }
        if not case_ids:
            return empty

        jobs = list(
            self.session.scalars(
                select(Job).where(Job.tenant_id == self.tenant_id, Job.case_id.in_(case_ids))
            )
        )
        completed_jobs = [job for job in jobs if job.status in {"SUCCEEDED", "FAILED"}]
        succeeded = sum(job.status == "SUCCEEDED" for job in completed_jobs)
        durations = [
            max(0.0, (job.updated_at - job.created_at).total_seconds()) for job in completed_jobs
        ]
        corrections = set(
            self.session.scalars(
                select(FieldCorrection.case_id).where(
                    FieldCorrection.tenant_id == self.tenant_id,
                    FieldCorrection.case_id.in_(case_ids),
                )
            )
        )
        latest_groups = self._latest_rule_groups(case_ids)
        group_ids = list(latest_groups.values())
        rules = list(
            self.session.scalars(
                select(RuleRun).where(
                    RuleRun.tenant_id == self.tenant_id,
                    RuleRun.run_group_id.in_(group_ids),
                )
            )
        ) if group_ids else []
        risks = list(
            self.session.scalars(
                select(RiskFinding).where(
                    RiskFinding.tenant_id == self.tenant_id,
                    RiskFinding.run_group_id.in_(group_ids),
                )
            )
        ) if group_ids else []
        approvals = list(
            self.session.scalars(
                select(Approval).where(
                    Approval.tenant_id == self.tenant_id,
                    Approval.case_id.in_(case_ids),
                )
            )
        )
        ready_reports = len(
            list(
                self.session.scalars(
                    select(Report.id).where(
                        Report.tenant_id == self.tenant_id,
                        Report.case_id.in_(case_ids),
                        Report.status == "READY",
                    )
                )
            )
        )
        document_count = len(
            list(
                self.session.scalars(
                    select(Document.id).where(
                        Document.tenant_id == self.tenant_id,
                        Document.case_id.in_(case_ids),
                    )
                )
            )
        )
        return {
            "period": {"start": start, "end": end},
            "total_cases": len(cases),
            "status_counts": dict(Counter(case.status for case in cases)),
            "total_documents": document_count,
            "total_jobs": len(jobs),
            "job_success_rate": round(succeeded / len(completed_jobs) * 100, 2)
            if completed_jobs
            else 0.0,
            "average_processing_seconds": round(sum(durations) / len(durations), 3)
            if durations
            else 0.0,
            "manual_review_rate": round(len(corrections) / len(cases) * 100, 2),
            "rule_hit_rate": round(
                sum(rule.outcome == "FAIL" for rule in rules) / len(rules) * 100, 2
            )
            if rules
            else 0.0,
            "risk_by_severity": dict(Counter(risk.severity for risk in risks)),
            "risk_by_status": dict(Counter(risk.status for risk in risks)),
            "approval_counts": dict(Counter(approval.decision for approval in approvals)),
            "ready_reports": ready_reports,
        }

    def _latest_rule_groups(self, case_ids: list[str]) -> dict[str, str]:
        runs = list(
            self.session.scalars(
                select(RuleRun)
                .where(
                    RuleRun.tenant_id == self.tenant_id,
                    RuleRun.case_id.in_(case_ids),
                )
                .order_by(RuleRun.created_at.desc())
            )
        )
        latest = {}
        for run in runs:
            latest.setdefault(run.case_id, run.run_group_id)
        return latest
