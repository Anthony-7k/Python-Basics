import argparse
from pathlib import Path

from app.services.ingestion.ingestion_service import ingest_file
from app.services.documents import build_document_id
from app.services.ingestion.uploader import (
    calculate_sha256,
)


def main():
    parser = argparse.ArgumentParser(
        description="Ingest a document into Chroma"
    )

    parser.add_argument(
        "file_path",
        help="Path to a TXT, PDF, or DOCX file",
    )
    parser.add_argument(
        "--knowledge-base-id",
        required=True,
        help="Knowledge base identifier",
    )

    args = parser.parse_args()

    content_hash = calculate_sha256(
        Path(args.file_path).read_bytes()
    )
    chunks = ingest_file(
        args.file_path,
        document_id=build_document_id(
            args.knowledge_base_id,
            content_hash,
        ),
        knowledge_base_id=(
            args.knowledge_base_id
        ),
    )

    print(
        f"Ingestion completed: {len(chunks)} chunks"
    )


if __name__ == "__main__":
    main()
