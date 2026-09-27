from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_check(
    name: str, command: list[str], *, env: dict[str, str] | None = None
) -> dict:
    started = datetime.now(UTC)
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "name": name,
        "passed": completed.returncode == 0,
        "exit_code": completed.returncode,
        "duration_seconds": round((datetime.now(UTC) - started).total_seconds(), 3),
        "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-2000:],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "eval" / "results" / "week2-acceptance.json",
    )
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args()

    python = sys.executable
    checks = [
        run_check("ruff", [python, "-m", "ruff", "check", "."]),
        run_check("format", [python, "-m", "ruff", "format", "--check", "."]),
    ]
    if not args.skip_tests:
        checks.append(
            run_check(
                "tests",
                [
                    python,
                    "-m",
                    "pytest",
                    "-p",
                    "no:cacheprovider",
                    "--basetemp=data/pytest-acceptance",
                    "--cov=app",
                    "--cov-report=term-missing",
                    "--cov-fail-under=90",
                    "-q",
                ],
            )
        )
    checks.append(
        run_check(
            "week2-evaluation",
            [
                python,
                "-m",
                "eval.run_eval",
                "--dataset",
                "eval/datasets/week2.json",
                "--output",
                "eval/results/week2.json",
            ],
        )
    )
    with tempfile.TemporaryDirectory(prefix="agent02-acceptance-") as temp_dir:
        database_path = Path(temp_dir) / "acceptance.db"
        migration_env = os.environ.copy()
        migration_env.update(
            {
                "APP_ENV": "integration",
                "DATABASE_URL": f"sqlite:///{database_path.as_posix()}",
            }
        )
        checks.append(
            run_check(
                "empty-database-migration",
                [python, "scripts/migrate.py"],
                env=migration_env,
            )
        )

    web_dist = ROOT / "web" / "dist" / "index.html"
    checks.append(
        {
            "name": "web-build-artifact",
            "passed": web_dist.is_file(),
            "exit_code": 0 if web_dist.is_file() else 1,
            "duration_seconds": 0,
            "stdout_tail": str(web_dist),
            "stderr_tail": "" if web_dist.is_file() else "Run pnpm --dir web build",
        }
    )
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
        "external_credentials": {
            "live_llm_evaluation": "not_run_by_offline_acceptance",
            "agent01_evaluation": "not_run_by_offline_acceptance",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "checks": [
                    {"name": item["name"], "passed": item["passed"]} for item in checks
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
