from __future__ import annotations

import re
import uuid
from pathlib import Path

from app.core.config import settings

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_UPLOAD_ROOT = _BACKEND_ROOT / "uploads" / "case_documents"

ALLOWED_UPLOAD_MIME = frozenset(
    {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
)
ALLOWED_IMAGE_MIME = frozenset({"image/jpeg", "image/png", "image/webp"})
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def _safe_filename(name: str) -> str:
    base = Path(name or "document").name
    cleaned = re.sub(r"[^\w.\-]+", "_", base).strip("._")
    return cleaned[:200] or "document"


class LocalCaseDocumentStorage:
    def put(
        self,
        *,
        case_id: int,
        document_id: int,
        version_number: int,
        filename: str,
        content: bytes,
    ) -> str:
        safe = _safe_filename(filename)
        key = f"case_documents/{case_id}/{document_id}/v{version_number}/{uuid.uuid4()}_{safe}"
        path = _BACKEND_ROOT / "uploads" / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return key

    def resolve_path(self, storage_key: str) -> Path:
        key = (storage_key or "").lstrip("/")
        if ".." in key.split("/"):
            raise ValueError("Invalid storage key")
        path = (_BACKEND_ROOT / "uploads" / key).resolve()
        root = (_BACKEND_ROOT / "uploads").resolve()
        if not str(path).startswith(str(root)):
            raise ValueError("Invalid storage key")
        return path

    def open_bytes(self, storage_key: str) -> tuple[Path, bytes]:
        path = self.resolve_path(storage_key)
        if not path.is_file():
            raise FileNotFoundError("File not found on disk")
        return path, path.read_bytes()


case_document_storage = LocalCaseDocumentStorage()
