from app.schemas.chunk import ChunkRecord
from app.services.embeddings.embedding_service import embed_texts

import chromadb

from app.core.settings import (
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSIONS,
)


client = chromadb.PersistentClient(
    path="data/chroma"
)

collection = client.get_or_create_collection(
    name="enterprise_knowledge",
    metadata={
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dimensions": EMBEDDING_DIMENSIONS,
    },
)

def upsert_chunks(chunks: list[ChunkRecord]) -> None:
    if not chunks:
        return

    existing = collection.get(
        ids=[
            chunk.chunk_id
            for chunk in chunks
        ],
        include=["metadatas"],
    )

    existing_metadata = {
        chunk_id: metadata
        for chunk_id, metadata in zip(
            existing["ids"],
            existing["metadatas"],
        )
    }

    chunks_to_upsert = []

    for chunk in chunks:
        old_metadata = existing_metadata.get(
            chunk.chunk_id
        )

        if (
                old_metadata
                and old_metadata.get("content_hash") == chunk.content_hash
                and old_metadata.get("embedding_model") == EMBEDDING_MODEL
        ):
            continue

        chunks_to_upsert.append(chunk)

    if not chunks_to_upsert:
        return

    texts = [
        chunk.content
        for chunk in chunks_to_upsert
    ]

    embeddings = embed_texts(texts)

    ids = [
        chunk.chunk_id
        for chunk in chunks_to_upsert
    ]

    metadatas = [
        {
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "source": chunk.source or "",
            "page": chunk.page if chunk.page is not None else -1,
            "content_hash": chunk.content_hash,
            "embedding_model": EMBEDDING_MODEL,
        }
        for chunk in chunks_to_upsert
    ]

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas,
    )

def query_chunks(
    query_text: str,
    n_results: int = 5,
):
    query_embedding = embed_texts(
        [query_text]
    )[0]

    return collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=[
            "documents",
            "metadatas",
            "distances",
        ],
    )

def delete_by_document(document_id: str) -> None:
    collection.delete(
        where={
            "document_id": document_id
        }
    )