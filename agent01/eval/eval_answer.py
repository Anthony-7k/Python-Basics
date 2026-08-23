"""Deterministic Day17 answer, refusal, and citation evaluation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from eval.evaluation_contract import (  # noqa: E402
    category_distribution,
    dataset_sha256,
    load_eval_dataset,
    score_answer_case,
    select_cases,
    split_distribution,
    summarize_answer_results,
)


DEFAULT_DATASET = (
    PROJECT_ROOT / "eval" / "datasets" / "day17_rag_eval_v1.json"
)
DEFAULT_JSON_REPORT = (
    PROJECT_ROOT / "eval" / "results" / "day17_answer_eval.json"
)
DEFAULT_CSV_REPORT = (
    PROJECT_ROOT / "eval" / "results" / "day17_answer_eval.csv"
)
DEFAULT_MARKDOWN_REPORT = (
    PROJECT_ROOT / "docs" / "day17_answer_quality.md"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate Day17 answers with deterministic 0/1/2 rules.",
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--responses-json",
        type=Path,
        help="Replay previously captured answers without network calls.",
    )
    source_group.add_argument(
        "--live",
        action="store_true",
        help=(
            "Call the configured Embedding and LLM services using only the "
            "synthetic employee handbook corpus."
        ),
    )
    parser.add_argument("--split", choices=("all", "dev", "holdout"), default="all")
    parser.add_argument("--mode", choices=("vector", "hybrid", "rerank"), default=None)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--max-distance", type=float, default=1.1)
    parser.add_argument("--json-report", type=Path, default=DEFAULT_JSON_REPORT)
    parser.add_argument("--csv-report", type=Path, default=DEFAULT_CSV_REPORT)
    parser.add_argument(
        "--markdown-report",
        type=Path,
        default=DEFAULT_MARKDOWN_REPORT,
    )
    parser.add_argument("--min-average-score", type=float, default=None)
    parser.add_argument("--min-fact-coverage", type=float, default=None)
    parser.add_argument("--min-fact-consistency", type=float, default=None)
    parser.add_argument("--min-answer-relevance", type=float, default=None)
    parser.add_argument("--min-refusal-accuracy", type=float, default=None)
    parser.add_argument(
        "--min-citation-correctness",
        type=float,
        default=None,
    )
    args = parser.parse_args(argv)
    if args.top_k < 1:
        parser.error("--top-k must be at least 1")
    if args.max_distance <= 0:
        parser.error("--max-distance must be greater than 0")
    if (
        args.min_average_score is not None
        and not 0 <= args.min_average_score <= 2
    ):
        parser.error("--min-average-score must be between 0 and 2")
    for name in (
        "min_fact_coverage",
        "min_fact_consistency",
        "min_answer_relevance",
        "min_refusal_accuracy",
        "min_citation_correctness",
    ):
        value = getattr(args, name)
        if value is not None and not 0 <= value <= 1:
            parser.error(f"--{name.replace('_', '-')} must be between 0 and 1")
    return args


def _load_responses(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        items = payload.get("cases", payload.get("results"))
        if items is None and all(isinstance(value, dict) for value in payload.values()):
            items = [
                {"case_id": case_id, **value}
                for case_id, value in payload.items()
            ]
    else:
        items = payload
    if not isinstance(items, list):
        raise ValueError("responses JSON must be a list or contain cases/results")
    responses = {}
    for item in items:
        case_id = item.get("case_id", item.get("id"))
        if not case_id or case_id in responses:
            raise ValueError("response case_id values must be present and unique")
        responses[str(case_id)] = item
    return responses


def _source_dict(source: Any) -> dict[str, Any]:
    if isinstance(source, dict):
        return source
    return {
        "source_id": getattr(source, "source_id", None),
        "chunk_id": getattr(source, "chunk_id", None),
        "file_name": getattr(source, "file_name", None),
        "content": getattr(source, "content", ""),
    }


def _evaluate_saved(
    cases: list[dict],
    responses_path: Path,
) -> list[dict]:
    responses = _load_responses(responses_path)
    missing = [case["case_id"] for case in cases if case["case_id"] not in responses]
    if missing:
        raise ValueError(
            "responses JSON is missing cases: " + ", ".join(missing)
        )

    results = []
    for case in cases:
        response = responses[case["case_id"]]
        result = score_answer_case(
            case,
            str(response.get("answer", "")),
            response.get("sources", []),
        )
        result["latency_ms"] = response.get("latency_ms")
        result["error"] = response.get("error")
        results.append(result)
    return results


def _evaluate_live(
    cases: list[dict],
    *,
    mode_override: str | None,
    top_k: int,
    max_distance: float,
) -> list[dict]:
    from app.prompts.rag_prompt import SYSTEM_PROMPT, build_user_prompt
    from app.services.llm.llm_client import generate_answer
    from app.services.rag.rag_service import build_context
    from app.services.retrieval.retriever import retrieve
    from eval.eval_retrieval import _seed_corpus
    import app.services.vector_stores.vector_store as vector_store

    knowledge_base_id = "day17-answer-eval-kb"
    document_id = "day17-answer-eval-employee-handbook"
    vector_store.delete_by_document(knowledge_base_id, document_id)
    _seed_corpus(
        corpus_path=None,
        knowledge_base_id=knowledge_base_id,
        document_id=document_id,
    )
    results = []
    try:
        for case in cases:
            started_at = time.perf_counter()
            error = None
            answer = ""
            sources = []
            try:
                items = retrieve(
                    query_text=case["standalone_question"],
                    knowledge_base_id=knowledge_base_id,
                    top_k=top_k,
                    max_distance=max_distance,
                    mode=(
                        mode_override
                        or case.get("retrieval", {}).get("mode", "vector")
                    ),
                )
                context, raw_sources = build_context(items)
                if not context.strip():
                    answer = "知识库中没有足够的信息回答这个问题。"
                else:
                    answer = generate_answer(
                        system_prompt=SYSTEM_PROMPT,
                        user_prompt=build_user_prompt(
                            question=case["question"],
                            standalone_question=case["standalone_question"],
                            context=context,
                        ),
                    )
                sources = [
                    {
                        "source_id": source["source_id"],
                        "chunk_id": source["chunk_id"],
                        "file_name": source["metadata"].get("source"),
                        "content": source["content"],
                    }
                    for source in raw_sources
                ]
            except Exception as exc:  # keep partial runs auditable
                error = f"{type(exc).__name__}: {exc}"
            result = score_answer_case(case, answer, sources)
            result["latency_ms"] = round(
                (time.perf_counter() - started_at) * 1000,
                2,
            )
            result["error"] = error
            results.append(result)
            print(
                f"[{result['manual_score']}] {case['case_id']} "
                f"{case['question']}"
            )
    finally:
        vector_store.delete_by_document(knowledge_base_id, document_id)
    return results


def _prompt_metadata() -> dict[str, str]:
    prompt_path = PROJECT_ROOT / "app" / "prompts" / "rag_prompt.py"
    return {
        "version": "rag-prompt-day14-v1",
        "sha256": hashlib.sha256(prompt_path.read_bytes()).hexdigest(),
    }


def evaluate_gates(summary: dict, thresholds: dict[str, float]) -> list[str]:
    labels = {
        "average_manual_score": "平均人工规则分",
        "average_fact_coverage": "事实覆盖率",
        "fact_consistency": "事实一致率",
        "answer_relevance": "回答相关率",
        "refusal_accuracy": "拒答准确率",
        "citation_correctness": "引用正确率",
    }
    failures = []
    for metric, minimum in thresholds.items():
        actual = summary[metric]
        if actual is None or actual < minimum:
            actual_text = "N/A" if actual is None else f"{actual:.4f}"
            failures.append(
                f"{labels[metric]}={actual_text} < {minimum:.4f}"
            )
    return failures


def _format_rate(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2%}"


def build_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Day17 回答质量评测报告",
        "",
        f"- 数据集：`{report['dataset_name']}` / `{report['dataset_version']}`",
        f"- 数据集 SHA-256：`{report['dataset_sha256']}`",
        f"- 运行时间：{report['generated_at']}",
        f"- 运行方式：`{report['evaluation_backend']}`",
        f"- 分片：`{report['split']}`，样本数：{summary['case_count']}",
        f"- LLM：`{report['llm_model']}`",
        f"- Embedding：`{report['embedding_model']}`",
        f"- Prompt：`{report['prompt']['version']}`",
        "",
        "## 汇总",
        "",
        f"- 平均 0/1/2 分：{summary['average_manual_score']:.4f}",
        f"- 事实覆盖率：{_format_rate(summary['average_fact_coverage'])}",
        f"- 事实一致率：{_format_rate(summary['fact_consistency'])}",
        f"- 回答相关率：{_format_rate(summary['answer_relevance'])}",
        f"- 拒答准确率：{_format_rate(summary['refusal_accuracy'])}",
        f"- 引用正确率：{_format_rate(summary['citation_correctness'])}",
        (
            f"- 平均回答耗时：{summary['average_latency_ms']:.2f} ms"
            if summary["average_latency_ms"] is not None
            else "- 平均回答耗时：N/A"
        ),
        (
            f"- P95 回答耗时：{summary['p95_latency_ms']:.2f} ms"
            if summary["p95_latency_ms"] is not None
            else "- P95 回答耗时：N/A"
        ),
        f"- 分数分布：`{json.dumps(summary['score_distribution'], ensure_ascii=False)}`",
        "",
        "## 0/1/2 人工复核标准",
        "",
        "- 0：错误、关键事实矛盾、应拒答却编造，或引用无法支持结论。",
        "- 1：部分正确但遗漏重要条件，或引用只支持部分结论。",
        "- 2：关键事实完整、边界明确、回答相关，且引用可追溯。",
        "",
        "## 独立引用规则",
        "",
        "- 回答中的每个 [S<n>] 必须对应返回的 source_id。",
        "- 至少一个实际引用来源必须匹配期望文件并包含期望证据。",
        "- 答案正确不自动代表引用正确；二者分别统计。",
        "- 信息不足题应明确拒答，不要求引用；带引用的拒答最多记 1 分。",
        "",
        "## 失败样例",
        "",
        (
            ", ".join(summary["failed_case_ids"])
            if summary["failed_case_ids"] else "无"
        ),
        "",
        "## 回归门槛",
        "",
    ]
    if report["thresholds"]:
        lines.append(
            f"- 配置：`{json.dumps(report['thresholds'], ensure_ascii=False)}`"
        )
        lines.append(
            "- 结果：" + ("通过" if not report["gate_failures"] else "失败")
        )
        for failure in report["gate_failures"]:
            lines.append(f"  - {failure}")
    else:
        lines.append("- 本次未启用门槛；传入 --min-* 参数后失败会返回非零状态。")
    lines.extend(
        [
            "",
            "## 限制",
            "",
            "- 字符串规则适合稳定回归，但同义改写可能需要人工复核。",
            "- LLM-as-judge 未启用；若未来加入，只能作为辅助且不得覆盖确定性失败。",
            "- 重放报告只证明所保存响应的质量，不代表当前线上模型状态。",
            "- Dev 可用于调参；Holdout 不应被用于反向修改检索或提示词。",
            "",
        ]
    )
    return "\n".join(lines)


def write_csv(path: Path, results: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "case_id",
        "split",
        "category",
        "answerable",
        "manual_score",
        "fact_coverage",
        "fact_consistent",
        "answer_relevant",
        "refusal_correct",
        "citation_correct",
        "latency_ms",
        "matched_facts",
        "missing_facts",
        "forbidden_fact_hits",
        "citation_ids",
        "answer",
        "error",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    key: (
                        json.dumps(result[key], ensure_ascii=False)
                        if isinstance(result.get(key), list)
                        else result.get(key)
                    )
                    for key in fieldnames
                }
            )


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    dataset_path = args.dataset.resolve()
    metadata, all_cases = load_eval_dataset(dataset_path)
    cases = select_cases(all_cases, args.split)
    if not cases:
        raise ValueError(f"dataset split {args.split!r} is empty")

    from app.core import settings

    if args.live:
        results = _evaluate_live(
            cases,
            mode_override=args.mode,
            top_k=args.top_k,
            max_distance=args.max_distance,
        )
        evaluation_backend = "configured-live-embedding-and-llm"
        llm_model = settings.LLM_MODEL or "unconfigured"
        embedding_model = settings.EMBEDDING_MODEL or "unconfigured"
        response_capture = None
    else:
        responses_path = args.responses_json.resolve()
        results = _evaluate_saved(cases, responses_path)
        raw = json.loads(responses_path.read_text(encoding="utf-8"))
        recorded_backend = (
            raw.get("evaluation_backend")
            if isinstance(raw, dict)
            else None
        )
        evaluation_backend = (
            f"replay:{recorded_backend}"
            if recorded_backend
            else f"saved-responses:{responses_path.name}"
        )
        llm_model = (
            raw.get("llm_model", "recorded-unspecified")
            if isinstance(raw, dict)
            else "recorded-unspecified"
        )
        embedding_model = (
            raw.get("embedding_model", "recorded-unspecified")
            if isinstance(raw, dict)
            else "recorded-unspecified"
        )
        response_capture = {
            "path": str(responses_path),
            "sha256": dataset_sha256(responses_path),
            "generated_at": (
                raw.get("generated_at")
                if isinstance(raw, dict)
                else None
            ),
        }

    summary = summarize_answer_results(results)
    thresholds = {
        key: value
        for key, value in {
            "average_manual_score": args.min_average_score,
            "average_fact_coverage": args.min_fact_coverage,
            "fact_consistency": args.min_fact_consistency,
            "answer_relevance": args.min_answer_relevance,
            "refusal_accuracy": args.min_refusal_accuracy,
            "citation_correctness": args.min_citation_correctness,
        }.items()
        if value is not None
    }
    gate_failures = evaluate_gates(summary, thresholds)
    errors = [result["case_id"] for result in results if result.get("error")]
    if errors:
        gate_failures.append("运行错误样例: " + ", ".join(errors))

    generated_at = datetime.now(timezone.utc).isoformat()
    report = {
        "generated_at": generated_at,
        "evaluation_date": generated_at[:10],
        "evaluation_backend": evaluation_backend,
        "dataset": str(dataset_path),
        "dataset_name": metadata["dataset_name"],
        "dataset_version": metadata["dataset_version"],
        "dataset_schema_version": metadata["schema_version"],
        "dataset_sha256": dataset_sha256(dataset_path),
        "split": args.split,
        "split_policy": metadata.get("split_policy"),
        "category_distribution": category_distribution(cases),
        "split_distribution": split_distribution(cases),
        "llm_model": llm_model,
        "embedding_model": embedding_model,
        "prompt": _prompt_metadata(),
        "response_capture": response_capture,
        "chunking": {"chunk_size": 500, "chunk_overlap": 50},
        "retrieval": {
            "mode_override": args.mode,
            "top_k": args.top_k,
            "max_distance": args.max_distance,
            "redis_cache_used": False,
        },
        "thresholds": thresholds,
        "gate_failures": gate_failures,
        "summary": summary,
        "cases": results,
    }

    for path in (args.json_report, args.markdown_report, args.csv_report):
        path.parent.mkdir(parents=True, exist_ok=True)
    args.json_report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    args.markdown_report.write_text(build_markdown(report), encoding="utf-8")
    write_csv(args.csv_report, results)

    print(
        f"AverageScore={summary['average_manual_score']:.4f}",
        f"FactCoverage={_format_rate(summary['average_fact_coverage'])}",
        f"FactConsistency={_format_rate(summary['fact_consistency'])}",
        f"Relevance={_format_rate(summary['answer_relevance'])}",
        f"Refusal={_format_rate(summary['refusal_accuracy'])}",
        f"Citation={_format_rate(summary['citation_correctness'])}",
    )
    for failure in gate_failures:
        print(f"GATE FAIL: {failure}", file=sys.stderr)
    return 1 if gate_failures else 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
