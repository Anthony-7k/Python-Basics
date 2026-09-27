# Portfolio MVP Baseline Evaluation

## Run summary

The baseline was generated on 4 September 2026 with the versioned 30-case dataset, the deterministic rule-based planner, the sample knowledge adapter, and the in-memory SQLite test database.

| Metric | Result |
| --- | ---: |
| Cases | 30 |
| Passed | 30 |
| Failed | 0 |
| Task Success Rate | 100.00% |
| Tool Selection Accuracy | 100.00% |
| Tool Execution Success Rate | 97.06% |
| Average Steps | 1.10 |
| Average Token Usage | unavailable |
| Average Latency | 49.73 ms |

Tool Execution Success Rate is below 100% because the evaluation deliberately records the failed attempt in the checkpoint recovery case before the task resumes successfully. Average Token Usage is unavailable because the deterministic planner does not call an LLM. These values were calculated by `python -m eval.run_eval` and are backed by `eval/results/baseline.json`.

## Coverage

The dataset includes simple, tool call, multi-tool, multi-step, failure, approval, and unanswerable cases. It verifies final task status, exact tool order, expected answer markers, retry counts, recovery, approval decisions, and modified approval payloads.
