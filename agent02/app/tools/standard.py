from __future__ import annotations

import asyncio
from datetime import date, timedelta
from decimal import Decimal, DivisionByZero, InvalidOperation
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from app.domain import RiskLevel
from app.tools.base import BaseTool, ToolContext, ToolExecutionFailure


class CalculatorArgs(BaseModel):
    operation: Literal["add", "subtract", "multiply", "divide"]
    left: Decimal
    right: Decimal


class CalculatorTool(BaseTool[CalculatorArgs]):
    name = "calculator"
    description = "Perform deterministic arithmetic without evaluating arbitrary code"
    args_model = CalculatorArgs

    async def execute(
        self, arguments: CalculatorArgs, context: ToolContext
    ) -> dict[str, Any]:
        try:
            if arguments.operation == "add":
                value = arguments.left + arguments.right
            elif arguments.operation == "subtract":
                value = arguments.left - arguments.right
            elif arguments.operation == "multiply":
                value = arguments.left * arguments.right
            else:
                value = arguments.left / arguments.right
        except (DivisionByZero, InvalidOperation) as exc:
            raise ToolExecutionFailure(
                "invalid_calculation", "Calculation is not defined", retryable=False
            ) from exc
        normalized = int(value) if value == value.to_integral() else float(value)
        return {"result": normalized, "operation": arguments.operation}


class SearchArgs(BaseModel):
    query: str = Field(min_length=1, max_length=1000)


class SearchTool(BaseTool[SearchArgs]):
    name = "search"
    description = "Search public information through a deterministic demo adapter"
    args_model = SearchArgs

    async def execute(
        self, arguments: SearchArgs, context: ToolContext
    ) -> dict[str, Any]:
        return {
            "answer": f"公共信息搜索结果：{arguments.query}",
            "results": [
                {
                    "title": "示例公共信息",
                    "url": "https://example.com/public-information",
                    "snippet": "This is deterministic demo data; replace the adapter for production.",
                }
            ],
            "sources": [
                {
                    "source_id": "WEB1",
                    "url": "https://example.com/public-information",
                    "untrusted": True,
                }
            ],
        }


class CalendarArgs(BaseModel):
    start_date: date
    workdays: int = Field(ge=1, le=60)


class CalendarTool(BaseTool[CalendarArgs]):
    name = "calendar"
    description = (
        "Calculate a sequence of working dates while skipping weekends; "
        "never create tasks or reminders"
    )
    args_model = CalendarArgs

    async def execute(
        self, arguments: CalendarArgs, context: ToolContext
    ) -> dict[str, Any]:
        current = arguments.start_date
        dates: list[str] = []
        while len(dates) < arguments.workdays:
            if current.weekday() < 5:
                dates.append(current.isoformat())
            current += timedelta(days=1)
        return {
            "workdays": dates,
            "start_date": arguments.start_date.isoformat(),
            "end_date": dates[-1],
        }


class TaskArgs(BaseModel):
    action: Literal["create"] = "create"
    title: str = Field(min_length=1, max_length=200)
    due_date: date | None = None


class TaskTool(BaseTool[TaskArgs]):
    name = "task"
    description = (
        "Create a task or reminder when the user explicitly requests one; "
        "execution requires human approval"
    )
    risk_level = RiskLevel.HIGH_RISK
    args_model = TaskArgs

    def __init__(self) -> None:
        self.created_tasks: dict[str, dict[str, Any]] = {}

    async def execute(
        self, arguments: TaskArgs, context: ToolContext
    ) -> dict[str, Any]:
        key = context.idempotency_key
        if not key:
            raise ToolExecutionFailure(
                "missing_idempotency_key",
                "High-risk task creation requires an idempotency key",
                retryable=False,
            )
        if key in self.created_tasks:
            return {**self.created_tasks[key], "idempotent_replay": True}
        created = {
            "task_action_id": str(uuid4()),
            "title": arguments.title,
            "due_date": arguments.due_date.isoformat() if arguments.due_date else None,
            "created": True,
            "idempotent_replay": False,
        }
        self.created_tasks[key] = created
        return created


class FailureArgs(BaseModel):
    failures_before_success: int = Field(default=1, ge=0, le=5)
    delay_seconds: float = Field(default=0, ge=0, le=30)


class FailureTool(BaseTool[FailureArgs]):
    """Fault-injection tool used only by tests and the recovery demo."""

    name = "failure_demo"
    description = "Demonstrate retry and timeout behavior in a controlled environment"
    args_model = FailureArgs

    def __init__(self) -> None:
        self.attempts: dict[str, int] = {}

    async def execute(
        self, arguments: FailureArgs, context: ToolContext
    ) -> dict[str, Any]:
        attempt = self.attempts.get(context.task_id, 0) + 1
        self.attempts[context.task_id] = attempt
        if arguments.delay_seconds:
            await asyncio.sleep(arguments.delay_seconds)
        if attempt <= arguments.failures_before_success:
            raise ToolExecutionFailure(
                "demo_transient_failure", "Injected transient failure", retryable=True
            )
        return {"answer": "故障恢复成功", "attempt": attempt}
