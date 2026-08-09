from pathlib import Path
import hashlib

from docx import Document

from app.schemas.document import DocumentRecord


def load_docx(file_path: str):

    doc = Document(file_path)

    content = []

    for paragraph in doc.paragraphs:
        if paragraph.text.strip():
            content.append(paragraph.text)

    text = "\n".join(content)

    return [
        DocumentRecord(
            document_id=hashlib.md5(
                Path(file_path).read_bytes()
            ).hexdigest(),
            source=file_path,
            content=text,
            content_hash=hashlib.md5(text.encode()).hexdigest(),
            file_name=Path(file_path).name,
        )
    ]