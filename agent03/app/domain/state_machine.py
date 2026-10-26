from app.domain.enums import CaseStatus


class InvalidTransition(ValueError):
    pass


ALLOWED_TRANSITIONS: dict[CaseStatus, set[CaseStatus]] = {
    CaseStatus.DRAFT: {CaseStatus.QUEUED, CaseStatus.ARCHIVED},
    CaseStatus.QUEUED: {CaseStatus.PROCESSING, CaseStatus.FAILED},
    CaseStatus.PROCESSING: {CaseStatus.REVIEW_READY, CaseStatus.FAILED},
    CaseStatus.FAILED: {CaseStatus.QUEUED, CaseStatus.ARCHIVED},
    CaseStatus.REVIEW_READY: {CaseStatus.APPROVED, CaseStatus.REJECTED, CaseStatus.ARCHIVED},
    CaseStatus.APPROVED: {CaseStatus.ARCHIVED},
    CaseStatus.REJECTED: {CaseStatus.ARCHIVED},
    CaseStatus.ARCHIVED: set(),
}


def transition_case(current: CaseStatus | str, target: CaseStatus | str) -> CaseStatus:
    current_status = CaseStatus(current)
    target_status = CaseStatus(target)
    if target_status not in ALLOWED_TRANSITIONS[current_status]:
        raise InvalidTransition(f"cannot transition case from {current_status} to {target_status}")
    return target_status

