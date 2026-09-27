from __future__ import annotations

import json
import logging

from app.logging_config import JsonFormatter, redact
from app.memory import MemoryService
from app.repositories import MemoryRepository


def test_long_term_memory_only_stores_explicit_preference(database):
    session = database.session_factory()
    service = MemoryService(MemoryRepository(session))
    assert service.consider_long_term("user-1", "你好，今天天气不错") is False
    assert service.consider_long_term("user-1", "请记住 以后请默认使用中文回答") is True
    values = MemoryRepository(session).list_for_user("user-1")
    assert len(values) == 1
    assert values[0].value_json["preference"] == "以后请默认使用中文回答"


def test_memory_rejects_secret_like_content(database):
    session = database.session_factory()
    service = MemoryService(MemoryRepository(session))
    assert (
        service.consider_long_term("user-1", "请记住 API_KEY=sk-example123456") is False
    )
    assert MemoryRepository(session).list_for_user("user-1") == []


def test_redaction_masks_sensitive_keys_and_values():
    redacted = redact(
        {
            "authorization": "Bearer abcdefghijk",
            "nested": {"api_key": "sk-secret123456", "safe": "visible"},
        }
    )
    assert redacted["authorization"] == "[REDACTED]"
    assert redacted["nested"]["api_key"] == "[REDACTED]"
    assert redacted["nested"]["safe"] == "visible"


def test_json_formatter_does_not_emit_bearer_token():
    record = logging.LogRecord(
        "test", logging.INFO, __file__, 1, "Bearer abcdefghijk", (), None
    )
    output = JsonFormatter().format(record)
    assert "abcdefghijk" not in output
    assert "[REDACTED]" in json.loads(output)["message"]
