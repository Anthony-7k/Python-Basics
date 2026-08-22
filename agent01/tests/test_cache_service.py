import json

from app.services.cache import (
    RetrievalCacheService,
    build_retrieval_cache_key,
)


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.set_calls = []

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ex):
        self.values[key] = value
        self.set_calls.append(
            (key, value, ex)
        )


class BrokenRedis:
    def get(self, key):
        raise RuntimeError("redis unavailable")

    def set(self, key, value, ex):
        raise RuntimeError("redis unavailable")


def test_cache_key_normalizes_question_and_scopes_inputs():
    common = {
        "knowledge_base_id": "kb-a",
        "knowledge_base_version": 7,
        "embedding_model": "text-embedding:v4",
        "top_k": 5,
        "max_distance": 0.98,
    }
    first = build_retrieval_cache_key(
        question="  上海  住宿上限是多少？ ",
        **common,
    )
    second = build_retrieval_cache_key(
        question="上海 住宿上限是多少？",
        **common,
    )

    assert first == second
    assert first.startswith(
        "rag:retrieval:v2:kb-a:7:"
    )
    assert "上海" not in first
    assert build_retrieval_cache_key(
        question="上海 住宿上限是多少？",
        **{
            **common,
            "knowledge_base_id": "kb-b",
        },
    ) != first

    assert build_retrieval_cache_key(
        question="上海 住宿上限是多少？",
        retrieval_mode="hybrid",
        **common,
    ) != first
    assert build_retrieval_cache_key(
        question="上海 住宿上限是多少？",
        **{
            **common,
            "knowledge_base_version": 8,
        },
    ) != first


def test_cache_round_trip_uses_ttl():
    client = FakeRedis()
    service = RetrievalCacheService(
        redis_url="redis://unused",
        ttl_seconds=45,
        client=client,
    )
    results = [
        {
            "chunk_id": "chunk-1",
            "content": "住宿上限 500 元。",
            "distance": 0.1,
            "metadata": {
                "document_id": "doc-1",
            },
        }
    ]

    assert service.set_retrieval_result(
        "cache-key",
        results,
    ) is True
    cached, lookup_ms = (
        service.get_retrieval_result(
            "cache-key"
        )
    )

    assert cached == results
    assert lookup_ms >= 0
    assert client.set_calls[0][2] == 45
    assert json.loads(
        client.set_calls[0][1]
    ) == results


def test_cache_failures_degrade_to_miss(caplog):
    service = RetrievalCacheService(
        redis_url="redis://unused",
        ttl_seconds=45,
        client=BrokenRedis(),
    )
    caplog.set_level("WARNING")

    cached, lookup_ms = (
        service.get_retrieval_result(
            "cache-key"
        )
    )

    assert cached is None
    assert lookup_ms >= 0
    assert service.set_retrieval_result(
        "cache-key",
        [],
    ) is False
    assert "redis cache get failed" in caplog.text
    assert "redis cache set failed" in caplog.text
