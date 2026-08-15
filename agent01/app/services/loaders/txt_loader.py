from pathlib import Path
import hashlib

from app.schemas.document import DocumentRecord


def calculate_hash(text: str) -> str:
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()

def calculate_file_hash(file_path: str) -> str:
    return hashlib.sha256(
        Path(file_path).read_bytes()
    ).hexdigest()


def load_txt(file_path: str) -> DocumentRecord:

    path = Path(file_path) # 找文件

    content = path.read_text(   # 读取文字
        encoding="utf-8"
    )

    return DocumentRecord(
        content=content,

        source=str(path),

        file_name=path.name,

        page=None,

        document_id=calculate_file_hash(file_path),  # 计算唯一标识

        content_hash=calculate_hash(content)
    )