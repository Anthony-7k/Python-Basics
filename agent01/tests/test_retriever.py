from app.services.retrieval import retriever
from app.services.cache import (
    RetrievalCacheService,
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


def fake_query_chunks(
    query_text: str,
    knowledge_base_id: str,
    n_results: int = 5,
):
    return {
        "ids": [
            [
                "chunk_1",
                "chunk_2",
            ]
        ],
        "documents": [
            [
                "正式员工离职需要提前30天。",
                "公司提供员工培训。",
            ]
        ],
        "metadatas": [
            [
                {
                    "source": "employee_handbook.txt",
                    "page": 1,
                },
                {
                    "source": "employee_handbook.txt",
                    "page": 2,
                },
            ]
        ],
        "distances": [
            [
                0.5,
                1.2,
            ]
        ],
    }


def test_retrieve_returns_results(
    monkeypatch,
):
    monkeypatch.setattr(
        retriever,
        "query_chunks",
        fake_query_chunks,
    )

    results = retriever.retrieve(
        query_text="员工离职需要提前多久？",
        knowledge_base_id="kb-a",
        top_k=2,
    )

    assert len(results) == 2
    assert results[0]["chunk_id"] == "chunk_1"
    assert results[0]["distance"] == 0.5
    assert results[0]["metadata"]["source"] == "employee_handbook.txt"


def test_retrieve_filters_by_distance(
    monkeypatch,
):
    monkeypatch.setattr(
        retriever,
        "query_chunks",
        fake_query_chunks,
    )

    results = retriever.retrieve(
        query_text="员工离职需要提前多久？",
        knowledge_base_id="kb-a",
        top_k=2,
        max_distance=1.0,
    )

    assert len(results) == 1
    assert results[0]["chunk_id"] == "chunk_1"


def test_retrieve_with_cache_skips_second_vector_query(
    monkeypatch,
):
    redis_client = FakeRedis()
    cache_service = RetrievalCacheService(
        redis_url="redis://unused",
        ttl_seconds=60,
        client=redis_client,
    )
    query_calls = []

    def tracked_query(**kwargs):
        query_calls.append(kwargs)
        return fake_query_chunks(**kwargs)

    monkeypatch.setattr(
        retriever,
        "query_chunks",
        tracked_query,
    )

    first = retriever.retrieve_with_cache(
        query_text="  员工离职  需要提前多久？ ",
        knowledge_base_id="kb-a",
        knowledge_base_version=3,
        top_k=2,
        max_distance=1.0,
        embedding_model="embedding-v1",
        cache_service=cache_service,
    )
    second = retriever.retrieve_with_cache(
        query_text="员工离职 需要提前多久？",
        knowledge_base_id="kb-a",
        knowledge_base_version=3,
        top_k=2,
        max_distance=1.0,
        embedding_model="embedding-v1",
        cache_service=cache_service,
    )

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert second.items == first.items
    assert len(query_calls) == 1
    assert redis_client.set_calls[0][2] == 60


def test_cache_key_version_prevents_stale_hit(
    monkeypatch,
):
    cache_service = RetrievalCacheService(
        redis_url="redis://unused",
        ttl_seconds=60,
        client=FakeRedis(),
    )
    query_calls = []

    def tracked_query(**kwargs):
        query_calls.append(kwargs)
        return fake_query_chunks(**kwargs)

    monkeypatch.setattr(
        retriever,
        "query_chunks",
        tracked_query,
    )

    for version in (1, 2):
        outcome = retriever.retrieve_with_cache(
            query_text="员工离职需要提前多久？",
            knowledge_base_id="kb-a",
            knowledge_base_version=version,
            embedding_model="embedding-v1",
            cache_service=cache_service,
        )
        assert outcome.cache_hit is False

    assert len(query_calls) == 2
