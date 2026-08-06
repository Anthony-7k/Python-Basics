from pypdf import PdfReader

from app.schemas.document import DocumentRecord


def load_pdf(file_path: str):

    reader = PdfReader(file_path)

    documents = []

    for index, page in enumerate(reader.pages):

        text = page.extract_text()

        if not text:
            continue

        documents.append(
            DocumentRecord(
                content=text,

                source=file_path,

                file_name=file_path.split("/")[-1],

                page=index + 1,

                document_id=f"{file_path}-{index}",

                content_hash=str(hash(text))
            )
        )

    return documents