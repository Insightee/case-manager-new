"""Environment-gated product modules for safe staged rollout."""

from __future__ import annotations

from fastapi import HTTPException, status

from app.core.config import settings


def _feature_unavailable() -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="This feature is not available in this environment.",
    )


def require_billing() -> None:
    if not settings.enable_billing:
        _feature_unavailable()


def billing_ledger_writes_enabled() -> bool:
    """Gate session/log ledger mutations. Independent of admin billing UI flag."""
    return bool(settings.billing_ledger_writes)
