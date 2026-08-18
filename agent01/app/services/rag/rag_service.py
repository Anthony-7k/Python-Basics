import uuid

import time

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

from app.core.logging_config import get_logger

logger = get_logger(__name__)

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
        max_distance=0.98,
    )

    context, sources = build_context(results)

    return {
        "context": context,
        "sources": sources,
    }


def answer_question(
    question: str | None = None,
    top_k: int = 5,
    request_id: str | None = None,
    *,
    original_question: str | None = None,
    standalone_question: str | None = None,
):
    if original_question is None:
        original_question = question

    if original_question is None:
        raise ValueError(
            "original_question is required"
        )

    if standalone_question is None:
        standalone_question = (
            original_question
        )

    if request_id is None:
        request_id = str(uuid.uuid4())

    total_start = time.perf_counter()

    retrieval_start = time.perf_counter()

    retrieval_result = retrieve_context(
        question=standalone_question,
        top_k=top_k,
    )

    retrieval_ms = (
                           time.perf_counter() - retrieval_start
                   ) * 1000

    logger.info(
        "rag retrieval completed request_id=%s "
        "original_question=%r "
        "standalone_question=%r "
        "sources=%s retrieval_ms=%.2f",
        request_id,
        original_question,
        standalone_question,
        len(retrieval_result["sources"]),
        retrieval_ms,
    )

    context = retrieval_result["context"]

    if not context.strip():
        total_ms = (
                           time.perf_counter() - total_start
                   ) * 1000

        logger.info(
            "rag request completed request_id=%s "
            "status=refused total_ms=%.2f",
            request_id,
            total_ms,
        )

        return RAGResponse(
            answer="知识库中没有足够的信息回答这个问题。",
            sources=[],
            used_chunk_ids=[],
            request_id=request_id,
        )

    user_prompt = build_user_prompt(
        question=original_question,
        context=context,
        standalone_question=(
            standalone_question
        ),
    )

    generation_start = time.perf_counter()

    answer = generate_answer(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    generation_ms = (
                            time.perf_counter() - generation_start
                    ) * 1000

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

    total_ms = (
        time.perf_counter() - total_start
    ) * 1000

    logger.info(
        "rag request completed request_id=%s "
        "status=answered sources=%s "
        "generation_ms=%.2f total_ms=%.2f",
        request_id,
        len(sources),
        generation_ms,
        total_ms,
    )

    return RAGResponse(
        answer=answer,
        sources=sources,
        used_chunk_ids=[
            item["chunk_id"]
            for item in retrieval_result["sources"]
        ],
        request_id=request_id,
    )
