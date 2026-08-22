from app.services.retrieval.keyword_retriever import (
    bm25_scores,
)


def reciprocal_rank_fusion(
    vector_items: list[dict],
    keyword_items: list[dict],
    *,
    top_k: int,
    rank_constant: int = 60,
) -> list[dict]:
    fused: dict[str, dict] = {}

    for source_name, items in (
        ("vector", vector_items),
        ("keyword", keyword_items),
    ):
        for rank, item in enumerate(items, start=1):
            chunk_id = item["chunk_id"]
            current = fused.setdefault(
                chunk_id,
                {
                    **item,
                    "rrf_score": 0.0,
                    "vector_rank": None,
                    "keyword_rank": None,
                },
            )
            current["rrf_score"] += 1 / (
                rank_constant + rank
            )
            current[f"{source_name}_rank"] = rank

            if source_name == "vector":
                current["distance"] = item.get("distance")

            if source_name == "keyword":
                current["keyword_score"] = item.get(
                    "keyword_score",
                    0.0,
                )

    ranked = sorted(
        fused.values(),
        key=lambda item: (
            -item["rrf_score"],
            item["vector_rank"] or float("inf"),
            item["keyword_rank"] or float("inf"),
            item["chunk_id"],
        ),
    )

    return ranked[:top_k]


def lexical_rerank(
    query_text: str,
    items: list[dict],
    *,
    top_k: int,
    lexical_weight: float,
) -> list[dict]:
    if not items:
        return []

    lexical_scores = bm25_scores(query_text, items)
    max_lexical = max(lexical_scores, default=0.0) or 1.0
    max_rrf = max(
        (item.get("rrf_score", 0.0) for item in items),
        default=0.0,
    ) or 1.0
    reranked = []

    for item, lexical_score in zip(items, lexical_scores):
        result = dict(item)
        result["rerank_score"] = (
            lexical_weight * lexical_score / max_lexical
            + (1 - lexical_weight)
            * result.get("rrf_score", 0.0)
            / max_rrf
        )
        reranked.append(result)

    reranked.sort(
        key=lambda item: (
            -item["rerank_score"],
            -item.get("rrf_score", 0.0),
            item["chunk_id"],
        )
    )

    return reranked[:top_k]
