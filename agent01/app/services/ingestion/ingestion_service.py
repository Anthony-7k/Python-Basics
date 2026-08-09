from pathlib import Path

from app.schemas.document import DocumentRecord
from app.services.loaders.txt_loader import load_txt
from app.services.loaders.pdf_loader import load_pdf
from app.services.loaders.docx_loader import load_docx
from app.services.cleaners.text_cleaner import clean_text
from app.services.chunkers.chunker import split_text
from app.schemas.chunk import ChunkRecord
from app.services.vector_stores.vector_store import upsert_chunks


def load_documents(file_path: str) -> list[DocumentRecord]:
    suffix = Path(file_path).suffix.lower()

    if suffix == ".txt":
        return [
            load_txt(file_path)
        ]

    if suffix == ".pdf":
        return load_pdf(file_path)

    if suffix == ".docx":
        return load_docx(file_path)

    raise ValueError(
        f"Unsupported file type: {suffix}"
    )

def build_chunks(file_path: str) -> list[ChunkRecord]:
    documents = load_documents(
        file_path
    )

    all_chunks = []

    for document in documents:
        cleaned_text = clean_text(
            document.content
        )

        chunks = split_text(
            cleaned_text,
            document.document_id,
            source=document.source,
            page=document.page,
        )

        all_chunks.extend(
            chunks
        )

    return all_chunks

def ingest_file(file_path: str) -> list[ChunkRecord]:
    chunks = build_chunks(
        file_path
    )

    upsert_chunks(
        chunks
    )

    return chunks