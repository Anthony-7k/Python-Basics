import zipfile
from pathlib import Path

import pytest

from app.domain import DocumentKind
from app.services.errors import InvalidInput
from app.services.uploads import inspect_upload


def write(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


@pytest.mark.parametrize(
    ("name", "data", "mime", "kind"),
    [
        ("scan.pdf", b"%PDF-1.7\n%%EOF", "application/pdf", DocumentKind.PDF),
        ("page.png", b"\x89PNG\r\n\x1a\nbody", "image/png", DocumentKind.PNG),
        ("photo.jpeg", b"\xff\xd8\xffbody", "image/jpeg", DocumentKind.JPEG),
    ],
)
def test_supported_signatures(tmp_path, name, data, mime, kind):
    result = inspect_upload(write(tmp_path / name, data), name, mime, 1024)
    assert result.kind == kind
    assert len(result.sha256) == 64


def test_valid_docx_signature(tmp_path):
    path = tmp_path / "document.docx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "<document />")
    result = inspect_upload(path, path.name, "application/zip", 10_000)
    assert result.kind == DocumentKind.DOCX


@pytest.mark.parametrize(
    ("name", "data", "mime", "limit", "message"),
    [
        ("bad.exe", b"MZ", "application/octet-stream", 100, "only PDF"),
        ("empty.pdf", b"", "application/pdf", 100, "empty"),
        ("large.pdf", b"%PDF-" + b"x" * 20, "application/pdf", 10, "25 MB"),
        ("fake.png", b"not-png", "image/png", 100, "does not match"),
        ("wrong.pdf", b"%PDF-1.4", "image/png", 100, "MIME"),
    ],
)
def test_rejected_uploads(tmp_path, name, data, mime, limit, message):
    with pytest.raises(InvalidInput, match=message):
        inspect_upload(write(tmp_path / name, data), name, mime, limit)


def test_malformed_docx_is_rejected(tmp_path):
    path = write(tmp_path / "bad.docx", b"not a zip")
    with pytest.raises(InvalidInput, match="does not match"):
        inspect_upload(path, path.name, "application/zip", 100)

