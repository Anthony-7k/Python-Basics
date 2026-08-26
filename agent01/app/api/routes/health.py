from collections.abc import Callable
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.logging_config import get_logger
from app.core.settings import (
    RAG_CACHE_ENABLED,
    UPLOAD_DIR,
)
from app.db.session import engine
from app.services.cache.cache_service import (
    retrieval_cache_service,
)
from app.services.vector_stores.vector_store import (
    collection,
)


router = APIRouter()
logger = get_logger(__name__)


def _check_database() -> str:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return "ok"


def _check_vector_store() -> str:
    collection.count()
    return "ok"


def _check_upload_storage() -> str:
    UPLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )
    with NamedTemporaryFile(
        dir=UPLOAD_DIR,
        prefix=".readiness-",
    ):
        pass
    return "ok"


def _check_redis() -> str:
    if not RAG_CACHE_ENABLED:
        return "disabled"

    if not retrieval_cache_service.ping():
        raise RuntimeError("Redis ping failed")
    return "ok"


READINESS_CHECKS: tuple[
    tuple[str, Callable[[], str]],
    ...,
] = (
    ("database", _check_database),
    ("vector_store", _check_vector_store),
    ("upload_storage", _check_upload_storage),
    ("redis", _check_redis),
)


@router.get("/health")
def health_check():
    return {
        "status": "ok"
    }


@router.get("/ready")
def readiness_check(response: Response):
    checks: dict[str, str] = {}

    for check_name, check in READINESS_CHECKS:
        try:
            checks[check_name] = check()
        except Exception:
            checks[check_name] = "failed"
            logger.warning(
                "readiness check failed",
                extra={
                    "event": "readiness_check",
                    "status": "failed",
                    "error_code": (
                        f"{check_name}_unavailable"
                    ),
                },
            )

    if "failed" in checks.values():
        response.status_code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
        )
        readiness_status = "not_ready"
    else:
        readiness_status = "ready"

    return {
        "status": readiness_status,
        "checks": checks,
    }
