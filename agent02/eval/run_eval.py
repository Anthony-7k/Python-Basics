from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from time import perf_counter
from uuid import uuid4

from app.config import Settings
from app.database import Database
from app.domain import AgentRequest
from app.service import AgentService
from app.tools import build_tool_registry

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "eval" / "datasets" / "portfolio_mvp.json"
DEFAULT_OUTPUT = ROOT / "eval" / "results" / "latest.json"


async def evaluate(dataset_path: Path) -> dict:
    raw_dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    if isinstance(raw_dataset, dict):
        cases = []
        if raw_dataset.get("extends"):
            parent = dataset_path.parent / raw_dataset["extends"]
            parent_data = json.loads(parent.read_text(encoding="utf-8"))
            if not isinstance(parent_data, list):
                raise ValueError("Extended evaluation dataset must be a JSON list")
            cases.extend(parent_data)
        cases.extend(raw_dataset.get("cases", []))
    else:
        cases = raw_dataset
    database = Database("sqlite://")
    database.create_all()
    base_settings = Settings(
        database_url="sqlite://",
        planner_mode="rule_based",
        knowledge_backend="sample",
        log_level="WARNING",
    )
    registry = build_tool_registry(base_settings)
    details = []
    tool_expected = 0
    tool_correct = 0
    tool_executions = 0
    tool_execution_successes = 0
    latencies = []
    steps = []
    token_totals = []

    for case in cases:
        settings = base_settings.model_copy(
            update={"tool_max_retries": case.get("tool_max_retries", 2)}
        )
        session = database.session_factory()
        service = AgentService(session, settings, registry=registry)
        request = AgentRequest(
            message=case["message"],
            user_id=f"eval-{case['id']}",
            session_id=f"session-{case['id']}",
            max_steps=case.get("max_steps"),
        )
        started = perf_counter()
        response = await service.run(request, f"eval-{uuid4()}")
        if case.get("approval_action") == "approve":
            response = await service.approve(
                response.task_id,
                request.user_id,
                case.get("modified_payload"),
            )
        elif case.get("approval_action") == "reject":
            response = service.reject(
                response.task_id, request.user_id, "Rejected by evaluation case"
            )
        if case.get("resume_on_failure"):
            response = await service.resume(response.task_id, request.user_id)
        latency_ms = (perf_counter() - started) * 1000
        actual_tools = [call.name for call in response.tool_calls]
        expected_tools = case.get("expected_tools", [])
        status_ok = response.status.value == case["expected_status"]
        tools_ok = actual_tools == expected_tools
        answer_marker = case.get("answer_contains")
        answer_ok = not answer_marker or answer_marker in response.answer
        passed = status_ok and tools_ok and answer_ok
        if "expected_tools" in case:
            tool_expected += 1
            tool_correct += int(tools_ok)
        tool_executions += len(response.tool_results)
        tool_execution_successes += sum(
            int(result.success) for result in response.tool_results
        )
        latencies.append(latency_ms)
        steps.append(response.current_step)
        total_tokens = response.token_usage.total_tokens
        if total_tokens is not None:
            token_totals.append(total_tokens)
        details.append(
            {
                "id": case["id"],
                "category": case["category"],
                "passed": passed,
                "expected_status": case["expected_status"],
                "actual_status": response.status.value,
                "expected_tools": expected_tools,
                "actual_tools": actual_tools,
                "answer_ok": answer_ok,
                "latency_ms": round(latency_ms, 3),
                "steps": response.current_step,
                "retry_count": sum(r.retry_count for r in response.tool_results),
                "error_type": response.error.error_type if response.error else None,
            }
        )
        session.close()

    passed_count = sum(int(item["passed"]) for item in details)
    return {
        "dataset": dataset_path.name,
        "dataset_size": len(cases),
        "generated_at": datetime.now(UTC).isoformat(),
        "configuration": {
            "planner_mode": "rule_based",
            "knowledge_backend": "sample",
            "agent_max_steps": base_settings.agent_max_steps,
            "tool_timeout_seconds": base_settings.tool_timeout_seconds,
        },
        "metrics": {
            "task_success_rate": passed_count / len(cases) if cases else 0,
            "tool_selection_accuracy": tool_correct / tool_expected
            if tool_expected
            else None,
            "tool_execution_success_rate": (
                tool_execution_successes / tool_executions if tool_executions else None
            ),
            "average_steps": mean(steps) if steps else 0,
            "average_token_usage": mean(token_totals) if token_totals else None,
            "average_latency_ms": mean(latencies) if latencies else 0,
        },
        "passed": passed_count,
        "failed": len(cases) - passed_count,
        "cases": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = asyncio.run(evaluate(args.dataset))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result["metrics"], ensure_ascii=False, indent=2))
    print(f"passed={result['passed']} failed={result['failed']}")
    if result["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
