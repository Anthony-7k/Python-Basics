import json
from pathlib import Path

from eval.eval_answer import (
    evaluate_gates as evaluate_answer_gates,
    run as run_answer_evaluation,
)
from eval.eval_retrieval import (
    evaluate_gates as evaluate_retrieval_gates,
    evaluate_mode,
)
from eval.evaluation_contract import (
    REQUIRED_CATEGORIES,
    load_eval_dataset,
    score_answer_case,
    summarize_answer_results,
    validate_eval_dataset,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = (
    PROJECT_ROOT / "eval" / "datasets" / "day17_rag_eval_v1.json"
)
CORE_PATH = (
    PROJECT_ROOT / "eval" / "datasets" / "day17_core_regression.json"
)
HANDBOOK_PATH = (
    PROJECT_ROOT / "data" / "sample" / "employee_handbook.txt"
)


def _load():
    return load_eval_dataset(DATASET_PATH)


def _answer_with_source(case):
    answer = "；".join(case["expected_answer"]["facts"]) + "。[S1]"
    source = {
        "source_id": "S1",
        "chunk_id": "core-chunk",
        "file_name": case["expected_source"]["file_name"],
        "content": "\n".join(
            case["expected_source"]["evidence_substrings"]
        ),
    }
    return answer, [source]


def test_day17_dataset_has_fifty_versioned_balanced_cases():
    metadata, cases = _load()

    validate_eval_dataset(metadata, cases, expected_count=50)

    assert metadata["dataset_version"] == "day17-v1"
    assert sum(case["split"] == "dev" for case in cases) == 25
    assert sum(case["split"] == "holdout" for case in cases) == 25
    assert sum(case["answerable"] for case in cases) == 40
    assert sum(not case["answerable"] for case in cases) == 10
    assert REQUIRED_CATEGORIES <= {case["category"] for case in cases}


def test_all_expected_evidence_exists_in_fixed_corpus():
    _, cases = _load()
    handbook = HANDBOOK_PATH.read_text(encoding="utf-8")

    for case in cases:
        if not case["answerable"]:
            continue
        for fragment in case["expected_source"]["evidence_substrings"]:
            assert fragment in handbook, case["case_id"]


def test_core_regression_suite_selects_ten_critical_cases():
    _, cases = _load()
    cases_by_id = {case["case_id"]: case for case in cases}
    suite = json.loads(CORE_PATH.read_text(encoding="utf-8"))

    assert suite["dataset_version"] == "day17-v1"
    assert len(suite["case_ids"]) == 10
    assert len(set(suite["case_ids"])) == 10
    assert set(suite["case_ids"]) <= set(cases_by_id)
    assert any(
        not cases_by_id[case_id]["answerable"]
        for case_id in suite["case_ids"]
    )
    assert any(
        cases_by_id[case_id]["category"] == "followup"
        for case_id in suite["case_ids"]
    )


def test_core_answer_scoring_requires_facts_and_real_citation():
    _, cases = _load()
    suite = json.loads(CORE_PATH.read_text(encoding="utf-8"))
    cases_by_id = {case["case_id"]: case for case in cases}

    for case_id in suite["case_ids"]:
        case = cases_by_id[case_id]
        if case["answerable"]:
            answer, sources = _answer_with_source(case)
        else:
            answer = "知识库中没有足够的信息回答这个问题。"
            sources = []
        result = score_answer_case(case, answer, sources)
        assert result["manual_score"] == 2, case_id


def test_answer_scoring_does_not_equate_correct_fact_with_citation():
    _, cases = _load()
    case = next(case for case in cases if case["case_id"] == "d17-010")
    result = score_answer_case(case, "员工每年有10天年假。[S9]", [])

    assert result["fact_coverage"] == 1.0
    assert result["citation_correct"] is False
    assert result["manual_score"] == 1


def test_retrieval_mode_computes_recall_and_mrr(monkeypatch):
    _, cases = _load()
    selected = [
        next(case for case in cases if case["case_id"] == "d17-002"),
        next(case for case in cases if case["case_id"] == "d17-010"),
        next(case for case in cases if case["case_id"] == "d17-041"),
    ]

    def fake_retrieve(**kwargs):
        if "迟到" in kwargs["query_text"]:
            return [
                {"chunk_id": "wrong", "content": "无关内容"},
                {
                    "chunk_id": "right",
                    "content": "达到3次及以上的，将记录为一次考勤异常",
                },
            ]
        if "10年" in kwargs["query_text"]:
            return [
                {
                    "chunk_id": "annual",
                    "content": "满10年但不满20年的员工，每年享有10天带薪年假",
                }
            ]
        return []

    monkeypatch.setattr(
        "app.services.retrieval.retriever.retrieve",
        fake_retrieve,
    )
    report = evaluate_mode(
        mode="vector",
        cases=selected,
        knowledge_base_id="kb-test",
        top_k=3,
        max_distance=1.1,
    )

    assert report["recall_at_k"] == 1.0
    assert report["mrr"] == 0.75
    assert report["no_answer_accuracy"] == 1.0


def test_threshold_failures_are_explicit_for_nonzero_exit_paths():
    retrieval_failures = evaluate_retrieval_gates(
        [
            {
                "mode": "vector",
                "recall_at_k": 0.8,
                "mrr": 0.7,
                "no_answer_accuracy": 0.6,
            }
        ],
        {"recall_at_k": 0.9, "mrr": 0.8},
    )
    answer_failures = evaluate_answer_gates(
        {
            "average_manual_score": 1.5,
            "average_fact_coverage": 0.8,
            "refusal_accuracy": 0.7,
            "citation_correctness": 0.75,
        },
        {"average_manual_score": 1.8, "citation_correctness": 0.9},
    )

    assert len(retrieval_failures) == 2
    assert len(answer_failures) == 2


def test_answer_summary_keeps_refusal_and_citation_independent():
    _, cases = _load()
    answerable = next(case for case in cases if case["case_id"] == "d17-010")
    unanswerable = next(case for case in cases if case["case_id"] == "d17-041")
    answer, sources = _answer_with_source(answerable)
    results = [
        score_answer_case(answerable, answer, sources),
        score_answer_case(
            unanswerable,
            "知识库中没有足够的信息回答这个问题。",
            [],
        ),
    ]

    summary = summarize_answer_results(results)

    assert summary["average_manual_score"] == 2.0
    assert summary["refusal_accuracy"] == 1.0
    assert summary["citation_correctness"] == 1.0


def test_answer_cli_replay_writes_all_formats_and_enforces_gate(tmp_path):
    _, cases = _load()
    selected = [
        next(case for case in cases if case["case_id"] == "d17-010"),
        next(case for case in cases if case["case_id"] == "d17-041"),
    ]
    dataset_path = tmp_path / "dataset.json"
    responses_path = tmp_path / "responses.json"
    json_report = tmp_path / "report.json"
    csv_report = tmp_path / "report.csv"
    markdown_report = tmp_path / "report.md"
    dataset_path.write_text(
        json.dumps(
            {
                "dataset_name": "test-suite",
                "dataset_version": "test-v1",
                "schema_version": "1.0",
                "cases": selected,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    answer, sources = _answer_with_source(selected[0])
    responses_path.write_text(
        json.dumps(
            {
                "llm_model": "frozen-test-model",
                "embedding_model": "frozen-test-embedding",
                "cases": [
                    {
                        "case_id": "d17-010",
                        "answer": answer,
                        "sources": sources,
                    },
                    {
                        "case_id": "d17-041",
                        "answer": "知识库中没有足够的信息回答这个问题。",
                        "sources": [],
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    common_args = [
        "--dataset",
        str(dataset_path),
        "--responses-json",
        str(responses_path),
        "--json-report",
        str(json_report),
        "--csv-report",
        str(csv_report),
        "--markdown-report",
        str(markdown_report),
    ]

    assert run_answer_evaluation(common_args + ["--min-average-score", "2"]) == 0
    assert json_report.exists()
    assert csv_report.exists()
    assert markdown_report.exists()
    responses_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "d17-010",
                        "answer": "无法确定。",
                        "sources": [],
                    },
                    {
                        "case_id": "d17-041",
                        "answer": "知识库中没有足够的信息回答这个问题。",
                        "sources": [],
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    assert run_answer_evaluation(common_args + ["--min-average-score", "2"]) == 1
