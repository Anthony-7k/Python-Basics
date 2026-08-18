import json
import os
from pathlib import Path
from app.services.retrieval.retriever import retrieve


DATASET_PATH = Path(
    "eval/datasets/retrieval_questions.jsonl"
)


def load_dataset() -> list[dict]:
    dataset = []

    with DATASET_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        for line in file:
            if not line.strip():
                continue

            item = json.loads(line)
            dataset.append(item)

    return dataset


def preview_retrieval(
    top_k: int = 3,
) -> None:
    dataset = load_dataset()

    for item in dataset:
        question = item["question"]

        results = retrieve(
            query_text=question,
            knowledge_base_id=os.environ[
                "KNOWLEDGE_BASE_ID"
            ],
            top_k=top_k,
        )

        print(f"\n{'=' * 60}")
        print(f"题目 {item['id']}：{question}")
        print(f"类型：{item['type']}")

        for index, result in enumerate(
            results,
            start=1,
        ):
            print(
                f"Top {index} | "
                f"distance={result['distance']:.4f} | "
                f"chunk_id={result['chunk_id']}"
            )

            print(
                result["content"][:100]
            )


def evaluate_retrieval(
    top_k: int = 3,
) -> None:
    dataset = load_dataset()

    total = 0
    hits = 0

    for item in dataset:
        expected_keyword = item["expected_keyword"]

        if expected_keyword is None:
            continue

        total += 1

        results = retrieve(
            query_text=item["question"],
            knowledge_base_id=os.environ[
                "KNOWLEDGE_BASE_ID"
            ],
            top_k=top_k,
        )

        matched = any(
            expected_keyword in result["content"]
            for result in results
        )

        if matched:
            hits += 1
            status = "HIT"
        else:
            status = "MISS"

        print(
            f"{status} | "
            f"题目 {item['id']} | "
            f"{item['question']}"
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
    dataset = load_dataset()

    total = 0
    passed = 0

    for item in dataset:
        if item["type"] != "unanswerable":
            continue

        total += 1

        results = retrieve(
            query_text=item["question"],
            knowledge_base_id=os.environ[
                "KNOWLEDGE_BASE_ID"
            ],
            top_k=top_k,
            max_distance=max_distance,
        )

        if not results:
            passed += 1
            status = "PASS"
        else:
            status = "FAIL"

        print(
            f"{status} | "
            f"题目 {item['id']} | "
            f"{item['question']}"
        )

    rate = passed / total if total else 0

    print("\n===== 不可回答题评测 =====")
    print(f"通过: {passed}/{total}")
    print(f"拒答前置过滤率: {rate:.2%}")
