from __future__ import annotations

import re
from pathlib import Path

from app.core.config import settings
from app.storage.object_io import put_stored_bytes, read_stored_bytes

ALLOWED_UPLOAD_MIME = frozenset(
    {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
)
ALLOWED_IMAGE_MIME = frozenset({"image/jpeg", "image/png", "image/webp"})
MAX_UPLOAD_BYTES = settings.case_document_max_bytes


def _safe_filename(name: str) -> str:
    base = Path(name or "document").name
    cleaned = re.sub(r"[^\w.\-]+", "_", base).strip("._")
    return cleaned[:200] or "document"


class LocalCaseDocumentStorage:
    """Case document blobs via the shared storage backend (local dev or R2)."""

    def put(
        self,
        *,
        case_id: int,
        document_id: int,
        version_number: int,
        filename: str,
        content: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        safe = _safe_filename(filename)
        key, _provider = put_stored_bytes(
            "case-documents",
            f"case_{case_id}",
            f"doc_{document_id}",
            f"v{version_number}",
            filename=safe,
            data=content,
            content_type=content_type,
        )
        return key

    def open_bytes(self, storage_key: str) -> tuple[None, bytes]:
        return None, read_stored_bytes(storage_key)


case_document_storage = LocalCaseDocumentStorage()
