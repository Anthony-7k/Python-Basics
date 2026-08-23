"""Shared Day17 dataset validation and deterministic scoring rules."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


REFUSAL_TEXT = "知识库中没有足够的信息回答这个问题"
CITATION_PATTERN = re.compile(r"\[(S\d+)\]")
ALLOWED_SPLITS = {"dev", "holdout"}
REQUIRED_CATEGORIES = {
    "single_fact",
    "numeric_boundary",
    "list",
    "cross_paragraph",
    "exact_term",
    "paraphrase",
    "unanswerable",
    "followup",
}


def normalize_text(value: str) -> str:
    """Normalize insignificant spacing and case for deterministic matching."""
    return "".join(value.lower().split())


def text_contains(text: str, expected: str) -> bool:
    normalized_text = normalize_text(text)
    normalized_expected = normalize_text(expected)
    start = 0

    while True:
        index = normalized_text.find(normalized_expected, start)
        if index < 0:
            return False
        end = index + len(normalized_expected)
        left_splits_number = (
            normalized_expected[0].isdigit()
            and index > 0
            and normalized_text[index - 1].isdigit()
        )
        right_splits_number = (
            normalized_expected[-1].isdigit()
            and end < len(normalized_text)
            and normalized_text[end].isdigit()
        )
        if not left_splits_number and not right_splits_number:
            return True
        start = index + 1


def text_contains_unnegated(text: str, expected: str) -> bool:
    """Find a forbidden phrase while ignoring common Chinese negations."""
    normalized_text = normalize_text(text)
    normalized_expected = normalize_text(expected)
    start = 0

    while True:
        index = normalized_text.find(normalized_expected, start)
        if index < 0:
            return False
        end = index + len(normalized_expected)
        prefix = normalized_text[max(0, index - 2):index]
        left_splits_number = (
            normalized_expected[0].isdigit()
            and index > 0
            and normalized_text[index - 1].isdigit()
        )
        right_splits_number = (
            normalized_expected[-1].isdigit()
            and end < len(normalized_text)
            and normalized_text[end].isdigit()
        )
        if (
            not prefix.endswith(("不", "未", "无", "非"))
            and not left_splits_number
            and not right_splits_number
        ):
            return True
        start = index + 1


def dataset_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_eval_dataset(path: Path) -> tuple[dict[str, Any], list[dict]]:
    """Load the Day17 contract while retaining Day16 list compatibility."""
    payload = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(payload, list):
        metadata = {
            "dataset_name": path.stem,
            "dataset_version": "legacy",
            "schema_version": "legacy",
        }
        cases = [_normalize_legacy_case(item) for item in payload]
        return metadata, cases

    if not isinstance(payload, dict) or not isinstance(
        payload.get("cases"),
        list,
    ):
        raise ValueError("dataset must be a list or an object with cases")

    metadata = {
        key: value
        for key, value in payload.items()
        if key != "cases"
    }
    cases = payload["cases"]
    validate_eval_dataset(metadata, cases)
    return metadata, cases


def _normalize_legacy_case(item: dict) -> dict:
    expected = item.get("expected_substring")
    return {
        **item,
        "case_id": str(item.get("case_id", item.get("id"))),
        "split": item.get("split", "dev"),
        "category": item.get(
            "category",
            item.get("failure_category", "single_fact"),
        ),
        "question": item.get("question", item.get("query")),
        "standalone_question": item.get(
            "standalone_question",
            item.get("query", item.get("question")),
        ),
        "history": item.get("history", []),
        "answerable": expected is not None,
        "expected_answer": {
            "facts": [] if expected is None else [expected],
            "forbidden_facts": [],
        },
        "expected_source": (
            None
            if expected is None
            else {
                "file_name": None,
                "evidence_substrings": [expected],
            }
        ),
        "retrieval": item.get("retrieval", {"mode": "vector"}),
        "notes": item.get(
            "notes",
            item.get("failure_hypothesis", "Legacy case."),
        ),
    }


def validate_eval_dataset(
    metadata: dict[str, Any],
    cases: list[dict],
    *,
    expected_count: int | None = None,
) -> None:
    for key in ("dataset_name", "dataset_version", "schema_version"):
        if not metadata.get(key):
            raise ValueError(f"dataset metadata missing {key}")

    if expected_count is not None and len(cases) != expected_count:
        raise ValueError(
            f"dataset needs {expected_count} cases, found {len(cases)}"
        )

    seen_ids: set[str] = set()
    for index, case in enumerate(cases, start=1):
        case_id = case.get("case_id")
        if not case_id or case_id in seen_ids:
            raise ValueError(
                f"case {index} has a missing or duplicate case_id"
            )
        seen_ids.add(case_id)

        if case.get("split") not in ALLOWED_SPLITS:
            raise ValueError(f"{case_id} has an invalid split")
        if not case.get("category"):
            raise ValueError(f"{case_id} has no category")
        if not case.get("question") or not case.get("standalone_question"):
            raise ValueError(f"{case_id} has no question")
        if not isinstance(case.get("history"), list):
            raise ValueError(f"{case_id} history must be a list")
        if not isinstance(case.get("answerable"), bool):
            raise ValueError(f"{case_id} answerable must be boolean")

        expected_answer = case.get("expected_answer")
        if not isinstance(expected_answer, dict):
            raise ValueError(f"{case_id} has no expected_answer")
        facts = expected_answer.get("facts")
        forbidden = expected_answer.get("forbidden_facts")
        if not isinstance(facts, list) or not isinstance(forbidden, list):
            raise ValueError(f"{case_id} fact fields must be lists")

        expected_source = case.get("expected_source")
        if case["answerable"]:
            if not facts:
                raise ValueError(f"{case_id} needs expected facts")
            if not isinstance(expected_source, dict):
                raise ValueError(f"{case_id} needs an expected source")
            if not expected_source.get("evidence_substrings"):
                raise ValueError(f"{case_id} needs expected evidence")
        elif facts or expected_source is not None:
            raise ValueError(
                f"{case_id} is unanswerable but declares facts or a source"
            )


def select_cases(cases: list[dict], split: str) -> list[dict]:
    if split == "all":
        return list(cases)
    return [case for case in cases if case["split"] == split]


def case_query(case: dict) -> str:
    return case.get("standalone_question") or case["question"]


def expected_evidence(case: dict) -> list[str]:
    source = case.get("expected_source") or {}
    return list(source.get("evidence_substrings", []))


def retrieval_match_ranks(case: dict, items: list[dict]) -> list[int]:
    evidence = expected_evidence(case)
    if not evidence:
        return []

    return [
        rank
        for rank, item in enumerate(items, start=1)
        if any(
            text_contains(item.get("content", ""), fragment)
            for fragment in evidence
        )
    ]


def _source_value(source: Any, key: str, default: Any = None) -> Any:
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _source_file_name(source: Any) -> str | None:
    file_name = _source_value(source, "file_name")
    if file_name:
        return Path(str(file_name).replace("\\", "/")).name
    metadata = _source_value(source, "metadata", {}) or {}
    if isinstance(metadata, dict) and metadata.get("source"):
        return Path(str(metadata["source"]).replace("\\", "/")).name
    return None


def score_answer_case(
    case: dict,
    answer: str,
    sources: list[Any],
) -> dict[str, Any]:
    """Apply deterministic facts, refusal, and citation rules."""
    expected_answer = case["expected_answer"]
    facts = expected_answer["facts"]
    forbidden_facts = expected_answer["forbidden_facts"]
    matched_facts = [fact for fact in facts if text_contains(answer, fact)]
    forbidden_hits = [
        fact
        for fact in forbidden_facts
        if text_contains_unnegated(answer, fact)
    ]
    fact_coverage = len(matched_facts) / len(facts) if facts else None
    refusal_present = text_contains(answer, REFUSAL_TEXT)
    refusal_correct = refusal_present if not case["answerable"] else None
    fact_consistent = (
        not forbidden_hits
        if case["answerable"]
        else refusal_present
    )
    answer_relevant = (
        bool(matched_facts) and not refusal_present
        if case["answerable"]
        else refusal_present
    )

    citation_ids = list(dict.fromkeys(CITATION_PATTERN.findall(answer)))
    sources_by_id = {
        str(_source_value(source, "source_id")): source
        for source in sources
        if _source_value(source, "source_id")
    }
    citations_exist = bool(citation_ids) and all(
        citation_id in sources_by_id for citation_id in citation_ids
    )
    citation_correct: bool | None

    if not case["answerable"]:
        citation_correct = None
    else:
        expected_source = case["expected_source"]
        expected_file = expected_source.get("file_name")
        evidence = expected_source["evidence_substrings"]
        cited_sources = [
            sources_by_id[citation_id]
            for citation_id in citation_ids
            if citation_id in sources_by_id
        ]
        source_supported = any(
            (
                expected_file is None
                or _source_file_name(source) == expected_file
            )
            and any(
                text_contains(
                    str(_source_value(source, "content", "")),
                    fragment,
                )
                for fragment in evidence
            )
            for source in cited_sources
        )
        citation_correct = citations_exist and source_supported

    if not case["answerable"]:
        manual_score = 2 if refusal_correct and not citation_ids else 0
        if refusal_correct and citation_ids:
            manual_score = 1
    elif forbidden_hits or refusal_present:
        manual_score = 0
    elif fact_coverage == 1.0 and citation_correct:
        manual_score = 2
    elif matched_facts:
        manual_score = 1
    else:
        manual_score = 0

    return {
        "case_id": case["case_id"],
        "split": case["split"],
        "category": case["category"],
        "question": case["question"],
        "answerable": case["answerable"],
        "answer": answer,
        "manual_score": manual_score,
        "matched_facts": matched_facts,
        "missing_facts": [fact for fact in facts if fact not in matched_facts],
        "forbidden_fact_hits": forbidden_hits,
        "fact_coverage": fact_coverage,
        "fact_consistent": fact_consistent,
        "answer_relevant": answer_relevant,
        "refusal_present": refusal_present,
        "refusal_correct": refusal_correct,
        "citation_ids": citation_ids,
        "citation_correct": citation_correct,
        "sources": [
            {
                "source_id": _source_value(source, "source_id"),
                "chunk_id": _source_value(source, "chunk_id"),
                "file_name": _source_file_name(source),
                "content": _source_value(source, "content", ""),
            }
            for source in sources
        ],
    }


def summarize_answer_results(results: list[dict]) -> dict[str, Any]:
    if not results:
        raise ValueError("cannot summarize an empty result set")

    answerable = [result for result in results if result["answerable"]]
    no_answer = [result for result in results if not result["answerable"]]
    cited = [
        result
        for result in answerable
        if result["citation_correct"] is not None
    ]
    distribution = Counter(result["manual_score"] for result in results)

    return {
        "case_count": len(results),
        "answerable_case_count": len(answerable),
        "no_answer_case_count": len(no_answer),
        "average_manual_score": round(
            sum(result["manual_score"] for result in results)
            / len(results),
            4,
        ),
        "score_distribution": {
            str(score): distribution.get(score, 0)
            for score in (0, 1, 2)
        },
        "average_fact_coverage": round(
            sum(result["fact_coverage"] for result in answerable)
            / len(answerable),
            4,
        ) if answerable else None,
        "fact_consistency": round(
            sum(bool(result["fact_consistent"]) for result in results)
            / len(results),
            4,
        ),
        "answer_relevance": round(
            sum(bool(result["answer_relevant"]) for result in results)
            / len(results),
            4,
        ),
        "refusal_accuracy": round(
            sum(bool(result["refusal_correct"]) for result in no_answer)
            / len(no_answer),
            4,
        ) if no_answer else None,
        "citation_correctness": round(
            sum(bool(result["citation_correct"]) for result in cited)
            / len(cited),
            4,
        ) if cited else None,
        "failed_case_ids": [
            result["case_id"]
            for result in results
            if result["manual_score"] < 2
        ],
    }


def category_distribution(cases: list[dict]) -> dict[str, int]:
    return dict(sorted(Counter(case["category"] for case in cases).items()))


def split_distribution(cases: list[dict]) -> dict[str, int]:
    return dict(sorted(Counter(case["split"] for case in cases).items()))
