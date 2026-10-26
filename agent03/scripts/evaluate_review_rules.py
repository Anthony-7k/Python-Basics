"""Measure risk detection on five fictional cases in an isolated database."""
from __future__ import annotations

import argparse
import json
import tempfile
from contextlib import ExitStack
from pathlib import Path
from time import perf_counter

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def evaluate(fixtures: Path, output: Path):
    manifest = json.loads((fixtures / "审查测试清单.json").read_text(encoding="utf-8"))
    if manifest.get("fictional") is not True:
        raise ValueError("only fictional fixtures are permitted")
    records = []
    with tempfile.TemporaryDirectory(prefix="docflow-eval-") as directory, ExitStack() as stack:
        root = Path(directory)
        settings = Settings(app_env="test", database_url=f"sqlite:///{root / 'eval.db'}",
                            object_storage_path=root / "objects", seed_demo_data=True,
                            auto_create_schema=True, task_queue_backend="eager", virus_scanner_backend="fake",
                            ocr_backend="fake", extraction_backend="deterministic")
        application = create_app(settings)
        stack.callback(application.state.database.engine.dispose)
        with TestClient(application) as client:
            login = client.post("/api/v1/auth/login", json={"email": "demo@docflow.local", "password": "Demo123!"})
            login.raise_for_status()
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            for index, scenario in enumerate(manifest["cases"]):
                started = perf_counter()
                created = client.post("/api/v1/cases", headers=headers, json={"title": scenario["title"]})
                created.raise_for_status()
                case_id = created.json()["id"]
                for relative in scenario["files"]:
                    path = (fixtures / relative).resolve()
                    if fixtures.resolve() not in path.parents:
                        raise ValueError("fixture outside benchmark root")
                    uploaded = client.post(f"/api/v1/cases/{case_id}/documents", headers=headers,
                                           files={"file": (path.name, path.read_bytes(), "application/pdf")})
                    uploaded.raise_for_status()
                submitted = client.post(f"/api/v1/cases/{case_id}/submit",
                                        headers={**headers, "Idempotency-Key": f"eval-{index}"})
                submitted.raise_for_status()
                job = client.get(f"/api/v1/jobs/{submitted.json()['id']}", headers=headers).json()
                risks = client.get(f"/api/v1/cases/{case_id}/risks", headers=headers)
                risks.raise_for_status()
                actual = {risk["risk_type"] for risk in risks.json()}
                expected = set(scenario["expected"])
                records.append({"scenario": scenario["folder"], "job_status": job["status"],
                                "expected": sorted(expected), "actual": sorted(actual),
                                "tp": len(actual & expected), "fp": len(actual - expected), "fn": len(expected - actual),
                                "exact_match": actual == expected and job["status"] == "SUCCEEDED",
                                "latency_ms": round((perf_counter() - started) * 1000, 2)})
    tp, fp, fn = (sum(row[key] for row in records) for key in ("tp", "fp", "fn"))
    precision, recall = tp / (tp + fp) if tp + fp else 0, tp / (tp + fn) if tp + fn else 0
    result = {"dataset": "synthetic-docflow-risk-v1", "samples": len(records),
              "warning": "Five synthetic cases, not real-world risk recall; no OCR or LLM included.",
              "precision": precision, "recall": recall,
              "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0,
              "exact_match_rate": sum(row["exact_match"] for row in records) / len(records), "records": records}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("samples", "precision", "recall", "f1", "exact_match_rate")}))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", type=Path, default=Path("tests/fixtures/demo"))
    parser.add_argument("--output", type=Path, default=Path("eval/results/review-rules.json"))
    args = parser.parse_args()
    evaluate(args.fixtures, args.output)
