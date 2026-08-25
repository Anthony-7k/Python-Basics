import json
import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()
PROJECT_ROOT = Path(__file__).resolve().parents[2]

CHROMA_PATH = Path(
    os.getenv(
        "CHROMA_PATH",
        str(PROJECT_ROOT / "data" / "chroma"),
    )
)

UPLOAD_DIR = Path(
    os.getenv(
        "UPLOAD_DIR",
        str(PROJECT_ROOT / "data" / "uploads"),
    )
)

MAX_UPLOAD_SIZE_BYTES = int(
    os.getenv(
        "MAX_UPLOAD_SIZE_BYTES",
        str(10 * 1024 * 1024),
    )
)

DEMO_AUTH_USERS_JSON = os.getenv(
    "DEMO_AUTH_USERS_JSON",
    "{}",
)


def _read_demo_auth_users(
    raw_value: str,
) -> dict[str, str]:
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "DEMO_AUTH_USERS_JSON must be valid JSON"
        ) from exc

    if not isinstance(parsed, dict):
        raise ValueError(
            "DEMO_AUTH_USERS_JSON must be a JSON object"
        )

    users: dict[str, str] = {}

    for token, email in parsed.items():
        if not isinstance(token, str) or not token:
            raise ValueError(
                "Demo authentication tokens must be non-empty strings"
            )
        if not isinstance(email, str) or "@" not in email:
            raise ValueError(
                "Demo authentication users must be email addresses"
            )
        users[token] = email.strip().lower()

    return users


DEMO_AUTH_USERS = _read_demo_auth_users(
    DEMO_AUTH_USERS_JSON
)

RATE_LIMIT_WINDOW_SECONDS = int(
    os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")
)
UPLOAD_RATE_LIMIT_REQUESTS = int(
    os.getenv("UPLOAD_RATE_LIMIT_REQUESTS", "10")
)
CHAT_RATE_LIMIT_REQUESTS = int(
    os.getenv("CHAT_RATE_LIMIT_REQUESTS", "30")
)


LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_MODEL = os.getenv("LLM_MODEL")
LLM_TIMEOUT_SECONDS = float(
    os.getenv(
        "LLM_TIMEOUT_SECONDS",
        "30",
    )
)


EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY")
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")

EMBEDDING_DIMENSIONS = int(
    os.getenv("EMBEDDING_DIMENSIONS", "1024")
)


def _read_bool(
    name: str,
    default: bool,
) -> bool:
    raw_value = os.getenv(name)

    if raw_value is None:
        return default

    normalized = raw_value.strip().lower()

    if normalized in {"1", "true", "yes", "on"}:
        return True

    if normalized in {"0", "false", "no", "off"}:
        return False

    raise ValueError(
        f"{name} must be a boolean value"
    )


REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379/0",
)
RAG_CACHE_ENABLED = _read_bool(
    "RAG_CACHE_ENABLED",
    True,
)
RAG_CACHE_TTL_SECONDS = int(
    os.getenv(
        "RAG_CACHE_TTL_SECONDS",
        "300",
    )
)
RAG_RETRIEVAL_MAX_DISTANCE = float(
    os.getenv(
        "RAG_RETRIEVAL_MAX_DISTANCE",
        "1.1",
    )
)
RAG_RETRIEVAL_MODE = os.getenv(
    "RAG_RETRIEVAL_MODE",
    "vector",
).strip().lower()
RAG_RETRIEVAL_CANDIDATE_MULTIPLIER = int(
    os.getenv(
        "RAG_RETRIEVAL_CANDIDATE_MULTIPLIER",
        "3",
    )
)
RAG_KEYWORD_TOP_K = int(
    os.getenv(
        "RAG_KEYWORD_TOP_K",
        "20",
    )
)
RAG_KEYWORD_MIN_SCORE = float(
    os.getenv(
        "RAG_KEYWORD_MIN_SCORE",
        "0.3",
    )
)
RAG_RRF_K = int(
    os.getenv(
        "RAG_RRF_K",
        "60",
    )
)
RAG_RERANKER_MODEL = os.getenv(
    "RAG_RERANKER_MODEL",
    "lexical-v1",
).strip()
RAG_RERANK_LEXICAL_WEIGHT = float(
    os.getenv(
        "RAG_RERANK_LEXICAL_WEIGHT",
        "0.7",
    )
)
REDIS_CONNECT_TIMEOUT_SECONDS = float(
    os.getenv(
        "REDIS_CONNECT_TIMEOUT_SECONDS",
        "0.2",
    )
)
REDIS_SOCKET_TIMEOUT_SECONDS = float(
    os.getenv(
        "REDIS_SOCKET_TIMEOUT_SECONDS",
        "0.2",
    )
)


def validate_settings():
    required_settings = {
        "LLM_API_KEY": LLM_API_KEY,
        "LLM_BASE_URL": LLM_BASE_URL,
        "LLM_MODEL": LLM_MODEL,
        "EMBEDDING_API_KEY": EMBEDDING_API_KEY,
        "EMBEDDING_BASE_URL": EMBEDDING_BASE_URL,
        "EMBEDDING_MODEL": EMBEDDING_MODEL,
    }

    missing_settings = [
        name
        for name, value in required_settings.items()
        if not value
    ]

    if missing_settings:
        raise RuntimeError(
            "Missing required settings: "
            + ", ".join(missing_settings)
        )

DATABASE_URL = os.getenv("DATABASE_URL")

DEFAULT_KNOWLEDGE_BASE_NAME = os.getenv(
    "DEFAULT_KNOWLEDGE_BASE_NAME",
    "Default Knowledge Base",
)

CONVERSATION_HISTORY_MAX_TURNS = int(
    os.getenv(
        "CONVERSATION_HISTORY_MAX_TURNS",
        "3",
    )
)

CONVERSATION_HISTORY_TOKEN_BUDGET = int(
    os.getenv(
        "CONVERSATION_HISTORY_TOKEN_BUDGET",
        "1800",
    )
)

CONVERSATION_SUMMARY_MAX_CHARS = int(
    os.getenv(
        "CONVERSATION_SUMMARY_MAX_CHARS",
        "2000",
    )
)


if CONVERSATION_HISTORY_MAX_TURNS < 1:
    raise ValueError(
        "CONVERSATION_HISTORY_MAX_TURNS must be at least 1"
    )

if CONVERSATION_HISTORY_TOKEN_BUDGET < 1:
    raise ValueError(
        "CONVERSATION_HISTORY_TOKEN_BUDGET must be at least 1"
    )

if CONVERSATION_SUMMARY_MAX_CHARS < 1:
    raise ValueError(
        "CONVERSATION_SUMMARY_MAX_CHARS must be at least 1"
    )

if RAG_CACHE_TTL_SECONDS < 1:
    raise ValueError(
        "RAG_CACHE_TTL_SECONDS must be at least 1"
    )

if RAG_RETRIEVAL_MAX_DISTANCE <= 0:
    raise ValueError(
        "RAG_RETRIEVAL_MAX_DISTANCE must be greater than 0"
    )

if RAG_RETRIEVAL_MODE not in {
    "vector",
    "hybrid",
    "rerank",
}:
    raise ValueError(
        "RAG_RETRIEVAL_MODE must be vector, hybrid, or rerank"
    )

if RAG_RETRIEVAL_CANDIDATE_MULTIPLIER < 1:
    raise ValueError(
        "RAG_RETRIEVAL_CANDIDATE_MULTIPLIER must be at least 1"
    )

if RAG_KEYWORD_TOP_K < 1:
    raise ValueError(
        "RAG_KEYWORD_TOP_K must be at least 1"
    )

if RAG_KEYWORD_MIN_SCORE < 0:
    raise ValueError(
        "RAG_KEYWORD_MIN_SCORE must be non-negative"
    )

if RAG_RRF_K < 1:
    raise ValueError(
        "RAG_RRF_K must be at least 1"
    )

if not 0 <= RAG_RERANK_LEXICAL_WEIGHT <= 1:
    raise ValueError(
        "RAG_RERANK_LEXICAL_WEIGHT must be between 0 and 1"
    )

if REDIS_CONNECT_TIMEOUT_SECONDS <= 0:
    raise ValueError(
        "REDIS_CONNECT_TIMEOUT_SECONDS must be greater than 0"
    )

if REDIS_SOCKET_TIMEOUT_SECONDS <= 0:
    raise ValueError(
        "REDIS_SOCKET_TIMEOUT_SECONDS must be greater than 0"
    )

if RATE_LIMIT_WINDOW_SECONDS < 1:
    raise ValueError(
        "RATE_LIMIT_WINDOW_SECONDS must be at least 1"
    )

if UPLOAD_RATE_LIMIT_REQUESTS < 1:
    raise ValueError(
        "UPLOAD_RATE_LIMIT_REQUESTS must be at least 1"
    )

if CHAT_RATE_LIMIT_REQUESTS < 1:
    raise ValueError(
        "CHAT_RATE_LIMIT_REQUESTS must be at least 1"
    )
