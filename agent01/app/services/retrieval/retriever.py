from app.services.vector_stores.vector_store import query_chunks


def retrieve(
    query_text: str,
    top_k: int = 5,
    max_distance: float | None = None,
) -> list[dict]:
    raw_results = query_chunks(
        query_text=query_text,
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
                "distance": distance,
                "metadata": metadata,
            }
        )

    return results