from app.services.retrieval.fusion import (
    lexical_rerank,
    reciprocal_rank_fusion,
)
from app.services.retrieval.keyword_retriever import (
    retrieve_keywords,
    tokenize,
)


def test_tokenize_preserves_numbers_and_chinese_bigrams():
    tokens = tokenize("A-17 员工年假 10 天")

    assert "a" in tokens
    assert "17" in tokens
    assert "员工" in tokens
    assert "年假" in tokens
    assert "10" in tokens


def test_bm25_prefers_exact_numeric_policy():
    items = [
        {
            "chunk_id": "five-days",
            "content": "工作满一年但不满十年，每年享有5天年假。",
            "metadata": {},
        },
        {
            "chunk_id": "ten-days",
            "content": "工作满10年但不满20年，每年享有10天年假。",
            "metadata": {},
        },
    ]

    results = retrieve_keywords(
        "工作满10年但不满20年有多少天年假？",
        items,
        limit=2,
    )

    assert results[0]["chunk_id"] == "ten-days"
    assert results[0]["keyword_score"] > 0


def test_bm25_threshold_filters_weak_common_term_match():
    items = [
        {
            "chunk_id": "handbook",
            "content": "员工应妥善保管公司电脑。",
            "metadata": {},
        }
    ]

    results = retrieve_keywords(
        "员工股票期权如何行权？",
        items,
        limit=3,
        min_score=0.3,
    )

    assert results == []


def test_rrf_deduplicates_and_combines_ranks():
    vector = [
        {
            "chunk_id": "a",
            "content": "A",
            "metadata": {},
            "distance": 0.2,
        },
        {
            "chunk_id": "b",
            "content": "B",
            "metadata": {},
            "distance": 0.3,
        },
    ]
    keyword = [
        {
            "chunk_id": "b",
            "content": "B",
            "metadata": {},
            "distance": None,
            "keyword_score": 3.0,
        },
        {
            "chunk_id": "c",
            "content": "C",
            "metadata": {},
            "distance": None,
            "keyword_score": 2.0,
        },
    ]

    results = reciprocal_rank_fusion(
        vector,
        keyword,
        top_k=3,
        rank_constant=60,
    )

    assert [item["chunk_id"] for item in results] == [
        "b",
        "a",
        "c",
    ]
    assert results[0]["vector_rank"] == 2
    assert results[0]["keyword_rank"] == 1


def test_lexical_rerank_keeps_stable_schema():
    items = [
        {
            "chunk_id": "general",
            "content": "员工可以申请年假。",
            "metadata": {},
            "distance": 0.1,
            "rrf_score": 0.03,
        },
        {
            "chunk_id": "exact",
            "content": "工作满20年及以上享有15天年假。",
            "metadata": {},
            "distance": 0.2,
            "rrf_score": 0.02,
        },
    ]

    results = lexical_rerank(
        "工作满20年有多少天年假？",
        items,
        top_k=2,
        lexical_weight=0.8,
    )

    assert results[0]["chunk_id"] == "exact"
    assert "rerank_score" in results[0]
