from app.services.retrieval import retriever


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
