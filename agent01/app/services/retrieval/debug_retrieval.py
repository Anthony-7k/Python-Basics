from app.services.retrieval.retriever import retrieve


def debug_retrieve(
    query_text: str,
    knowledge_base_id: str,
    top_k: int = 5,
) -> None:
    results = retrieve(
        query_text=query_text,
        knowledge_base_id=(
            knowledge_base_id
        ),
        top_k=top_k,
    )

    print(f"\n问题：{query_text}")

    if not results:
        print("没有检索到相关结果。")
        return

    for index, result in enumerate(
        results,
        start=1,
    ):
        metadata = result["metadata"]

        print(f"\n========== Top {index} ==========")
        print(f"chunk_id: {result['chunk_id']}")
        print(f"distance: {result['distance']:.4f}")
        print(f"source: {metadata.get('source', '')}")
        print(f"page: {metadata.get('page', '')}")

        print("\n内容：")
        print(result["content"])
