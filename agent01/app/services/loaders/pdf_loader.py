from pathlib import Path
import hashlib

from pypdf import PdfReader

from app.schemas.document import DocumentRecord


def calculate_hash(text: str) -> str:
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def calculate_file_hash(file_path: str) -> str:
    return hashlib.sha256(
        Path(file_path).read_bytes()
    ).hexdigest()


def load_pdf(file_path: str) -> list[DocumentRecord]:
    path = Path(file_path)

    reader = PdfReader(file_path)

    documents = []

    document_id = calculate_file_hash(
        file_path
    )

    for index, page in enumerate(reader.pages):
        text = page.extract_text()

        if not text:
            continue

        documents.append(
            DocumentRecord(
                content=text,
                source=str(path),
                file_name=path.name,
                page=index + 1,
                document_id=document_id,
                content_hash=calculate_hash(text),
            )
        )

    return documents