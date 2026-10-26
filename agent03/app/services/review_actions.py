from __future__ import annotations

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.database import AuditLog, FieldCorrection, FieldValue, RiskFinding, utc_now
from app.domain import CaseStatus
from app.repositories import TenantRepository
from app.rules import CaseReviewService
from app.services.errors import Conflict, InvalidInput


class ReviewActionService:
    def __init__(self, session: Session, tenant_id: str, actor_id: str):
        self.session = session
        self.tenant_id = tenant_id
        self.actor_id = actor_id
        self.repo = TenantRepository(session, tenant_id)

    def correct_field(
        self,
        field_id: str,
        expected_version: int,
        normalized_value: str,
        reason: str,
        trace_id: str,
    ) -> FieldValue:
        field = self.repo.get_field(field_id)
        document = self.repo.get_document(field.document_id)
        case = self.repo.get_case(document.case_id)
        if CaseStatus(case.status) != CaseStatus.REVIEW_READY:
            raise Conflict("fields can only be corrected when a case is ready for review")
        corrected = normalized_value.strip()
        explanation = reason.strip()
        if not corrected or not explanation:
            raise InvalidInput("corrected value and reason are required")
        previous = field.normalized_value
        result = self.session.execute(
            update(FieldValue)
            .where(
                FieldValue.id == field.id,
                FieldValue.tenant_id == self.tenant_id,
                FieldValue.version == expected_version,
            )
            .values(
                normalized_value=corrected,
                version=expected_version + 1,
                source="HUMAN",
            )
        )
        if result.rowcount != 1:
            self.session.rollback()
            raise Conflict("field version conflict; refresh and try again")
        self.session.add(
            FieldCorrection(
                tenant_id=self.tenant_id,
                case_id=case.id,
                field_value_id=field.id,
                actor_id=self.actor_id,
                from_version=expected_version,
                to_version=expected_version + 1,
                previous_value=previous,
                corrected_value=corrected,
                reason=explanation,
            )
        )
        case.version += 1
        review = CaseReviewService(self.session, self.tenant_id).run(case.id)
        self._audit(
            "field.correct",
            "field_value",
            field.id,
            trace_id,
            before={"value": previous, "version": expected_version},
            after={
                "value": corrected,
                "version": expected_version + 1,
                "reason": explanation,
                "review_run_group_id": review.run_group_id,
            },
        )
        self.session.commit()
        return self.repo.get_field(field.id)

    def resolve_risk(
        self,
        risk_id: str,
        expected_version: int,
        disposition: str,
        reason: str,
        trace_id: str,
    ) -> RiskFinding:
        risk = self.repo.get_risk(risk_id)
        case = self.repo.get_case(risk.case_id)
        if CaseStatus(case.status) != CaseStatus.REVIEW_READY:
            raise Conflict("risks can only be resolved when a case is ready for review")
        if risk.id not in {item.id for item in CaseReviewService(self.session, self.tenant_id).latest_risks(case.id)}:
            raise Conflict("risk belongs to an outdated review; refresh and try again")
        if disposition not in {"RESOLVED", "ACCEPTED"}:
            raise InvalidInput("disposition must be RESOLVED or ACCEPTED")
        if risk.status != "OPEN":
            raise Conflict("risk has already been processed")
        explanation = reason.strip()
        if not explanation:
            raise InvalidInput("resolution reason is required")
        resolved_at = utc_now()
        result = self.session.execute(
            update(RiskFinding)
            .where(
                RiskFinding.id == risk.id,
                RiskFinding.tenant_id == self.tenant_id,
                RiskFinding.version == expected_version,
                RiskFinding.status == "OPEN",
            )
            .values(
                status=disposition,
                version=expected_version + 1,
                resolution_reason=explanation,
                resolved_by=self.actor_id,
                resolved_at=resolved_at,
            )
        )
        if result.rowcount != 1:
            self.session.rollback()
            raise Conflict("risk version conflict; refresh and try again")
        case.version += 1
        self._audit(
            "risk.resolve",
            "risk_finding",
            risk.id,
            trace_id,
            before={"status": "OPEN", "version": expected_version},
            after={
                "status": disposition,
                "version": expected_version + 1,
                "reason": explanation,
            },
        )
        self.session.commit()
        return self.repo.get_risk(risk.id)

    def _audit(
        self,
        action: str,
        resource_type: str,
        resource_id: str,
        trace_id: str,
        *,
        before: dict,
        after: dict,
    ) -> None:
        self.session.add(
            AuditLog(
                tenant_id=self.tenant_id,
                actor_id=self.actor_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                outcome="success",
                trace_id=trace_id,
                before=before,
                after=after,
            )
        )
