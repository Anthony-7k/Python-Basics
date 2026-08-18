import argparse
from pathlib import Path

from app.services.ingestion.ingestion_service import ingest_file
from app.services.rag.rag_service import answer_question
from app.core.settings import validate_settings
from app.core.logging_config import (
    setup_logging,
    get_logger,
)
from app.services.documents import (
    build_document_id,
)
from app.services.ingestion.uploader import (
    calculate_sha256,
)


logger = get_logger(__name__)


def run_ingest(
    file_path: str,
    knowledge_base_id: str,
):
    content_hash = calculate_sha256(
        Path(file_path).read_bytes()
    )
    chunks = ingest_file(
        file_path,
        document_id=build_document_id(
            knowledge_base_id,
            content_hash,
        ),
        knowledge_base_id=(
            knowledge_base_id
        ),
    )

    print()
    print("Ingestion completed")
    print(f"File: {file_path}")
    print(f"Chunks: {len(chunks)}")


def run_chat(
    question: str,
    top_k: int,
    knowledge_base_id: str,
):
    response = answer_question(
        question=question,
        top_k=top_k,
        knowledge_base_id=(
            knowledge_base_id
        ),
    )

    print()
    print("Answer:")
    print(response.answer)

    print()
    print("Sources:")

    if not response.sources:
        print("No sources")
    else:
        for source in response.sources:
            print(
                f"[{source.source_id}] "
                f"file={source.file_name} "
                f"page={source.page} "
                f"chunk_id={source.chunk_id}"
            )

    print()
    print(f"Request ID: {response.request_id}")


def main():
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Enterprise Knowledge Base RAG CLI"
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    ingest_parser = subparsers.add_parser(
        "ingest",
        help="Ingest a document into the knowledge base",
    )

    ingest_parser.add_argument(
        "file_path",
        help="Path to PDF, DOCX or TXT file",
    )
    ingest_parser.add_argument(
        "--knowledge-base-id",
        required=True,
        help="Knowledge base identifier",
    )

    chat_parser = subparsers.add_parser(
        "chat",
        help="Ask a question to the knowledge base",
    )

    chat_parser.add_argument(
        "question",
        help="Question to ask",
    )
    chat_parser.add_argument(
        "--knowledge-base-id",
        required=True,
        help="Knowledge base identifier",
    )

    chat_parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of retrieved chunks",
    )

    args = parser.parse_args()

    validate_settings()

    logger.info(
        "CLI command started command=%s",
        args.command,
    )

    if args.command == "ingest":
        run_ingest(
            file_path=args.file_path,
            knowledge_base_id=(
                args.knowledge_base_id
            ),
        )

    elif args.command == "chat":
        run_chat(
            question=args.question,
            top_k=args.top_k,
            knowledge_base_id=(
                args.knowledge_base_id
            ),
        )


if __name__ == "__main__":
    main()
