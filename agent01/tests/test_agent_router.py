import json
from pathlib import Path

from app.schemas.agent import AgentRequest
from app.services.agent.router import (
    DeterministicAgentRouter,
)


DATASET = (
    Path(__file__).parents[1]
    / "eval"
    / "datasets"
    / "day19_agent_routing.json"
)


def test_day19_router_selects_at_least_ten_of_twelve_cases():
    cases = json.loads(
        DATASET.read_text(encoding="utf-8")
    )
    router = DeterministicAgentRouter()
    failures = []

    for case in cases:
        plan = router.route(
            AgentRequest(
                knowledge_base_id="test-kb",
                instruction=case["instruction"],
                document_ids=case["document_ids"],
            )
        )
        actual_tool = (
            plan.tool_calls[0].tool_name.value
            if plan.tool_calls
            else None
        )
        if not (
            plan.status.value == case["expected_status"]
            and actual_tool == case["expected_tool"]
        ):
            failures.append(
                {
                    "id": case["id"],
                    "actual_status": plan.status.value,
                    "actual_tool": actual_tool,
                }
            )

    assert len(cases) == 12
    assert len(cases) - len(failures) >= 10, failures


def test_document_evidence_never_creates_additional_tool_calls():
    plan = DeterministicAgentRouter().route(
        AgentRequest(
            knowledge_base_id="test-kb",
            instruction="这份制度规定了哪些报销条件？",
            document_ids=[],
        )
    )

    assert len(plan.tool_calls) == 1
    assert plan.tool_calls[0].tool_name.value == (
        "search_knowledge"
    )
