import uuid

from app.services.retrieval.retriever import retrieve

from app.prompts.rag_prompt import (
    SYSTEM_PROMPT,
    build_user_prompt,
)

from app.services.llm.llm_client import generate_answer

from app.schemas.rag import (
    RAGResponse,
    RAGSource,
)


def build_context(results: list[dict]):
    """
    将检索结果转换成带来源编号的上下文
    """

    contexts = []
    sources = []

    for index, item in enumerate(results, start=1):

        source_id = f"S{index}"

        contexts.append(
            f"[{source_id}]\n{item['content']}"
        )

        sources.append(
            {
                "source_id": source_id,
                "chunk_id": item["chunk_id"],
                "content": item["content"],
                "metadata": item["metadata"],
            }
        )

    return "\n\n".join(contexts), sources



def retrieve_context(
    question: str,
    top_k: int = 5
):
    """
    用户问题 -> 检索 -> 构造上下文
    """

    results = retrieve(
        query_text=question,
        top_k=top_k,
        max_distance=0.5,
    )

    context, sources = build_context(results)

    return {
        "context": context,
        "sources": sources,
    }


def answer_question(
    question: str,
    top_k: int = 5,
):

    retrieval_result = retrieve_context(
        question=question,
        top_k=top_k,
    )

    context = retrieval_result["context"]

    if not context.strip():
        return RAGResponse(
            answer="知识库中没有足够的信息回答这个问题。",
            sources=[],
            used_chunk_ids=[],
            request_id=str(uuid.uuid4()),
        )

    user_prompt = build_user_prompt(
        question=question,
        context=context,
    )

    answer = generate_answer(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    sources = [
        RAGSource(
            source_id=item["source_id"],
            chunk_id=item["chunk_id"],
            file_name=item["metadata"].get("source"),
            page=item["metadata"].get("page"),
            content=item.get("content", ""),
        )
        for item in retrieval_result["sources"]
    ]

    return RAGResponse(
        answer=answer,
        sources=sources,
        used_chunk_ids=[
            item["chunk_id"]
            for item in retrieval_result["sources"]
        ],
        request_id=str(uuid.uuid4()),
    )