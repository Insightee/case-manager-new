"""Read/write stored objects (R2 or local backend) with legacy disk fallback."""
from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import Response

from app.core.config import settings
from app.storage.factory import get_storage_backend, get_storage_backend_for_provider
from app.storage.keys import _prefix_env

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_LEGACY_UPLOADS = (_BACKEND_ROOT / "uploads").resolve()


def is_object_store_key(file_path: str) -> bool:
    """True when path is a key in the configured object store (not legacy uploads/)."""
    if not file_path:
        return False
    normalized = file_path.lstrip("/")
    prefix, _env = _prefix_env()
    return normalized.startswith(f"{prefix}/")


def _legacy_disk_candidates(file_path: str) -> list[Path]:
    raw = (file_path or "").strip()
    if not raw:
        return []
    p = Path(raw)
    candidates: list[Path] = []
    if p.is_absolute():
        candidates.append(p)
    else:
        candidates.append(Path.cwd() / raw)
        candidates.append(_BACKEND_ROOT / raw)
        if not raw.startswith("uploads/"):
            candidates.append(_LEGACY_UPLOADS / raw)
        else:
            candidates.append(_BACKEND_ROOT / raw)
    if raw.startswith("case_documents/"):
        candidates.append(_LEGACY_UPLOADS / raw)
    seen: set[str] = set()
    out: list[Path] = []
    for c in candidates:
        key = str(c.resolve()) if c.exists() or not c.is_absolute() else str(c)
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


def read_stored_bytes(file_path: str, *, storage_provider: str | None = None) -> bytes:
    if is_object_store_key(file_path):
        backend = get_storage_backend_for_provider(storage_provider)
        try:
            return backend.get_bytes(file_path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="File not found") from exc
    for candidate in _legacy_disk_candidates(file_path):
        if candidate.is_file():
            return candidate.read_bytes()
    raise HTTPException(status_code=404, detail="File not found")


def put_stored_bytes(
    category: str,
    *segments: str,
    filename: str,
    data: bytes,
    content_type: str,
) -> tuple[str, str]:
    from app.storage.keys import build_object_key

    key = build_object_key(category, *segments, filename=filename)
    result = get_storage_backend().put_bytes(key, data, content_type)
    return key, result.provider


def delete_stored_object(file_path: str, *, storage_provider: str | None = None) -> None:
    if is_object_store_key(file_path):
        get_storage_backend_for_provider(storage_provider).delete(file_path)
        return
    for candidate in _legacy_disk_candidates(file_path):
        if candidate.is_file():
            candidate.unlink(missing_ok=True)
            return


def object_exists(file_path: str, *, storage_provider: str | None = None) -> bool:
    if is_object_store_key(file_path):
        return get_storage_backend_for_provider(storage_provider).exists(file_path)
    return any(candidate.is_file() for candidate in _legacy_disk_candidates(file_path))


def generate_signed_upload_url(
    category: str,
    *segments: str,
    filename: str,
    content_type: str,
    expires_seconds: int = 300,
) -> tuple[str, str]:
    from app.storage.keys import build_object_key

    backend = get_storage_backend()
    if not hasattr(backend, "presign_put"):
        raise HTTPException(status_code=400, detail="Signed uploads are not enabled for current storage provider")
    key = build_object_key(category, *segments, filename=filename)
    url = backend.presign_put(key, content_type=content_type, expires_seconds=expires_seconds)
    return key, url


def stored_file_response(
    file_path: str,
    *,
    filename: str,
    media_type: str,
    storage_provider: str | None = None,
    inline: bool = False,
) -> Response:
    data = read_stored_bytes(file_path, storage_provider=storage_provider)
    disposition = "inline" if inline else "attachment"
    safe_name = Path(filename or "file").name
    return Response(
        content=data,
        media_type=media_type or "application/octet-stream",
        headers={"Content-Disposition": f'{disposition}; filename="{safe_name}"'},
    )
