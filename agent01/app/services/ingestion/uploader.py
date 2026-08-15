from app.core.settings import MAX_UPLOAD_SIZE_BYTES, UPLOAD_DIR

from pathlib import Path

from fastapi import UploadFile

from hashlib import sha256

ALLOWED_MIME_TYPES = {
    ".txt": {"text/plain"},
    ".pdf": {"application/pdf"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    },
}

def validate_file_type(file: UploadFile) -> str:
    if not file.filename:
        raise ValueError("Filename is required")

    suffix = Path(file.filename).suffix.lower()
    allowed_mime_types = ALLOWED_MIME_TYPES.get(suffix)

    if allowed_mime_types is None:
        raise ValueError(
            f"Unsupported file extension: {suffix or 'none'}"
        )

    if file.content_type not in allowed_mime_types:
        raise ValueError(
            f"Unsupported MIME type: {file.content_type}"
        )

    return suffix

async def read_validated_file(
    file: UploadFile,
) -> tuple[bytes, str]:
    suffix = validate_file_type(file)

    content = await file.read(
        MAX_UPLOAD_SIZE_BYTES + 1
    )

    if not content:
        raise ValueError("File is empty")

    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise ValueError(
            f"File exceeds the maximum size of "
            f"{MAX_UPLOAD_SIZE_BYTES} bytes"
        )

    return content, suffix

def calculate_sha256(content: bytes) -> str:
    return sha256(content).hexdigest()

def save_uploaded_file(
    content: bytes,
    suffix: str,
) -> tuple[str, Path]:
    document_id = calculate_sha256(content)

    UPLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_path = UPLOAD_DIR / f"{document_id}{suffix}"

    if not file_path.exists():
        file_path.write_bytes(content)

    return document_id, file_path