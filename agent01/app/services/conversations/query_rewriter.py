from __future__ import annotations

import json
import math
import re
from collections.abc import Callable

from app.core.logging_config import get_logger
from app.core.settings import (
    CONVERSATION_HISTORY_TOKEN_BUDGET,
    CONVERSATION_SUMMARY_MAX_CHARS,
)
from app.prompts.query_rewrite_prompt import (
    QUERY_REWRITE_SYSTEM_PROMPT,
    SUMMARY_SYSTEM_PROMPT,
    build_query_rewrite_prompt,
    build_summary_prompt,
)
from app.services.llm.llm_client import (
    generate_answer,
)


logger = get_logger(__name__)

HistoryItem = dict[str, object]
LLMGenerate = Callable[[str, str], str]

_CJK_PATTERN = re.compile(
    r"[\u3400-\u4dbf\u4e00-\u9fff]"
)


def estimate_text_tokens(text: str) -> int:
    if not text:
        return 0

    cjk_count = len(
        _CJK_PATTERN.findall(text)
    )
    other_count = len(text) - cjk_count

    return max(
        1,
        cjk_count
        + math.ceil(other_count / 4),
    )


def _truncate_to_token_budget(
    text: str,
    token_budget: int,
) -> str:
    if token_budget < 1:
        return ""

    if estimate_text_tokens(text) <= token_budget:
        return text

    low = 0
    high = len(text)

    while low < high:
        middle = (low + high + 1) // 2

        if (
            estimate_text_tokens(
                text[:middle]
            )
            <= token_budget
        ):
            low = middle
        else:
            high = middle - 1

    return text[:low].rstrip()


def _format_history_item(
    item: HistoryItem,
) -> str:
    role = str(item.get("role", "unknown"))
    content = str(item.get("content", ""))
    source_summary = item.get(
        "source_summary"
    )

    text = f"{role}: {content}"

    if source_summary:
        text += "\nsource_summary: "
        text += json.dumps(
            source_summary,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    return text


def fit_context_to_token_budget(
    history: list[HistoryItem],
    conversation_summary: str | None,
    token_budget: int = (
        CONVERSATION_HISTORY_TOKEN_BUDGET
    ),
) -> tuple[list[HistoryItem], str | None]:
    summary = (
        conversation_summary.strip()
        if conversation_summary
        else None
    )
    summary_budget = 0

    if summary:
        summary_budget = min(
            estimate_text_tokens(summary),
            max(1, token_budget // 3),
        )
        summary = _truncate_to_token_budget(
            summary,
            summary_budget,
        )

    remaining_budget = max(
        0,
        token_budget - summary_budget,
    )
    selected_reversed: list[
        HistoryItem
    ] = []

    for item in reversed(history):
        item_tokens = estimate_text_tokens(
            _format_history_item(item)
        )

        if item_tokens > remaining_budget:
            if (
                not selected_reversed
                and remaining_budget > 0
            ):
                truncated_item = dict(item)
                role_overhead = (
                    estimate_text_tokens(
                        str(
                            item.get(
                                "role",
                                "unknown",
                            )
                        )
                        + ": "
                    )
                )
                truncated_item["content"] = (
                    _truncate_to_token_budget(
                        str(
                            item.get(
                                "content",
                                "",
                            )
                        ),
                        max(
                            1,
                            remaining_budget
                            - role_overhead,
                        ),
                    )
                )
                truncated_item[
                    "source_summary"
                ] = None
                selected_reversed.append(
                    truncated_item
                )
            break

        selected_reversed.append(item)
        remaining_budget -= item_tokens

    return (
        list(reversed(selected_reversed)),
        summary,
    )


def fit_summary_messages_to_budget(
    messages: list[HistoryItem],
    existing_summary: str | None,
    token_budget: int,
) -> list[HistoryItem]:
    summary_tokens = estimate_text_tokens(
        existing_summary or ""
    )
    remaining_budget = max(
        1,
        token_budget
        - min(
            summary_tokens,
            max(1, token_budget // 3),
        ),
    )
    selected: list[HistoryItem] = []

    for item in messages:
        item_tokens = estimate_text_tokens(
            _format_history_item(item)
        )

        if item_tokens > remaining_budget:
            if selected:
                break

            truncated_item = dict(item)
            role_overhead = estimate_text_tokens(
                str(item.get("role", "unknown"))
                + ": "
            )
            truncated_item["content"] = (
                _truncate_to_token_budget(
                    str(item.get("content", "")),
                    max(
                        1,
                        remaining_budget
                        - role_overhead,
                    ),
                )
            )
            truncated_item["source_summary"] = None
            selected.append(truncated_item)
            break

        selected.append(item)
        remaining_budget -= item_tokens

    return selected


def format_history(
    history: list[HistoryItem],
) -> str:
    return "\n\n".join(
        _format_history_item(item)
        for item in history
    )


def condense_question(
    history: list[HistoryItem],
    current_question: str,
    conversation_summary: str | None = None,
    token_budget: int = (
        CONVERSATION_HISTORY_TOKEN_BUDGET
    ),
    llm_generate: LLMGenerate | None = None,
) -> str:
    original_question = current_question.strip()

    if not history and not conversation_summary:
        return original_question

    bounded_history, bounded_summary = (
        fit_context_to_token_budget(
            history=history,
            conversation_summary=(
                conversation_summary
            ),
            token_budget=token_budget,
        )
    )

    if not bounded_history and not bounded_summary:
        return original_question

    generator = llm_generate or generate_answer
    user_prompt = build_query_rewrite_prompt(
        current_question=original_question,
        history_text=format_history(
            bounded_history
        ),
        conversation_summary=bounded_summary,
    )

    try:
        rewritten = generator(
            QUERY_REWRITE_SYSTEM_PROMPT,
            user_prompt,
        )
    except Exception:
        logger.warning(
            "query rewrite failed; using original question",
            exc_info=True,
        )
        return original_question

    if not rewritten:
        return original_question

    standalone_question = (
        rewritten.strip().splitlines()[0].strip()
    )

    for prefix in (
        "独立问题：",
        "独立问题:",
        "Standalone question:",
    ):
        if standalone_question.startswith(prefix):
            standalone_question = (
                standalone_question[
                    len(prefix):
                ].strip()
            )

    standalone_question = (
        standalone_question.strip("\"'“”")
    )

    if (
        not standalone_question
        or len(standalone_question) > 2000
    ):
        return original_question

    return standalone_question


def summarize_conversation(
    existing_summary: str | None,
    messages: list[HistoryItem],
    token_budget: int = (
        CONVERSATION_HISTORY_TOKEN_BUDGET
    ),
    max_chars: int = (
        CONVERSATION_SUMMARY_MAX_CHARS
    ),
    llm_generate: LLMGenerate | None = None,
) -> str:
    bounded_messages = (
        fit_summary_messages_to_budget(
            messages=messages,
            existing_summary=existing_summary,
            token_budget=token_budget,
        )
    )

    if not bounded_messages:
        return existing_summary or ""

    generator = llm_generate or generate_answer
    summary = generator(
        SUMMARY_SYSTEM_PROMPT,
        build_summary_prompt(
            existing_summary=(
                _truncate_to_token_budget(
                    existing_summary or "",
                    max(1, token_budget // 3),
                )
                or None
            ),
            messages_text=format_history(
                bounded_messages
            ),
        ),
    )

    if not summary:
        return existing_summary or ""

    return summary.strip()[:max_chars]
