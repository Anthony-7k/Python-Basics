from app.schemas.chunk import ChunkRecord
import hashlib


def split_text(
    text: str,
    document_id: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
):
    chunks = []

    start = 0
    index = 0

    while start < len(text):
        end = start + chunk_size

        chunk_content = text[start:end]

        chunk = ChunkRecord(
            chunk_id=f"{document_id}_{index}",
            document_id=document_id,
            content=chunk_content,
            start_index=start,
            end_index=end,
            content_hash=hashlib.md5(
                chunk_content.encode()
            ).hexdigest(),
        )

        chunks.append(chunk)

        index += 1

        start = end - chunk_overlap

    return chunks