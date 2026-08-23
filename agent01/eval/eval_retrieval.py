"""Versioned retrieval evaluation for vector, hybrid, and rerank modes."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from eval.evaluation_contract import (  # noqa: E402
    case_query,
    category_distribution,
    dataset_sha256,
    load_eval_dataset,
    retrieval_match_ranks,
    select_cases,
    split_distribution,
)


DEFAULT_DATASET = (
    PROJECT_ROOT / "eval" / "datasets" / "day17_rag_eval_v1.json"
)
DEFAULT_JSON_REPORT = (
    PROJECT_ROOT / "eval" / "results" / "day17_retrieval_eval.json"
)
DEFAULT_CSV_REPORT = (
    PROJECT_ROOT / "eval" / "results" / "day17_retrieval_eval.csv"
)
DEFAULT_MARKDOWN_REPORT = (
    PROJECT_ROOT / "docs" / "day17_retrieval_quality.md"
)
LEGACY_DATASET_PATH = (
    PROJECT_ROOT / "eval" / "datasets" / "retrieval_questions.jsonl"
)


def load_dataset() -> list[dict]:
    """Preserve the pre-Day16 JSONL loader for interactive callers."""
    dataset = []
    with LEGACY_DATASET_PATH.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                dataset.append(json.loads(line))
    return dataset


def preview_retrieval(top_k: int = 3) -> None:
    """Preserve the original interactive retrieval preview."""
    from app.services.retrieval.retriever import retrieve

    for item in load_dataset():
        results = retrieve(
            query_text=item["question"],
            knowledge_base_id=os.environ["KNOWLEDGE_BASE_ID"],
            top_k=top_k,
        )
        print(f"\n{'=' * 60}")
        print(f"题目 {item['id']}：{item['question']}")
        for index, result in enumerate(results, start=1):
            print(
                f"Top {index} | distance={result.get('distance')} | "
                f"chunk_id={result['chunk_id']}"
            )
            print(result["content"][:100])


def evaluate_retrieval(top_k: int = 3) -> None:
    """Preserve the original lightweight recall entry point."""
    from app.services.retrieval.retriever import retrieve

    answerable = [
        item for item in load_dataset()
        if item["expected_keyword"] is not None
    ]
    hits = 0
    for item in answerable:
        results = retrieve(
            query_text=item["question"],
            knowledge_base_id=os.environ["KNOWLEDGE_BASE_ID"],
            top_k=top_k,
        )
        hit = any(
            item["expected_keyword"] in result["content"]
            for result in results
        )
        hits += int(hit)
        print(f"{'HIT' if hit else 'MISS'} | {item['question']}")
    recall = hits / len(answerable) if answerable else 0
    print(f"Recall@{top_k}: {recall:.2%}")


def evaluate_unanswerable(
    top_k: int = 3,
    max_distance: float = 1.0,
) -> None:
    """Preserve the original unanswerable entry point."""
    from app.services.retrieval.retriever import retrieve

    cases = [
        item for item in load_dataset()
        if item["type"] == "unanswerable"
    ]
    passed = sum(
        not retrieve(
            query_text=item["question"],
            knowledge_base_id=os.environ["KNOWLEDGE_BASE_ID"],
            top_k=top_k,
            max_distance=max_distance,
        )
        for item in cases
    )
    rate = passed / len(cases) if cases else 0
    print(f"拒答前置过滤率: {rate:.2%}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate the versioned Day17 retrieval suite.",
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--corpus-json", type=Path, default=None)
    parser.add_argument(
        "--json-report",
        "--output",
        dest="json_report",
        type=Path,
        default=DEFAULT_JSON_REPORT,
    )
    parser.add_argument(
        "--markdown-report",
        "--report",
        dest="markdown_report",
        type=Path,
        default=DEFAULT_MARKDOWN_REPORT,
    )
    parser.add_argument(
        "--csv-report",
        type=Path,
        default=DEFAULT_CSV_REPORT,
    )
    parser.add_argument("--split", choices=("all", "dev", "holdout"), default="all")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--max-distance", type=float, default=None)
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=("vector", "hybrid", "rerank"),
        default=("vector", "hybrid", "rerank"),
    )
    parser.add_argument(
        "--live-embedding",
        action="store_true",
        help="Use the configured external embedding endpoint.",
    )
    parser.add_argument("--min-recall-at-k", type=float, default=None)
    parser.add_argument("--min-mrr", type=float, default=None)
    parser.add_argument(
        "--min-no-answer-accuracy",
        type=float,
        default=None,
    )
    args = parser.parse_args(argv)
    if args.top_k < 1:
        parser.error("--top-k must be at least 1")
    for name in (
        "min_recall_at_k",
        "min_mrr",
        "min_no_answer_accuracy",
    ):
        value = getattr(args, name)
        if value is not None and not 0 <= value <= 1:
            parser.error(f"--{name.replace('_', '-')} must be between 0 and 1")
    return args


def load_cases(path: Path) -> list[dict]:
    """Compatibility wrapper used by tests and earlier imports."""
    _, cases = load_eval_dataset(path)
    return cases


def offline_embed_texts(texts: list[str]) -> list[list[float]]:
    """Return deterministic hashed token vectors for engineering regression."""
    from app.core.settings import EMBEDDING_DIMENSIONS
    from app.services.retrieval.keyword_retriever import tokenize

    embeddings = []
    for value in texts:
        vector = [0.0] * EMBEDDING_DIMENSIONS
        for token in tokenize(value):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS
            vector[index] += 1.0 if digest[4] % 2 == 0 else -1.0
        norm = math.sqrt(sum(item * item for item in vector))
        if norm:
            vector = [item / norm for item in vector]
        embeddings.append(vector)
    return embeddings


def _p95(values: list[float]) -> float:
    index = max(0, math.ceil(len(values) * 0.95) - 1)
    return sorted(values)[index]


def evaluate_mode(
    *,
    mode: str,
    cases: list[dict],
    knowledge_base_id: str,
    top_k: int,
    max_distance: float,
) -> dict[str, Any]:
    from app.services.retrieval.retriever import retrieve

    case_results = []
    latencies = []
    for case in cases:
        started_at = time.perf_counter()
        items = retrieve(
            query_text=case_query(case),
            knowledge_base_id=knowledge_base_id,
            top_k=top_k,
            max_distance=max_distance,
            mode=mode,
        )
        latency_ms = (time.perf_counter() - started_at) * 1000
        latencies.append(latency_ms)
        ranks = retrieval_match_ranks(case, items)
        hit = bool(ranks) if case["answerable"] else not items
        case_results.append(
            {
                "case_id": case["case_id"],
                "split": case["split"],
                "category": case["category"],
                "question": case["question"],
                "standalone_question": case_query(case),
                "answerable": case["answerable"],
                "hit": hit,
                "first_relevant_rank": min(ranks) if ranks else None,
                "reciprocal_rank": round(1 / min(ranks), 4) if ranks else 0.0,
                "latency_ms": round(latency_ms, 2),
                "retrieved_chunk_ids": [
                    item["chunk_id"] for item in items
                ],
                "top_contents": [
                    item["content"][:160] for item in items
                ],
                "rerank_candidate_count": (
                    items[0].get("rerank_candidate_count", 0)
                    if items else 0
                ),
                "risk": case.get("retrieval", {}).get("risk"),
            }
        )

    answerable = [
        result for result in case_results if result["answerable"]
    ]
    no_answer = [
        result for result in case_results if not result["answerable"]
    ]
    return {
        "mode": mode,
        "recall_at_k": round(
            sum(result["hit"] for result in answerable) / len(answerable),
            4,
        ) if answerable else None,
        "mrr": round(
            sum(result["reciprocal_rank"] for result in answerable)
            / len(answerable),
            4,
        ) if answerable else None,
        "no_answer_accuracy": round(
            sum(result["hit"] for result in no_answer) / len(no_answer),
            4,
        ) if no_answer else None,
        "average_retrieval_ms": round(statistics.mean(latencies), 2),
        "p95_retrieval_ms": round(_p95(latencies), 2),
        "average_rerank_candidate_count": round(
            statistics.mean(
                result["rerank_candidate_count"]
                for result in case_results
            ),
            2,
        ),
        "cases": case_results,
    }


def _format_rate(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2%}"


def build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Day17 检索评测报告",
        "",
        f"- 数据集：`{report['dataset_name']}` / `{report['dataset_version']}`",
        f"- 数据集 SHA-256：`{report['dataset_sha256']}`",
        f"- 运行时间：{report['generated_at']}",
        f"- 分片：`{report['split']}`，样本数：{report['case_count']}",
        f"- Embedding：`{report['embedding_model']}`",
        (
            f"- Chunk：size={report['chunking']['chunk_size']}，"
            f"overlap={report['chunking']['chunk_overlap']}"
        ),
        (
            f"- 参数：Top-K={report['top_k']}，"
            f"最大距离={report['max_distance']}，Redis 未参与"
        ),
        "",
    ]
    if report["evaluation_backend"].startswith("offline-"):
        lines.extend(
            [
                "> 离线哈希向量仅用于工程回归；指标不能作为生产 "
                "Embedding 的质量结论或简历百分比。",
                "",
            ]
        )
    lines.extend(
        [
            "## 汇总",
            "",
            "| 模式 | Recall@K | MRR | 信息不足准确率 | 平均耗时 | P95 |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for mode in report["modes"]:
        lines.append(
            f"| {mode['mode']} | {_format_rate(mode['recall_at_k'])} | "
            f"{_format_rate(mode['mrr'])} | "
            f"{_format_rate(mode['no_answer_accuracy'])} | "
            f"{mode['average_retrieval_ms']:.2f} ms | "
            f"{mode['p95_retrieval_ms']:.2f} ms |"
        )
    lines.extend(["", "## 失败样例", ""])
    for mode in report["modes"]:
        failed = [
            case["case_id"] for case in mode["cases"] if not case["hit"]
        ]
        lines.append(
            f"- {mode['mode']}：{', '.join(failed) if failed else '无'}"
        )
    lines.extend(["", "## 回归门槛", ""])
    if report["thresholds"]:
        lines.append(
            f"- 配置：`{json.dumps(report['thresholds'], ensure_ascii=False)}`"
        )
        lines.append(
            "- 结果："
            + ("通过" if not report["gate_failures"] else "失败")
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
            "- Dev 用于调参；Holdout 只用于最终验证，不应用其逐题结果反向调参。",
            "- 信息不足准确率衡量检索前置过滤，不等同于回答模型的拒答准确率。",
            "- 小样本延迟受本机、Chroma、远程服务预热和网络抖动影响。",
            "- MRR 以首个包含期望证据片段的 Chunk 排名计算。",
            "",
        ]
    )
    return "\n".join(lines)


def write_csv(path: Path, mode_reports: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "mode",
        "case_id",
        "split",
        "category",
        "answerable",
        "hit",
        "first_relevant_rank",
        "reciprocal_rank",
        "latency_ms",
        "retrieved_chunk_ids",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for mode_report in mode_reports:
            for case in mode_report["cases"]:
                writer.writerow(
                    {
                        key: (
                            json.dumps(case[key], ensure_ascii=False)
                            if key == "retrieved_chunk_ids"
                            else case[key]
                        )
                        for key in fieldnames
                        if key != "mode"
                    }
                    | {"mode": mode_report["mode"]}
                )


def evaluate_gates(
    mode_reports: list[dict],
    thresholds: dict[str, float],
) -> list[str]:
    failures = []
    metric_names = {
        "recall_at_k": "Recall@K",
        "mrr": "MRR",
        "no_answer_accuracy": "信息不足准确率",
    }
    for mode in mode_reports:
        for key, minimum in thresholds.items():
            actual = mode[key]
            if actual is None or actual < minimum:
                actual_text = "N/A" if actual is None else f"{actual:.4f}"
                failures.append(
                    f"{mode['mode']} {metric_names[key]}="
                    f"{actual_text} < {minimum:.4f}"
                )
    return failures


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _seed_corpus(
    *,
    corpus_path: Path | None,
    knowledge_base_id: str,
    document_id: str,
) -> str:
    from app.schemas.chunk import ChunkRecord
    from app.services.ingestion.ingestion_service import build_chunks
    import app.services.vector_stores.vector_store as vector_store

    if corpus_path is None:
        sample_path = (
            PROJECT_ROOT / "data" / "sample" / "employee_handbook.txt"
        )
        chunks = build_chunks(
            str(sample_path),
            document_id=document_id,
            knowledge_base_id=knowledge_base_id,
            display_file_name="employee_handbook.txt",
        )
        corpus_name = _display_path(sample_path)
    else:
        corpus_items = json.loads(corpus_path.read_text(encoding="utf-8"))
        chunks = [
            ChunkRecord(
                chunk_id=f"{document_id}_{item['id']}",
                document_id=document_id,
                knowledge_base_id=knowledge_base_id,
                content=item["content"],
                start_index=0,
                end_index=len(item["content"]),
                page=None,
                source=corpus_path.name,
                content_hash=hashlib.md5(
                    item["content"].encode("utf-8")
                ).hexdigest(),
            )
            for item in corpus_items
        ]
        corpus_name = _display_path(corpus_path)
    vector_store.upsert_chunks(chunks)
    return corpus_name


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    dataset_path = args.dataset.resolve()
    corpus_path = args.corpus_json.resolve() if args.corpus_json else None
    metadata, all_cases = load_eval_dataset(dataset_path)
    cases = select_cases(all_cases, args.split)
    if not cases:
        raise ValueError(f"dataset split {args.split!r} is empty")

    max_distance = (
        args.max_distance
        if args.max_distance is not None
        else (1.1 if args.live_embedding else 1.6)
    )
    knowledge_base_id = "day17-eval-kb"
    document_id = (
        "day17-eval-custom-corpus"
        if corpus_path else "day17-eval-employee-handbook"
    )

    import app.services.vector_stores.vector_store as vector_store
    from app.core import settings

    if args.live_embedding:
        evaluation_backend = "configured-live-embedding"
        embedding_model = settings.EMBEDDING_MODEL or "unconfigured"
    else:
        vector_store.embed_texts = offline_embed_texts
        evaluation_backend = "offline-hashed-token-v1"
        embedding_model = "offline-hashed-token-v1"

    vector_store.delete_by_document(knowledge_base_id, document_id)
    corpus_name = _seed_corpus(
        corpus_path=corpus_path,
        knowledge_base_id=knowledge_base_id,
        document_id=document_id,
    )
    try:
        mode_reports = [
            evaluate_mode(
                mode=mode,
                cases=cases,
                knowledge_base_id=knowledge_base_id,
                top_k=args.top_k,
                max_distance=max_distance,
            )
            for mode in args.modes
        ]
    finally:
        vector_store.delete_by_document(knowledge_base_id, document_id)

    thresholds = {
        key: value
        for key, value in {
            "recall_at_k": args.min_recall_at_k,
            "mrr": args.min_mrr,
            "no_answer_accuracy": args.min_no_answer_accuracy,
        }.items()
        if value is not None
    }
    gate_failures = evaluate_gates(mode_reports, thresholds)
    generated_at = datetime.now(timezone.utc).isoformat()
    report = {
        "generated_at": generated_at,
        "evaluation_date": generated_at[:10],
        "evaluation_backend": evaluation_backend,
        "dataset": _display_path(dataset_path),
        "dataset_name": metadata["dataset_name"],
        "dataset_version": metadata["dataset_version"],
        "dataset_schema_version": metadata["schema_version"],
        "dataset_sha256": dataset_sha256(dataset_path),
        "corpus": corpus_name,
        "split": args.split,
        "split_policy": metadata.get("split_policy"),
        "case_count": len(cases),
        "answerable_case_count": sum(case["answerable"] for case in cases),
        "no_answer_case_count": sum(
            not case["answerable"] for case in cases
        ),
        "category_distribution": category_distribution(cases),
        "split_distribution": split_distribution(cases),
        "embedding_model": embedding_model,
        "chunking": {"chunk_size": 500, "chunk_overlap": 50},
        "top_k": args.top_k,
        "max_distance": max_distance,
        "retrieval_parameters": {
            "candidate_multiplier": settings.RAG_RETRIEVAL_CANDIDATE_MULTIPLIER,
            "keyword_top_k": settings.RAG_KEYWORD_TOP_K,
            "keyword_min_score": settings.RAG_KEYWORD_MIN_SCORE,
            "rrf_k": settings.RAG_RRF_K,
            "reranker_model": settings.RAG_RERANKER_MODEL,
            "rerank_lexical_weight": settings.RAG_RERANK_LEXICAL_WEIGHT,
        },
        "thresholds": thresholds,
        "gate_failures": gate_failures,
        "modes": mode_reports,
    }

    for path in (args.json_report, args.markdown_report, args.csv_report):
        path.parent.mkdir(parents=True, exist_ok=True)
    args.json_report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    args.markdown_report.write_text(build_markdown(report), encoding="utf-8")
    write_csv(args.csv_report, mode_reports)

    for mode in mode_reports:
        print(
            mode["mode"],
            f"Recall@{args.top_k}={_format_rate(mode['recall_at_k'])}",
            f"MRR={_format_rate(mode['mrr'])}",
            f"NoAnswer={_format_rate(mode['no_answer_accuracy'])}",
        )
    for failure in gate_failures:
        print(f"GATE FAIL: {failure}", file=sys.stderr)
    return 1 if gate_failures else 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
