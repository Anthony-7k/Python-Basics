from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Approval, AuditLog, RiskFinding
from app.domain import CaseStatus, transition_case
from app.repositories import TenantRepository
from app.rules import CaseReviewService
from app.services.errors import Conflict, InvalidInput


class ApprovalService:
    def __init__(self, session: Session, tenant_id: str, actor_id: str):
        self.session = session
        self.tenant_id = tenant_id
        self.actor_id = actor_id
        self.repo = TenantRepository(session, tenant_id)

    def decide(
        self,
        case_id: str,
        expected_version: int,
        decision: str,
        reason: str,
        trace_id: str,
    ) -> Approval:
        case = self.repo.get_case(case_id)
        if case.version != expected_version:
            raise Conflict("case version conflict; refresh and try again")
        if CaseStatus(case.status) != CaseStatus.REVIEW_READY:
            raise Conflict("case is not ready for approval")
        if decision not in {"APPROVED", "REJECTED"}:
            raise InvalidInput("decision must be APPROVED or REJECTED")
        explanation = reason.strip()
        if not explanation:
            raise InvalidInput("approval reason is required")
        if decision == "APPROVED":
            group = CaseReviewService(self.session, self.tenant_id).latest_run_group(case.id)
            if group is None:
                raise Conflict("case has no completed review; run review before approval")
            open_high = self.session.scalar(
                select(func.count(RiskFinding.id)).where(
                    RiskFinding.tenant_id == self.tenant_id,
                    RiskFinding.case_id == case.id,
                    RiskFinding.run_group_id == group,
                    RiskFinding.status == "OPEN",
                    RiskFinding.severity == "HIGH",
                )
            )
            if open_high:
                raise Conflict("all high risks must be resolved or accepted before approval")
        target = CaseStatus.APPROVED if decision == "APPROVED" else CaseStatus.REJECTED
        case.status = transition_case(case.status, target).value
        case.version += 1
        approval = Approval(
            tenant_id=self.tenant_id,
            case_id=case.id,
            decision=decision,
            reason=explanation,
            actor_id=self.actor_id,
            case_version=expected_version,
        )
        self.session.add(approval)
        self.session.add(
            AuditLog(
                tenant_id=self.tenant_id,
                actor_id=self.actor_id,
                action="case.approve",
                resource_type="case",
                resource_id=case.id,
                outcome="success",
                trace_id=trace_id,
                before={"status": CaseStatus.REVIEW_READY.value, "version": expected_version},
                after={"status": case.status, "version": case.version, "reason": explanation},
            )
        )
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise Conflict("this case version already has an approval decision") from exc
        return approval
