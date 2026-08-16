from unittest.mock import patch

import httpx
import pytest
from openai import APITimeoutError, OpenAIError

from app.core.exceptions import (
    UpstreamServiceError,
    UpstreamTimeoutError,
)
from app.services.llm.llm_client import generate_answer


def test_generate_answer_converts_timeout():
    request = httpx.Request(
        "POST",
        "https://example.com/v1/chat/completions",
    )

    with patch(
        "app.services.llm.llm_client.client.chat.completions.create",
        side_effect=APITimeoutError(request),
    ):
        with pytest.raises(UpstreamTimeoutError) as exc_info:
            generate_answer(
                system_prompt="测试系统提示词",
                user_prompt="测试问题",
            )

    assert str(exc_info.value) == "LLM request timed out"
    assert isinstance(
        exc_info.value.__cause__,
        APITimeoutError,
    )


def test_generate_answer_converts_openai_error():
    with patch(
        "app.services.llm.llm_client.client.chat.completions.create",
        side_effect=OpenAIError("上游敏感错误"),
    ):
        with pytest.raises(UpstreamServiceError) as exc_info:
            generate_answer(
                system_prompt="测试系统提示词",
                user_prompt="测试问题",
            )

    assert str(exc_info.value) == "LLM request failed"
    assert isinstance(
        exc_info.value.__cause__,
        OpenAIError,
    )