from app.schemas.chunk import ChunkRecord
import hashlib


def split_text(
    text: str,
    document_id: str,
    knowledge_base_id: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    source: str | None = None,
    page: int | None = None,
):
    chunks = []

    start = 0
    index = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        chunk_content = text[start:end]

        if page is not None:
            chunk_id = f"{document_id}_p{page}_{index}"
        else:
            chunk_id = f"{document_id}_{index}"

        chunk = ChunkRecord(
            chunk_id=chunk_id,
            document_id=document_id,
            knowledge_base_id=(
                knowledge_base_id
            ),
            content=chunk_content,
            start_index=start,
            end_index=end,
            source=source,
            page=page,
            content_hash=hashlib.md5(
                chunk_content.encode()
            ).hexdigest(),
        )

        chunks.append(chunk)

        index += 1

        if end == len(text):
            break

        start = end - chunk_overlap

    return chunks
