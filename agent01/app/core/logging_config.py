import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any

from app.core.settings import (
    DEMO_AUTH_USERS,
    EMBEDDING_API_KEY,
    LLM_API_KEY,
)


SAFE_LOG_FIELDS = (
    "event",
    "request_id",
    "route",
    "method",
    "status_code",
    "latency_ms",
    "actor_id",
    "knowledge_base_id",
    "document_id",
    "retrieval_mode",
    "error_code",
)

BEARER_PATTERN = re.compile(
    r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"
)
API_KEY_PATTERN = re.compile(
    r"(?i)((?:api[_-]?key|token)\s*[:=]\s*)[^\s,;]+"
)


def redact_sensitive_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    redacted = BEARER_PATTERN.sub(
        r"\1[REDACTED]",
        value,
    )
    redacted = API_KEY_PATTERN.sub(
        r"\1[REDACTED]",
        redacted,
    )

    configured_secrets = (
        LLM_API_KEY,
        EMBEDDING_API_KEY,
        *DEMO_AUTH_USERS.keys(),
    )
    for secret in configured_secrets:
        if secret:
            redacted = redacted.replace(
                secret,
                "[REDACTED]",
            )

    return redacted


class JsonLogFormatter(logging.Formatter):
    def format(
        self,
        record: logging.LogRecord,
    ) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_sensitive_text(
                record.getMessage()
            ),
        }

        for field_name in SAFE_LOG_FIELDS:
            value = getattr(
                record,
                field_name,
                None,
            )
            if value is not None:
                payload[field_name] = (
                    redact_sensitive_text(value)
                )

        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )


def setup_logging(
    level: int = logging.INFO,
) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(level)

    logging.getLogger("httpx").setLevel(
        logging.WARNING
    )

    logging.getLogger("httpcore").setLevel(
        logging.WARNING
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
