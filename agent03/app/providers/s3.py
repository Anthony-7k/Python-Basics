from __future__ import annotations

from pathlib import Path

import fsspec

from app.providers.base import StoredObject


class S3ObjectStorage:
    def __init__(self, endpoint: str, bucket: str, access_key: str, secret_key: str):
        self.bucket = bucket
        self.fs = fsspec.filesystem(
            "s3",
            key=access_key,
            secret=secret_key,
            client_kwargs={"endpoint_url": endpoint},
        )
        if not self.fs.exists(bucket):
            self.fs.mkdir(bucket)

    def put(self, source: Path, key: str) -> StoredObject:
        target = f"{self.bucket}/{key}"
        self.fs.put(str(source), target)
        return StoredObject(key=key, size_bytes=source.stat().st_size)

    def get_to(self, key: str, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        self.fs.get(f"{self.bucket}/{key}", str(target))

    def delete(self, key: str) -> None:
        target = f"{self.bucket}/{key}"
        if self.fs.exists(target):
            self.fs.rm(target)

