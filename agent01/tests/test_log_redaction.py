import json
import logging

from app.core.logging_config import (
    JsonLogFormatter,
)


def test_json_logs_redact_credentials_and_drop_body_fields():
    record = logging.LogRecord(
        name="security-test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=(
            "Authorization: Bearer super-secret-token "
            "api_key=another-secret"
        ),
        args=(),
        exc_info=None,
    )
    record.event = "http_request"
    record.request_id = "request-123"
    record.route = "/api/v1/chat"
    record.question = "完整敏感问题不应进入日志"

    payload = json.loads(
        JsonLogFormatter().format(record)
    )
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
    )

    assert payload["event"] == "http_request"
    assert payload["request_id"] == "request-123"
    assert "super-secret-token" not in serialized
    assert "another-secret" not in serialized
    assert "完整敏感问题" not in serialized
    assert serialized.count("[REDACTED]") == 2
