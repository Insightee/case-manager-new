from __future__ import annotations

from typing import Protocol

from app.storage.types import StorageResult


class StorageBackend(Protocol):
    provider: str

    def put_bytes(self, key: str, data: bytes, content_type: str) -> StorageResult: ...

    def get_bytes(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...

    def exists(self, key: str) -> bool: ...
