from __future__ import annotations

from pydantic import BaseModel

from app.core.settings import (
    AGENT_MAX_DOCUMENT_CHARS,
    AGENT_MAX_DOCUMENT_CHUNKS,
)
from app.models import DocumentStatus
from app.prompts.agent_tool_prompt import (
    COMPARE_SYSTEM_PROMPT,
    SUMMARY_SYSTEM_PROMPT,
    build_compare_prompt,
    build_summary_prompt,
)
from app.schemas.agent import (
    CompareDocumentsArguments,
    SearchKnowledgeArguments,
    SummarizeDocumentArguments,
    ToolName,
)
from app.services.documents import DocumentService
from app.services.llm.llm_client import generate_answer
from app.services.rag.rag_service import answer_question
from app.services.security import AccessControlService
from app.services.vector_stores.vector_store import (
    list_document_chunks,
)

from app.services.agent.registry import (
    AgentToolFailure,
    ToolDefinition,
    ToolExecutionContext,
    ToolExecutionPayload,
    ToolRegistry,
)


def _bounded_chunks(
    chunks: list[dict],
) -> list[dict]:
    ordered = sorted(
        chunks,
        key=lambda item: (
            item.get("metadata", {}).get("page", -1),
            item.get("chunk_id", ""),
        ),
    )[:AGENT_MAX_DOCUMENT_CHUNKS]

    bounded: list[dict] = []
    remaining_chars = AGENT_MAX_DOCUMENT_CHARS
    for item in ordered:
        content = str(item.get("content", ""))
        if remaining_chars <= 0:
            break
        content = content[:remaining_chars]
        if content:
            bounded.append(
                {
                    **item,
                    "content": content,
                }
            )
            remaining_chars -= len(content)
    return bounded


def _document_sources(
    chunks: list[dict],
) -> list[dict]:
    return [
        {
            "chunk_id": item.get("chunk_id"),
            "file_name": item.get(
                "metadata", {}
            ).get("source"),
            "page": item.get(
                "metadata", {}
            ).get("page"),
        }
        for item in chunks
    ]


def _require_ready_document(
    service: DocumentService,
    knowledge_base_id: str,
    document_id: str,
):
    document = service.get_document(
        knowledge_base_id=knowledge_base_id,
        document_id=document_id,
    )
    if document is None:
        raise AgentToolFailure(
            "document_not_found",
            "目标文档不存在或不属于指定知识库",
        )
    if document.status != DocumentStatus.READY:
        raise AgentToolFailure(
            "document_not_ready",
            "目标文档尚未完成入库，暂时不能执行该工具",
            retryable=True,
        )
    return document


def search_knowledge(
    arguments: BaseModel,
    context: ToolExecutionContext,
) -> ToolExecutionPayload:
    arguments = SearchKnowledgeArguments.model_validate(
        arguments
    )
    knowledge_base = AccessControlService(
        context.session,
        context.current_user,
    ).require_knowledge_base_access(
        arguments.knowledge_base_id
    )
    response = answer_question(
        knowledge_base_id=knowledge_base.id,
        knowledge_base_version=knowledge_base.version,
        original_question=arguments.query,
        standalone_question=arguments.query,
        top_k=arguments.top_k,
        request_id=context.request_id,
    )
    return ToolExecutionPayload(
        output=response.model_dump(mode="json"),
        result_summary=(
            f"answered_with_{len(response.sources)}_sources"
        ),
    )


def summarize_document(
    arguments: BaseModel,
    context: ToolExecutionContext,
) -> ToolExecutionPayload:
    arguments = SummarizeDocumentArguments.model_validate(
        arguments
    )
    service = DocumentService(
        context.session,
        current_user=context.current_user,
    )
    document = _require_ready_document(
        service,
        arguments.knowledge_base_id,
        arguments.document_id,
    )
    chunks = _bounded_chunks(
        list_document_chunks(
            arguments.knowledge_base_id,
            document.id,
        )
    )
    if not chunks:
        raise AgentToolFailure(
            "document_content_unavailable",
            "目标文档没有可用于总结的已索引内容",
        )

    answer = generate_answer(
        system_prompt=SUMMARY_SYSTEM_PROMPT,
        user_prompt=build_summary_prompt(
            arguments.instruction,
            chunks,
        ),
    )
    return ToolExecutionPayload(
        output={
            "answer": answer,
            "document_id": document.id,
            "file_name": document.file_name,
            "sources": _document_sources(chunks),
        },
        result_summary=(
            f"summarized_document_with_{len(chunks)}_chunks"
        ),
    )


def compare_documents(
    arguments: BaseModel,
    context: ToolExecutionContext,
) -> ToolExecutionPayload:
    arguments = CompareDocumentsArguments.model_validate(
        arguments
    )
    service = DocumentService(
        context.session,
        current_user=context.current_user,
    )
    left_document = _require_ready_document(
        service,
        arguments.knowledge_base_id,
        arguments.left_document_id,
    )
    right_document = _require_ready_document(
        service,
        arguments.knowledge_base_id,
        arguments.right_document_id,
    )
    left_chunks = _bounded_chunks(
        list_document_chunks(
            arguments.knowledge_base_id,
            left_document.id,
        )
    )
    right_chunks = _bounded_chunks(
        list_document_chunks(
            arguments.knowledge_base_id,
            right_document.id,
        )
    )
    if not left_chunks or not right_chunks:
        raise AgentToolFailure(
            "document_content_unavailable",
            "至少一个目标文档没有可用于对比的已索引内容",
        )

    answer = generate_answer(
        system_prompt=COMPARE_SYSTEM_PROMPT,
        user_prompt=build_compare_prompt(
            arguments.instruction,
            left_chunks,
            right_chunks,
        ),
    )
    return ToolExecutionPayload(
        output={
            "answer": answer,
            "left_document": {
                "document_id": left_document.id,
                "file_name": left_document.file_name,
                "sources": _document_sources(left_chunks),
            },
            "right_document": {
                "document_id": right_document.id,
                "file_name": right_document.file_name,
                "sources": _document_sources(right_chunks),
            },
        },
        result_summary=(
            "compared_two_documents_with_"
            f"{len(left_chunks) + len(right_chunks)}_chunks"
        ),
    )


def build_default_tool_registry() -> ToolRegistry:
    return ToolRegistry(
        [
            ToolDefinition(
                name=ToolName.SEARCH_KNOWLEDGE,
                description=(
                    "Answer a question from one authorized knowledge base"
                ),
                arguments_model=SearchKnowledgeArguments,
                handler=search_knowledge,
            ),
            ToolDefinition(
                name=ToolName.SUMMARIZE_DOCUMENT,
                description=(
                    "Summarize one authorized indexed document"
                ),
                arguments_model=SummarizeDocumentArguments,
                handler=summarize_document,
            ),
            ToolDefinition(
                name=ToolName.COMPARE_DOCUMENTS,
                description=(
                    "Compare two authorized indexed documents"
                ),
                arguments_model=CompareDocumentsArguments,
                handler=compare_documents,
            ),
        ]
    )
