import json
from hashlib import sha256
from time import perf_counter
from urllib.parse import quote

from redis import Redis

from app.core.logging_config import get_logger
from app.core.settings import (
    RAG_CACHE_ENABLED,
    RAG_CACHE_TTL_SECONDS,
    REDIS_CONNECT_TIMEOUT_SECONDS,
    REDIS_SOCKET_TIMEOUT_SECONDS,
    REDIS_URL,
)


logger = get_logger(__name__)


def normalize_question(question: str) -> str:
    return " ".join(question.split())


def build_retrieval_cache_key(
    *,
    knowledge_base_id: str,
    knowledge_base_version: int,
    embedding_model: str,
    top_k: int,
    max_distance: float | None,
    question: str,
    retrieval_mode: str = "vector",
    candidate_multiplier: int = 1,
    keyword_top_k: int = 0,
    keyword_min_score: float = 0.0,
    rrf_k: int = 60,
    reranker_model: str = "none",
    rerank_lexical_weight: float = 0.0,
) -> str:
    normalized_question = normalize_question(
        question
    )
    question_hash = sha256(
        normalized_question.encode("utf-8")
    ).hexdigest()
    model_token = quote(
        embedding_model,
        safe="._-",
    )
    distance_token = (
        "none"
        if max_distance is None
        else format(max_distance, ".12g")
    )
    strategy = "|".join(
        (
            retrieval_mode,
            str(candidate_multiplier),
            str(keyword_top_k),
            format(keyword_min_score, ".12g"),
            str(rrf_k),
            reranker_model,
            format(rerank_lexical_weight, ".12g"),
        )
    )
    strategy_hash = sha256(
        strategy.encode("utf-8")
    ).hexdigest()[:16]

    return (
        "rag:retrieval:v2:"
        f"{knowledge_base_id}:"
        f"{knowledge_base_version}:"
        f"{model_token}:"
        f"{retrieval_mode}:"
        f"{strategy_hash}:"
        f"{top_k}:"
        f"{distance_token}:"
        f"{question_hash}"
    )


class RetrievalCacheService:
    def __init__(
        self,
        *,
        redis_url: str,
        ttl_seconds: int,
        enabled: bool = True,
        connect_timeout_seconds: float = 0.2,
        socket_timeout_seconds: float = 0.2,
        client=None,
    ) -> None:
        self.redis_url = redis_url
        self.ttl_seconds = ttl_seconds
        self.enabled = enabled
        self.connect_timeout_seconds = (
            connect_timeout_seconds
        )
        self.socket_timeout_seconds = (
            socket_timeout_seconds
        )
        self._client = client

    def _get_client(self):
        if self._client is None:
            self._client = Redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=(
                    self.connect_timeout_seconds
                ),
                socket_timeout=(
                    self.socket_timeout_seconds
                ),
            )

        return self._client

    def ping(self) -> bool:
        if not self.enabled:
            return True

        return bool(self._get_client().ping())

    def get_retrieval_result(
        self,
        key: str,
    ) -> tuple[list[dict] | None, float]:
        if not self.enabled:
            return None, 0.0

        started_at = perf_counter()

        try:
            payload = self._get_client().get(key)
        except Exception as exc:
            lookup_ms = (
                perf_counter() - started_at
            ) * 1000
            logger.warning(
                "redis cache get failed key=%s error=%s",
                key,
                exc,
            )
            return None, lookup_ms

        lookup_ms = (
            perf_counter() - started_at
        ) * 1000

        if payload is None:
            return None, lookup_ms

        try:
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")

            value = json.loads(payload)

            if not isinstance(value, list):
                raise ValueError(
                    "cached retrieval result is not a list"
                )

            if not all(
                isinstance(item, dict)
                for item in value
            ):
                raise ValueError(
                    "cached retrieval items must be objects"
                )

            return value, lookup_ms
        except (TypeError, ValueError) as exc:
            logger.warning(
                "redis cache payload ignored key=%s error=%s",
                key,
                exc,
            )
            return None, lookup_ms

    def set_retrieval_result(
        self,
        key: str,
        results: list[dict],
    ) -> bool:
        if not self.enabled:
            return False

        try:
            payload = json.dumps(
                results,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            self._get_client().set(
                key,
                payload,
                ex=self.ttl_seconds,
            )
            return True
        except Exception as exc:
            logger.warning(
                "redis cache set failed key=%s error=%s",
                key,
                exc,
            )
            return False


retrieval_cache_service = RetrievalCacheService(
    redis_url=REDIS_URL,
    ttl_seconds=RAG_CACHE_TTL_SECONDS,
    enabled=RAG_CACHE_ENABLED,
    connect_timeout_seconds=(
        REDIS_CONNECT_TIMEOUT_SECONDS
    ),
    socket_timeout_seconds=(
        REDIS_SOCKET_TIMEOUT_SECONDS
    ),
)
