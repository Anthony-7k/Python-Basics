from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from app.agent.planner import OpenAICompatiblePlanner
from app.config import Settings
from app.tools import build_tool_registry

ROOT = Path(__file__).resolve().parents[1]


async def run(dataset: Path) -> dict:
    settings = Settings(planner_mode="openai")
    settings.validate_runtime()
    planner = OpenAICompatiblePlanner(settings)
    schemas = build_tool_registry(settings).schemas()
    cases = json.loads(dataset.read_text(encoding="utf-8"))
    details = []
    for case in cases:
        started = perf_counter()
        result = await planner.plan(case["message"], schemas)
        actual = [call.name for call in result.tool_calls]
        details.append(
            {
                "id": case["id"],
                "passed": actual == case["expected_tools"],
                "expected_tools": case["expected_tools"],
                "actual_tools": actual,
                "latency_ms": round((perf_counter() - started) * 1000, 3),
                "token_usage": result.token_usage.model_dump(mode="json"),
                "estimated_cost_usd": result.estimated_cost_usd,
            }
        )
    passed = sum(item["passed"] for item in details)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "model": settings.llm_model,
        "dataset_size": len(details),
        "passed": passed,
        "failed": len(details) - passed,
        "tool_selection_accuracy": passed / len(details) if details else 0,
        "cases": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=ROOT / "eval" / "datasets" / "live_week2.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "eval" / "results" / "live_week2.json",
    )
    args = parser.parse_args()
    result = asyncio.run(run(args.dataset))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "dataset_size",
                    "passed",
                    "failed",
                    "tool_selection_accuracy",
                )
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if result["tool_selection_accuracy"] < 0.9:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
