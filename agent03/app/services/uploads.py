from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass
from pathlib import Path

from app.domain import DocumentKind
from app.services.errors import InvalidInput


@dataclass(frozen=True)
class InspectedUpload:
    kind: DocumentKind
    sha256: str
    size_bytes: int
    content_type: str


EXTENSION_TYPES: dict[str, tuple[DocumentKind, str]] = {
    ".pdf": (DocumentKind.PDF, "application/pdf"),
    ".png": (DocumentKind.PNG, "image/png"),
    ".jpg": (DocumentKind.JPEG, "image/jpeg"),
    ".jpeg": (DocumentKind.JPEG, "image/jpeg"),
    ".docx": (DocumentKind.DOCX, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
}


def inspect_upload(path: Path, original_name: str, content_type: str, max_bytes: int) -> InspectedUpload:
    suffix = Path(original_name).suffix.lower()
    expected = EXTENSION_TYPES.get(suffix)
    if expected is None:
        raise InvalidInput("only PDF, PNG, JPG, JPEG and DOCX files are allowed")
    size = path.stat().st_size
    if size == 0:
        raise InvalidInput("empty files are not allowed")
    if size > max_bytes:
        raise InvalidInput("file exceeds the 25 MB upload limit")
    kind, canonical_type = expected
    prefix = path.read_bytes()[:16]
    valid = False
    if kind == DocumentKind.PDF:
        valid = prefix.startswith(b"%PDF-")
    elif kind == DocumentKind.PNG:
        valid = prefix.startswith(b"\x89PNG\r\n\x1a\n")
    elif kind == DocumentKind.JPEG:
        valid = prefix.startswith(b"\xff\xd8\xff")
    elif kind == DocumentKind.DOCX:
        try:
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                valid = "[Content_Types].xml" in names and "word/document.xml" in names
        except zipfile.BadZipFile:
            valid = False
    if not valid:
        raise InvalidInput("file content does not match its extension")
    if content_type and content_type not in {canonical_type, "application/octet-stream"}:
        allowed_docx_alias = kind == DocumentKind.DOCX and content_type == "application/zip"
        if not allowed_docx_alias:
            raise InvalidInput("file MIME type does not match its extension")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return InspectedUpload(kind, digest.hexdigest(), size, canonical_type)

