from __future__ import annotations

from pathlib import Path

from app.storage.types import StorageResult

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_OBJECTS_ROOT = (_BACKEND_ROOT / "uploads" / "objects").resolve()


class LocalStorageBackend:
    provider = "local"

    def _resolve_path(self, key: str) -> Path:
        normalized = (key or "").lstrip("/")
        if ".." in normalized.split("/"):
            raise ValueError("Invalid storage key")
        path = (_OBJECTS_ROOT / normalized).resolve()
        if not str(path).startswith(str(_OBJECTS_ROOT)):
            raise ValueError("Invalid storage key")
        return path

    def put_bytes(self, key: str, data: bytes, content_type: str) -> StorageResult:
        path = self._resolve_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StorageResult(
            provider=self.provider,
            key=key,
            size_bytes=len(data),
            content_type=content_type,
        )

    def get_bytes(self, key: str) -> bytes:
        path = self._resolve_path(key)
        if not path.is_file():
            raise FileNotFoundError(f"Object not found: {key}")
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = self._resolve_path(key)
        if path.is_file():
            path.unlink()

    def exists(self, key: str) -> bool:
        try:
            return self._resolve_path(key).is_file()
        except ValueError:
            return False
