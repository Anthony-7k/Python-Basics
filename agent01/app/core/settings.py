import os

from dotenv import load_dotenv


load_dotenv()


LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_MODEL = os.getenv("LLM_MODEL")


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