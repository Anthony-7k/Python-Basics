import sys
import json

from pathlib import Path


ROOT_PATH = Path(__file__).resolve().parent.parent

sys.path.append(
    str(ROOT_PATH)
)


from app.services.rag.rag_service import answer_question
from app.services.retrieval.retriever import retrieve


DATASET_PATH = Path(
    "eval/datasets/retrieval_questions.jsonl"
)


def load_questions():
    questions = []

    with open(
        DATASET_PATH,
        "r",
        encoding="utf-8",
    ) as f:
        for line in f:
            questions.append(
                json.loads(line)
            )

    return questions


def evaluate_question(item):

    response = answer_question(
        item["question"]
    )

    answer = response.answer
    source_files = [
        source.file_name.replace("\\", "/").split("/")[-1]
        for source in response.sources
        if source.file_name
    ]

    expected_source = item["expected_source"]

    source_hit = None

    if expected_source is not None:
        source_hit = expected_source in source_files

    result = {
        "id": item["id"],
        "type": item["type"],
        "question": item["question"],
        "answer": answer,
        "expected_keyword": item["expected_keyword"],
        "expected_source": expected_source,
        "source_hit": source_hit,
        "passed": False,
    }

    if item["type"] == "unanswerable":

        if "知识库中没有足够的信息" in answer:
            result["passed"] = True

    else:

        keyword = item["expected_keyword"]

        if keyword and keyword in answer:
            result["passed"] = True

    return result


def main():

    questions = load_questions()

    results = []

    for item in questions:

        result = evaluate_question(
            item
        )

        results.append(
            result
        )

        status = "PASS" if result["passed"] else "FAIL"

        print(
            f"[{status}] "
            f"id={result['id']} "
            f"{result['question']}"
        )

        if not result["passed"]:
            print(
                f"  Answer: {result['answer']}"
            )
            print(
                f"  Expected: {result['expected_keyword']}"
            )
            raw_results = retrieve(
                query_text=result["question"],
                top_k=3,
                max_distance=None,
            )

            for index, r in enumerate(
                raw_results,
                start=1,
            ):
                print(
                    f"  Top{index}: "
                    f"distance={r['distance']:.4f} "
                    f"content={r['content'][:80]}"
                )


    passed = sum(
        1
        for r in results
        if r["passed"]
    )

    total = len(results)

    print()
    print(
        f"Score: {passed}/{total}"
    )
    source_results = [
        r
        for r in results
        if r["expected_source"] is not None
    ]

    source_hits = sum(
        1
        for r in source_results
        if r["source_hit"]
    )

    source_total = len(
        source_results
    )

    source_rate = (
        source_hits / source_total
        if source_total
        else 0
    )

    print(
        f"Citation Hit Rate: "
        f"{source_hits}/{source_total} "
        f"({source_rate:.1%})"
    )


if __name__ == "__main__":
    main()