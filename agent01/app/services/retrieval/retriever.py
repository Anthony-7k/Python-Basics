from dataclasses import dataclass
from time import perf_counter

from app.core.settings import EMBEDDING_MODEL
from app.services.cache import (
    RetrievalCacheService,
    build_retrieval_cache_key,
    retrieval_cache_service,
)
from app.services.vector_stores.vector_store import query_chunks


@dataclass(frozen=True)
class RetrievalOutcome:
    items: list[dict]
    cache_hit: bool
    cache_lookup_ms: float
    retrieval_ms: float


def retrieve(
    query_text: str,
    knowledge_base_id: str,
    top_k: int = 5,
    max_distance: float | None = None,
) -> list[dict]:
    raw_results = query_chunks(
        query_text=query_text,
        knowledge_base_id=(
            knowledge_base_id
        ),
        n_results=top_k,
    )

    ids = raw_results.get("ids", [[]])[0]
    documents = raw_results.get("documents", [[]])[0]
    metadatas = raw_results.get("metadatas", [[]])[0]
    distances = raw_results.get("distances", [[]])[0]

    results = []

    for chunk_id, content, metadata, distance in zip(
            ids,
            documents,
            metadatas,
            distances,
    ):
        if (
                max_distance is not None
                and distance > max_distance
        ):
            continue

        results.append(
            {
                "chunk_id": chunk_id,
                "content": content,
                "distance": float(distance),
                "metadata": dict(
                    metadata or {}
                ),
            }
        )

    return results


def retrieve_with_cache(
    query_text: str,
    knowledge_base_id: str,
    knowledge_base_version: int,
    top_k: int = 5,
    max_distance: float | None = None,
    *,
    embedding_model: str | None = None,
    cache_service: (
        RetrievalCacheService | None
    ) = None,
) -> RetrievalOutcome:
    service = (
        cache_service
        if cache_service is not None
        else retrieval_cache_service
    )
    model_name = (
        embedding_model
        or EMBEDDING_MODEL
        or "unknown"
    )
    cache_key = build_retrieval_cache_key(
        knowledge_base_id=knowledge_base_id,
        knowledge_base_version=(
            knowledge_base_version
        ),
        embedding_model=model_name,
        top_k=top_k,
        max_distance=max_distance,
        question=query_text,
    )
    cached_items, cache_lookup_ms = (
        service.get_retrieval_result(
            cache_key
        )
    )

    if cached_items is not None:
        return RetrievalOutcome(
            items=cached_items,
            cache_hit=True,
            cache_lookup_ms=cache_lookup_ms,
            retrieval_ms=0.0,
        )

    retrieval_started_at = perf_counter()
    items = retrieve(
        query_text=query_text,
        knowledge_base_id=knowledge_base_id,
        top_k=top_k,
        max_distance=max_distance,
    )
    retrieval_ms = (
        perf_counter() - retrieval_started_at
    ) * 1000

    service.set_retrieval_result(
        cache_key,
        items,
    )

    return RetrievalOutcome(
        items=items,
        cache_hit=False,
        cache_lookup_ms=cache_lookup_ms,
        retrieval_ms=retrieval_ms,
    )
