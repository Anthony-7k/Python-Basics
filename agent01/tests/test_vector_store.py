import app.services.vector_stores.vector_store as vector_store

from app.services.chunkers.chunker import split_text

def test_upsert_empty_chunks():
    vector_store.upsert_chunks([])

def test_idempotent_upsert(monkeypatch):
    document_id = "pytest_idempotent_doc"
    knowledge_base_id = "pytest-kb-a"

    vector_store.delete_by_document(
        knowledge_base_id,
        document_id
    )

    call_count = 0

    def fake_embed_texts(texts):
        nonlocal call_count
        call_count += 1

        return [
            [0.1] * 1024
            for _ in texts
        ]

    monkeypatch.setattr(
        vector_store,
        "embed_texts",
        fake_embed_texts,
    )

    chunks = split_text(
        "员工年假为5天，试用期为3个月。",
        document_id,
        knowledge_base_id,
        source="test_handbook.txt",
        page=1,
    )

    vector_store.upsert_chunks(chunks)
    vector_store.upsert_chunks(chunks)

    result = vector_store.collection.get(
        ids=[chunks[0].chunk_id]
    )

    assert result["ids"] == [
        chunks[0].chunk_id
    ]

    assert call_count == 1

    vector_store.delete_by_document(
        knowledge_base_id,
        document_id
    )

def test_delete_by_document(monkeypatch):
    document_id = "pytest_delete_doc"
    knowledge_base_id = "pytest-kb-a"

    vector_store.delete_by_document(
        knowledge_base_id,
        document_id
    )

    def fake_embed_texts(texts):
        return [
            [0.2] * 1024
            for _ in texts
        ]

    monkeypatch.setattr(
        vector_store,
        "embed_texts",
        fake_embed_texts,
    )

    chunks = split_text(
        "公司试用期为3个月。",
        document_id,
        knowledge_base_id,
        source="test_handbook.txt",
        page=1,
    )

    vector_store.upsert_chunks(chunks)

    before = vector_store.collection.get(
        where={
            "document_id": document_id
        }
    )

    assert len(before["ids"]) == 1

    vector_store.delete_by_document(
        knowledge_base_id,
        document_id
    )

    after = vector_store.collection.get(
        where={
            "document_id": document_id
        }
    )

    assert len(after["ids"]) == 0

def test_query_chunks(monkeypatch):
    document_id = "pytest_query_doc"
    knowledge_base_id = "pytest-kb-a"

    vector_store.delete_by_document(
        knowledge_base_id,
        document_id
    )

    def fake_embed_texts(texts):
        embeddings = []

        for text in texts:
            if "年假" in text:
                embeddings.append(
                    [1.0] + [0.0] * 1023
                )
            else:
                embeddings.append(
                    [0.0, 1.0] + [0.0] * 1022
                )

        return embeddings

    monkeypatch.setattr(
        vector_store,
        "embed_texts",
        fake_embed_texts,
    )

    chunks = split_text(
        "员工年假为5天。",
        document_id,
        knowledge_base_id,
        source="test_handbook.txt",
        page=1,
    )

    vector_store.upsert_chunks(chunks)

    result = vector_store.query_chunks(
        "员工年假有几天？",
        knowledge_base_id=(
            knowledge_base_id
        ),
        n_results=1,
    )

    assert result["documents"][0][0] == "员工年假为5天。"

    assert (
        result["metadatas"][0][0]["document_id"]
        == document_id
    )

    vector_store.delete_by_document(
        knowledge_base_id,
        document_id
    )


def test_query_chunks_prevents_cross_knowledge_base_results(
    monkeypatch,
):
    kb_a = "pytest-isolation-kb-a"
    kb_b = "pytest-isolation-kb-b"
    doc_a = "pytest-isolation-doc-a"
    doc_b = "pytest-isolation-doc-b"

    def fake_embed_texts(texts):
        return [
            [0.3] * 1024
            for _ in texts
        ]

    monkeypatch.setattr(
        vector_store,
        "embed_texts",
        fake_embed_texts,
    )
    vector_store.delete_by_document(
        kb_a,
        doc_a,
    )
    vector_store.delete_by_document(
        kb_b,
        doc_b,
    )
    vector_store.upsert_chunks(
        split_text(
            "A库年假为10天。",
            doc_a,
            kb_a,
        )
    )
    vector_store.upsert_chunks(
        split_text(
            "B库年假为20天。",
            doc_b,
            kb_b,
        )
    )

    result = vector_store.query_chunks(
        "年假有几天？",
        knowledge_base_id=kb_a,
        n_results=5,
    )
    metadatas = result["metadatas"][0]
    assert metadatas
    assert {
        item["knowledge_base_id"]
        for item in metadatas
    } == {kb_a}

    vector_store.delete_by_document(
        kb_a,
        doc_a,
    )
    vector_store.delete_by_document(
        kb_b,
        doc_b,
    )
