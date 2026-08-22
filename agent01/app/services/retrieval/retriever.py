from dataclasses import dataclass
from time import perf_counter

from app.core.settings import (
    EMBEDDING_MODEL,
    RAG_KEYWORD_MIN_SCORE,
    RAG_KEYWORD_TOP_K,
    RAG_RERANKER_MODEL,
    RAG_RERANK_LEXICAL_WEIGHT,
    RAG_RETRIEVAL_CANDIDATE_MULTIPLIER,
    RAG_RETRIEVAL_MODE,
    RAG_RRF_K,
)
from app.services.cache import (
    RetrievalCacheService,
    build_retrieval_cache_key,
    retrieval_cache_service,
)
from app.services.retrieval.fusion import (
    lexical_rerank,
    reciprocal_rank_fusion,
)
from app.services.retrieval.keyword_retriever import (
    retrieve_keywords,
)
from app.services.vector_stores.vector_store import (
    list_chunks,
    query_chunks,
)


@dataclass(frozen=True)
class RetrievalOutcome:
    items: list[dict]
    cache_hit: bool
    cache_lookup_ms: float
    retrieval_ms: float
    mode: str = "vector"
    rerank_ms: float = 0.0
    rerank_candidate_count: int = 0


def _retrieve_with_diagnostics(
    query_text: str,
    knowledge_base_id: str,
    top_k: int = 5,
    max_distance: float | None = None,
    *,
    mode: str | None = None,
    candidate_multiplier: int | None = None,
    keyword_top_k: int | None = None,
    keyword_min_score: float | None = None,
    rrf_k: int | None = None,
    rerank_lexical_weight: float | None = None,
) -> tuple[list[dict], float]:
    selected_mode = mode or RAG_RETRIEVAL_MODE
    selected_candidate_multiplier = (
        candidate_multiplier
        if candidate_multiplier is not None
        else RAG_RETRIEVAL_CANDIDATE_MULTIPLIER
    )
    selected_keyword_top_k = (
        keyword_top_k
        if keyword_top_k is not None
        else RAG_KEYWORD_TOP_K
    )
    selected_keyword_min_score = (
        keyword_min_score
        if keyword_min_score is not None
        else RAG_KEYWORD_MIN_SCORE
    )
    selected_rrf_k = rrf_k if rrf_k is not None else RAG_RRF_K
    selected_rerank_weight = (
        rerank_lexical_weight
        if rerank_lexical_weight is not None
        else RAG_RERANK_LEXICAL_WEIGHT
    )

    if selected_mode not in {"vector", "hybrid", "rerank"}:
        raise ValueError(
            "retrieval mode must be vector, hybrid, or rerank"
        )

    vector_limit = (
        top_k
        if selected_mode == "vector"
        else top_k * selected_candidate_multiplier
    )
    raw_results = query_chunks(
        query_text=query_text,
        knowledge_base_id=(
            knowledge_base_id
        ),
        n_results=vector_limit,
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

    if selected_mode == "vector":
        return results[:top_k], 0.0

    keyword_items = retrieve_keywords(
        query_text,
        list_chunks(knowledge_base_id),
        limit=selected_keyword_top_k,
        min_score=selected_keyword_min_score,
    )
    fused_items = reciprocal_rank_fusion(
        results,
        keyword_items,
        top_k=len(results) + len(keyword_items),
        rank_constant=selected_rrf_k,
    )

    if selected_mode == "hybrid":
        return fused_items[:top_k], 0.0

    rerank_started_at = perf_counter()
    reranked = lexical_rerank(
        query_text,
        fused_items,
        top_k=top_k,
        lexical_weight=selected_rerank_weight,
    )
    rerank_ms = (
        perf_counter() - rerank_started_at
    ) * 1000
    rerank_candidate_count = len(fused_items)

    for item in reranked:
        item["rerank_candidate_count"] = (
            rerank_candidate_count
        )

    return reranked, rerank_ms


def retrieve(
    query_text: str,
    knowledge_base_id: str,
    top_k: int = 5,
    max_distance: float | None = None,
    *,
    mode: str | None = None,
    candidate_multiplier: int | None = None,
    keyword_top_k: int | None = None,
    keyword_min_score: float | None = None,
    rrf_k: int | None = None,
    rerank_lexical_weight: float | None = None,
) -> list[dict]:
    items, _ = _retrieve_with_diagnostics(
        query_text=query_text,
        knowledge_base_id=knowledge_base_id,
        top_k=top_k,
        max_distance=max_distance,
        mode=mode,
        candidate_multiplier=candidate_multiplier,
        keyword_top_k=keyword_top_k,
        keyword_min_score=keyword_min_score,
        rrf_k=rrf_k,
        rerank_lexical_weight=rerank_lexical_weight,
    )

    return items


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
    mode: str | None = None,
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
    selected_mode = mode or RAG_RETRIEVAL_MODE
    cache_key = build_retrieval_cache_key(
        knowledge_base_id=knowledge_base_id,
        knowledge_base_version=(
            knowledge_base_version
        ),
        embedding_model=model_name,
        top_k=top_k,
        max_distance=max_distance,
        question=query_text,
        retrieval_mode=selected_mode,
        candidate_multiplier=(
            RAG_RETRIEVAL_CANDIDATE_MULTIPLIER
        ),
        keyword_top_k=RAG_KEYWORD_TOP_K,
        keyword_min_score=RAG_KEYWORD_MIN_SCORE,
        rrf_k=RAG_RRF_K,
        reranker_model=RAG_RERANKER_MODEL,
        rerank_lexical_weight=(
            RAG_RERANK_LEXICAL_WEIGHT
        ),
    )
    cached_items, cache_lookup_ms = (
        service.get_retrieval_result(
            cache_key
        )
    )

    if cached_items is not None:
        cached_candidate_count = (
            cached_items[0].get(
                "rerank_candidate_count",
                0,
            )
            if cached_items
            else 0
        )
        return RetrievalOutcome(
            items=cached_items,
            cache_hit=True,
            cache_lookup_ms=cache_lookup_ms,
            retrieval_ms=0.0,
            mode=selected_mode,
            rerank_candidate_count=(
                cached_candidate_count
            ),
        )

    retrieval_started_at = perf_counter()
    items, rerank_ms = _retrieve_with_diagnostics(
        query_text=query_text,
        knowledge_base_id=knowledge_base_id,
        top_k=top_k,
        max_distance=max_distance,
        mode=selected_mode,
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
        mode=selected_mode,
        rerank_ms=rerank_ms,
        rerank_candidate_count=(
            items[0].get(
                "rerank_candidate_count",
                0,
            )
            if items
            else 0
        ),
    )
