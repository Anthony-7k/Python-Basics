import os

from dotenv import load_dotenv
from pathlib import Path


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

DEFAULT_USER_EMAIL = os.getenv(
    "DEFAULT_USER_EMAIL",
    "local-user@agent01.local",
)

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
