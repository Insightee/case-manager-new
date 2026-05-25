from __future__ import annotations

from typing import Optional

from app.core.config import settings
from app.storage.base import StorageBackend
from app.storage.local_backend import LocalStorageBackend
from app.storage.r2_backend import R2StorageBackend

_backend: Optional[StorageBackend] = None


def _validate_r2_settings() -> None:
    missing = []
    if not settings.r2_account_id.strip() and not settings.r2_endpoint_url.strip():
        missing.append("R2_ACCOUNT_ID or R2_ENDPOINT_URL")
    if not settings.r2_access_key_id.strip():
        missing.append("R2_ACCESS_KEY_ID")
    if not settings.r2_secret_access_key.strip():
        missing.append("R2_SECRET_ACCESS_KEY")
    if not settings.r2_bucket_name.strip():
        missing.append("R2_BUCKET_NAME")
    if missing:
        raise RuntimeError(f"STORAGE_PROVIDER=r2 requires: {', '.join(missing)}")


def get_storage_backend() -> StorageBackend:
    global _backend
    if _backend is not None:
        return _backend
    provider = (settings.storage_provider or "local").strip().lower()
    if provider == "r2":
        _validate_r2_settings()
        _backend = R2StorageBackend()
    elif provider == "local":
        _backend = LocalStorageBackend()
    else:
        raise RuntimeError(f"Unknown STORAGE_PROVIDER: {settings.storage_provider}")
    return _backend


def get_storage_backend_for_provider(provider: Optional[str]) -> StorageBackend:
    """Resolve backend for a stored row (legacy rows may use local paths)."""
    p = (provider or settings.storage_provider or "local").strip().lower()
    if p == "r2":
        return R2StorageBackend()
    return LocalStorageBackend()


def reset_storage_backend_for_tests() -> None:
    global _backend
    _backend = None
