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


def sanitize_file_name(file_name: str) -> str:
    """Return a basename for both POSIX and Windows separators."""
    return Path(
        file_name.replace("\\", "/")
    ).name

def validate_file_type(file: UploadFile) -> str:
    if not file.filename:
        raise ValueError("Filename is required")

    suffix = Path(
        sanitize_file_name(file.filename)
    ).suffix.lower()
    allowed_mime_types = ALLOWED_MIME_TYPES.get(suffix)

    if allowed_mime_types is None:
        raise ValueError("Unsupported file extension")

    if file.content_type not in allowed_mime_types:
        raise ValueError("Unsupported MIME type")

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
    content_hash = calculate_sha256(content)

    UPLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_path = UPLOAD_DIR / f"{content_hash}{suffix}"

    if not file_path.exists():
        file_path.write_bytes(content)

    return content_hash, file_path


def get_uploaded_file_path(
    content_hash: str,
    file_name: str,
) -> Path:
    suffix = Path(
        sanitize_file_name(file_name)
    ).suffix.lower()
    return UPLOAD_DIR / f"{content_hash}{suffix}"
