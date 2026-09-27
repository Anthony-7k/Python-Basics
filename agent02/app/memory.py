from __future__ import annotations

import re
from typing import Any

from app.logging_config import SENSITIVE_KEY, SENSITIVE_VALUE
from app.repositories import MemoryRepository

PREFERENCE_PATTERN = re.compile(
    r"(?:我喜欢|我偏好|请记住|以后请|默认使用)\s*(.{2,120})",
    re.IGNORECASE,
)


class MemoryService:
    """Stores session state and only explicit, non-sensitive long-term preferences."""

    def __init__(self, repository: MemoryRepository) -> None:
        self.repository = repository

    def save_session_state(self, state: dict[str, Any]) -> None:
        self.repository.save_short_term(
            state["user_id"],
            state["session_id"],
            "latest_task",
            {
                "task_id": state["task_id"],
                "status": state.get("status"),
                "answer": state.get("answer", ""),
                "tool_results": state.get("tool_results", []),
            },
            tenant_id=state["tenant_id"],
        )

    def consider_long_term(
        self, user_id: str, message: str, *, tenant_id: str = "legacy"
    ) -> bool:
        if SENSITIVE_KEY.search(message) or SENSITIVE_VALUE.search(message):
            return False
        match = PREFERENCE_PATTERN.search(message)
        if not match:
            return False
        preference = match.group(1).strip("。.!！ ")
        if not preference:
            return False
        self.repository.save_long_term(
            user_id,
            "explicit_preference",
            {"preference": preference},
            tenant_id=tenant_id,
        )
        return True
