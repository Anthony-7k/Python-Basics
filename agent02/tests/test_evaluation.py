from __future__ import annotations

from pathlib import Path

import pytest

from eval.run_eval import evaluate


@pytest.mark.asyncio
async def test_portfolio_evaluation_dataset_is_repeatable():
    dataset = Path(__file__).parents[1] / "eval" / "datasets" / "portfolio_mvp.json"
    result = await evaluate(dataset)
    assert result["dataset_size"] == 30
    assert result["failed"] == 0
    assert result["metrics"]["task_success_rate"] == 1.0
    assert result["metrics"]["tool_selection_accuracy"] == 1.0
    assert result["metrics"]["average_token_usage"] is None


@pytest.mark.asyncio
async def test_week2_evaluation_dataset_has_fifty_passing_cases():
    dataset = Path(__file__).parents[1] / "eval" / "datasets" / "week2.json"
    result = await evaluate(dataset)
    assert result["dataset_size"] == 50
    assert result["failed"] == 0
    assert result["metrics"]["task_success_rate"] == 1.0
    assert result["metrics"]["tool_selection_accuracy"] == 1.0
