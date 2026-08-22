import argparse
import hashlib
import json
import math
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
DEFAULT_DATASET = (
    PROJECT_ROOT
    / "eval"
    / "datasets"
    / "day16_retrieval_cases.json"
)
DEFAULT_JSON_REPORT = (
    PROJECT_ROOT
    / "eval"
    / "results"
    / "day16_retrieval_eval.json"
)
DEFAULT_MARKDOWN_REPORT = (
    PROJECT_ROOT
    / "docs"
    / "day16_retrieval_quality.md"
)
LEGACY_DATASET_PATH = (
    PROJECT_ROOT
    / "eval"
    / "datasets"
    / "retrieval_questions.jsonl"
)


def load_dataset() -> list[dict]:
    """Load the pre-Day16 30-question JSONL dataset."""
    dataset = []

    with LEGACY_DATASET_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        for line in file:
            if line.strip():
                dataset.append(json.loads(line))

    return dataset


def preview_retrieval(top_k: int = 3) -> None:
    """Preserve the original interactive retrieval preview."""
    import os

    from app.services.retrieval.retriever import retrieve

    for item in load_dataset():
        results = retrieve(
            query_text=item["question"],
            knowledge_base_id=os.environ["KNOWLEDGE_BASE_ID"],
            top_k=top_k,
        )
        print(f"\n{'=' * 60}")
        print(f"题目 {item['id']}：{item['question']}")
        print(f"类型：{item['type']}")

        for index, result in enumerate(results, start=1):
            distance = result.get("distance")
            distance_text = (
                "n/a"
                if distance is None
                else f"{distance:.4f}"
            )
            print(
                f"Top {index} | distance={distance_text} | "
                f"chunk_id={result['chunk_id']}"
            )
            print(result["content"][:100])


def evaluate_retrieval(top_k: int = 3) -> None:
    """Preserve the original evaluation entry point."""
    import os

    from app.services.retrieval.retriever import retrieve

    total = 0
    hits = 0

    for item in load_dataset():
        expected_keyword = item["expected_keyword"]

        if expected_keyword is None:
            continue

        total += 1
        results = retrieve(
            query_text=item["question"],
            knowledge_base_id=os.environ["KNOWLEDGE_BASE_ID"],
            top_k=top_k,
        )
        matched = any(
            expected_keyword in result["content"]
            for result in results
        )
        hits += int(matched)
        print(
            f"{'HIT' if matched else 'MISS'} | "
            f"题目 {item['id']} | {item['question']}"
        )

    recall = hits / total if total else 0
    print("\n===== 评测结果 =====")
    print(f"Top-K: {top_k}")
    print(f"命中: {hits}/{total}")
    print(f"Recall@{top_k}: {recall:.2%}")


def evaluate_unanswerable(
    top_k: int = 3,
    max_distance: float = 1.0,
) -> None:
    """Preserve the original unanswerable evaluation entry point."""
    import os

    from app.services.retrieval.retriever import retrieve

    total = 0
    passed = 0

    for item in load_dataset():
        if item["type"] != "unanswerable":
            continue

        total += 1
        results = retrieve(
            query_text=item["question"],
            knowledge_base_id=os.environ["KNOWLEDGE_BASE_ID"],
            top_k=top_k,
            max_distance=max_distance,
        )
        success = not results
        passed += int(success)
        print(
            f"{'PASS' if success else 'FAIL'} | "
            f"题目 {item['id']} | {item['question']}"
        )

    rate = passed / total if total else 0
    print("\n===== 不可回答题评测 =====")
    print(f"通过: {passed}/{total}")
    print(f"拒答前置过滤率: {rate:.2%}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate Day16 vector/hybrid/rerank retrieval.",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
    )
    parser.add_argument(
        "--corpus-json",
        type=Path,
        default=None,
        help=(
            "Optional fixed JSON corpus. Each item needs id and content."
        ),
    )
    parser.add_argument(
        "--json-report",
        type=Path,
        default=DEFAULT_JSON_REPORT,
    )
    parser.add_argument(
        "--markdown-report",
        type=Path,
        default=DEFAULT_MARKDOWN_REPORT,
    )
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument(
        "--max-distance",
        type=float,
        default=None,
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=("vector", "hybrid", "rerank"),
        default=("vector", "hybrid", "rerank"),
    )
    parser.add_argument(
        "--live-embedding",
        action="store_true",
        help=(
            "Use the configured external embedding endpoint. "
            "Without this flag, evaluation stays offline."
        ),
    )
    return parser.parse_args()


def load_cases(path: Path) -> list[dict]:
    if path.suffix.lower() == ".jsonl":
        cases = []

        with path.open("r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue

                item = json.loads(line)
                cases.append(
                    {
                        "id": str(item["id"]),
                        "query": item["question"],
                        "expected_substring": item[
                            "expected_keyword"
                        ],
                        "failure_category": item["type"],
                        "failure_hypothesis": (
                            "Pre-Day16 fixed retrieval case."
                        ),
                    }
                )

        return cases

    return json.loads(path.read_text(encoding="utf-8"))


def offline_embed_texts(texts: list[str]) -> list[list[float]]:
    from app.core.settings import EMBEDDING_DIMENSIONS
    from app.services.retrieval.keyword_retriever import tokenize

    embeddings = []

    for text in texts:
        vector = [0.0] * EMBEDDING_DIMENSIONS

        for token in tokenize(text):
            digest = hashlib.sha256(
                token.encode("utf-8")
            ).digest()
            index = int.from_bytes(
                digest[:4],
                "big",
            ) % EMBEDDING_DIMENSIONS
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))

        if norm:
            vector = [value / norm for value in vector]

        embeddings.append(vector)

    return embeddings


def evaluate_mode(
    *,
    mode: str,
    cases: list[dict],
    knowledge_base_id: str,
    top_k: int,
    max_distance: float,
) -> dict:
    from app.services.retrieval.retriever import retrieve

    results = []
    latencies = []

    for case in cases:
        started_at = time.perf_counter()
        items = retrieve(
            query_text=case["query"],
            knowledge_base_id=knowledge_base_id,
            top_k=top_k,
            max_distance=max_distance,
            mode=mode,
        )
        latency_ms = (time.perf_counter() - started_at) * 1000
        latencies.append(latency_ms)
        expected = case["expected_substring"]
        hit = (
            not items
            if expected is None
            else any(
                expected in item["content"]
                for item in items
            )
        )
        results.append(
            {
                **case,
                "hit": hit,
                "latency_ms": round(latency_ms, 2),
                "retrieved_chunk_ids": [
                    item["chunk_id"]
                    for item in items
                ],
                "top_contents": [
                    item["content"][:160]
                    for item in items
                ],
                "rerank_candidate_count": (
                    items[0].get(
                        "rerank_candidate_count",
                        0,
                    )
                    if items
                    else 0
                ),
            }
        )

    answerable = [
        result
        for result in results
        if result["expected_substring"] is not None
    ]
    no_answer = [
        result
        for result in results
        if result["expected_substring"] is None
    ]

    return {
        "mode": mode,
        "recall_at_k": round(
            sum(result["hit"] for result in answerable)
            / len(answerable),
            4,
        ),
        "no_answer_accuracy": round(
            sum(result["hit"] for result in no_answer)
            / len(no_answer),
            4,
        ) if no_answer else None,
        "average_retrieval_ms": round(
            statistics.mean(latencies),
            2,
        ),
        "p95_retrieval_ms": round(
            sorted(latencies)[
                min(
                    len(latencies) - 1,
                    int(len(latencies) * 0.95),
                )
            ],
            2,
        ),
        "average_rerank_candidate_count": round(
            statistics.mean(
                result["rerank_candidate_count"]
                for result in results
            ),
            2,
        ),
        "cases": results,
    }


def build_markdown(report: dict) -> str:
    lines = [
        "# Day16 检索质量对比报告",
        "",
        f"运行时间：{report['generated_at']}",
        "",
        f"评测后端：`{report['evaluation_backend']}`。",
        "",
        (
            f"固定数据集：{report['case_count']} 个问题，其中 "
            f"{report['answerable_case_count']} 个可回答问题、"
            f"{report['no_answer_case_count']} 个信息不足问题。"
        ),
        (
            f"参数：Top-K={report['top_k']}，"
            f"向量距离上限={report['max_distance']}，"
            "Redis 检索缓存未参与。"
        ),
        "",
        "## 汇总",
        "",
        "| 模式 | Recall@K | 信息不足准确率 | 平均检索耗时 | P95 检索耗时 | 平均重排候选数 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]

    if report["evaluation_backend"].startswith("offline-"):
        lines.extend(
            [
                (
                    "> 注意：离线哈希向量只用于可重复的工程回归；"
                    "其距离尺度、Recall 和延迟不能替代生产 Embedding 评测。"
                ),
                "",
            ]
        )

    for mode in report["modes"]:
        no_answer = mode["no_answer_accuracy"]
        no_answer_text = (
            "N/A"
            if no_answer is None
            else f"{no_answer:.2%}"
        )
        lines.append(
            f"| {mode['mode']} | {mode['recall_at_k']:.2%} | "
            f"{no_answer_text} | "
            f"{mode['average_retrieval_ms']:.2f} ms | "
            f"{mode['p95_retrieval_ms']:.2f} ms | "
            f"{mode['average_rerank_candidate_count']:.2f} |"
        )

    lines.extend(
        [
            "",
            "## 固定失败/风险分类",
            "",
            "| ID | 分类 | 问题 | Vector | Hybrid | Rerank |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    modes_by_name = {
        mode["mode"]: {
            case["id"]: case
            for case in mode["cases"]
        }
        for mode in report["modes"]
    }

    for case in report["modes"][0]["cases"]:
        cells = []

        for mode_name in ("vector", "hybrid", "rerank"):
            mode_case = modes_by_name.get(mode_name, {}).get(case["id"])
            cells.append(
                "命中" if mode_case and mode_case["hit"] else "失败"
            )

        lines.append(
            f"| {case['id']} | {case['failure_category']} | "
            f"{case['query']} | {' | '.join(cells)} |"
        )

    vector = modes_by_name.get("vector", {})
    hybrid = modes_by_name.get("hybrid", {})
    improved = [
        case_id
        for case_id, hybrid_case in hybrid.items()
        if hybrid_case["hit"]
        and case_id in vector
        and not vector[case_id]["hit"]
    ]
    regressed = [
        case_id
        for case_id, hybrid_case in hybrid.items()
        if not hybrid_case["hit"]
        and case_id in vector
        and vector[case_id]["hit"]
    ]
    summaries = {
        mode["mode"]: mode
        for mode in report["modes"]
    }
    vector_summary = summaries.get("vector")
    hybrid_summary = summaries.get("hybrid")
    rerank_summary = summaries.get("rerank")
    lines.extend(
        [
            "",
            "## 结论",
            "",
            (
                "- Hybrid 相比 Vector 新增命中："
                f"{', '.join(improved) if improved else '无'}。"
            ),
            (
                "- Hybrid 相比 Vector 退化："
                f"{', '.join(regressed) if regressed else '无'}。"
            ),
            (
                "- 当前关键词分支直接读取指定 knowledge_base_id 的 "
                "Chroma Chunk，避免维护第二套索引；代价是知识库变大后全量 "
                "BM25 扫描会增加延迟与内存开销。"
            ),
            (
                "- rerank 使用本地 lexical-v1，并非外部 cross-encoder；"
                "它没有模型费用，但只能强化词面匹配。只有固定集数据支持时，"
                "才应把默认模式从 vector 改为 hybrid 或 rerank。"
            ),
        ]
    )

    if (
        report["evaluation_backend"]
        == "configured-live-embedding"
    ):
        lines.extend(
            [
                (
                    "- 本次三种模式按顺序调用同一远程 Embedding 服务；"
                    "13 问样本较小，预热和网络抖动会影响平均/P95，"
                    "因此不能据此断言 Hybrid 比 Vector 更快。"
                ),
            ]
        )

    if (
        vector_summary
        and hybrid_summary
        and hybrid_summary["recall_at_k"]
        > vector_summary["recall_at_k"]
        and not regressed
    ):
        lines.append(
            "- 当前固定集支持保留 Hybrid 作为可选优化；默认仍为 Vector，"
            "待更大真实数据集确认后再切换生产默认值。"
        )

    if (
        hybrid_summary
        and rerank_summary
        and rerank_summary["recall_at_k"]
        <= hybrid_summary["recall_at_k"]
    ):
        lines.append(
            "- Rerank 未比 Hybrid 增加命中，当前不值得设为默认模式。"
        )

    lines.append("")

    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    dataset_path = args.dataset.resolve()
    corpus_path = (
        args.corpus_json.resolve()
        if args.corpus_json is not None
        else None
    )
    max_distance = (
        args.max_distance
        if args.max_distance is not None
        else (1.1 if args.live_embedding else 1.6)
    )
    cases = load_cases(dataset_path)
    knowledge_base_id = "day16-eval-kb"
    document_id = (
        "day16-eval-custom-corpus"
        if corpus_path is not None
        else "day16-eval-employee-handbook"
    )

    from app.schemas.chunk import ChunkRecord
    from app.services.ingestion.ingestion_service import build_chunks
    import app.services.vector_stores.vector_store as vector_store

    if args.live_embedding:
        evaluation_backend = "configured-live-embedding"
    else:
        vector_store.embed_texts = offline_embed_texts
        evaluation_backend = "offline-hashed-bigram-v1"

    vector_store.delete_by_document(
        knowledge_base_id,
        document_id,
    )

    if corpus_path is None:
        sample_path = (
            PROJECT_ROOT
            / "data"
            / "sample"
            / "employee_handbook.txt"
        )
        chunks = build_chunks(
            str(sample_path),
            document_id=document_id,
            knowledge_base_id=knowledge_base_id,
            display_file_name="employee_handbook.txt",
        )
        corpus_name = str(sample_path.relative_to(PROJECT_ROOT))
    else:
        corpus_items = json.loads(
            corpus_path.read_text(encoding="utf-8")
        )
        chunks = [
            ChunkRecord(
                chunk_id=f"{document_id}_{item['id']}",
                document_id=document_id,
                knowledge_base_id=knowledge_base_id,
                content=item["content"],
                start_index=0,
                end_index=len(item["content"]),
                page=None,
                source="day16_failure_corpus.json",
                content_hash=hashlib.md5(
                    item["content"].encode("utf-8")
                ).hexdigest(),
            )
            for item in corpus_items
        ]
        corpus_name = str(corpus_path.relative_to(PROJECT_ROOT))
    vector_store.upsert_chunks(chunks)

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
        vector_store.delete_by_document(
            knowledge_base_id,
            document_id,
        )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_backend": evaluation_backend,
        "dataset": str(dataset_path.relative_to(PROJECT_ROOT)),
        "corpus": corpus_name,
        "case_count": len(cases),
        "answerable_case_count": sum(
            case["expected_substring"] is not None
            for case in cases
        ),
        "no_answer_case_count": sum(
            case["expected_substring"] is None
            for case in cases
        ),
        "top_k": args.top_k,
        "max_distance": max_distance,
        "modes": mode_reports,
    }
    args.json_report.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_report.parent.mkdir(parents=True, exist_ok=True)
    args.json_report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    args.markdown_report.write_text(
        build_markdown(report),
        encoding="utf-8",
    )

    for mode in mode_reports:
        print(
            mode["mode"],
            f"Recall@{args.top_k}={mode['recall_at_k']:.2%}",
            f"avg={mode['average_retrieval_ms']:.2f}ms",
        )


if __name__ == "__main__":
    main()
