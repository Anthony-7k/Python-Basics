import pytest

from app.domain import CaseStatus, InvalidTransition, transition_case


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (CaseStatus.DRAFT, CaseStatus.QUEUED),
        (CaseStatus.QUEUED, CaseStatus.PROCESSING),
        (CaseStatus.PROCESSING, CaseStatus.REVIEW_READY),
        (CaseStatus.PROCESSING, CaseStatus.FAILED),
        (CaseStatus.FAILED, CaseStatus.QUEUED),
        (CaseStatus.REVIEW_READY, CaseStatus.APPROVED),
        (CaseStatus.REVIEW_READY, CaseStatus.REJECTED),
    ],
)
def test_allowed_transitions(current, target):
    assert transition_case(current, target) == target


def test_rejects_illegal_transition():
    with pytest.raises(InvalidTransition):
        transition_case(CaseStatus.DRAFT, CaseStatus.REVIEW_READY)

