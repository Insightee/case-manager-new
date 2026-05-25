from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StorageResult:
    provider: str
    key: str
    size_bytes: int
    content_type: str
