import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.schemas.agent import AgentRequest
from app.services.agent.router import (
    DeterministicAgentRouter,
)


DEFAULT_DATASET = (
    PROJECT_ROOT
    / "eval"
    / "datasets"
    / "day19_agent_routing.json"
)


def evaluate(dataset_path: Path) -> tuple[int, int]:
    cases = json.loads(
        dataset_path.read_text(encoding="utf-8")
    )
    router = DeterministicAgentRouter()
    correct = 0

    for case in cases:
        plan = router.route(
            AgentRequest(
                knowledge_base_id="eval-kb",
                instruction=case["instruction"],
                document_ids=case["document_ids"],
            )
        )
        actual_tool = (
            plan.tool_calls[0].tool_name.value
            if plan.tool_calls
            else None
        )
        matched = (
            plan.status.value == case["expected_status"]
            and actual_tool == case["expected_tool"]
        )
        correct += int(matched)
        if not matched:
            print(
                f"FAIL {case['id']}: "
                f"status={plan.status.value}, tool={actual_tool}; "
                f"expected_status={case['expected_status']}, "
                f"expected_tool={case['expected_tool']}"
            )

    return correct, len(cases)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
    )
    parser.add_argument(
        "--min-correct",
        type=int,
        default=10,
    )
    args = parser.parse_args()

    correct, total = evaluate(args.dataset)
    print(
        f"Agent routing accuracy: {correct}/{total} "
        f"({correct / total:.2%})"
    )
    if correct < args.min_correct:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
