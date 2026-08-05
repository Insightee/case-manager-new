"""Environment-gated product modules for safe staged rollout."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.core.config import settings
from app.core.permissions import RoleName
from app.models.user import User


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


def require_billing_ledger_writes() -> None:
    """HTTP gate for invoice/ledger money mutations when writes are off.

    Distinct from ``require_billing`` (router visibility). Staging PASS 2 keeps
    ``BILLING_LEDGER_WRITES=false`` so preview/Control Tower can run without
    creating invoices or promoting PENDING_FINANCE rows.
    """
    if not billing_ledger_writes_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Posting disabled until ledger writes are enabled (pre-cutover).",
        )


_CONTROL_TOWER_ROLES = frozenset({RoleName.SUPER_ADMIN.value, RoleName.FINANCE.value})


def require_finance_control_tower_read() -> Callable:
    """Stage 1 Control Tower: SUPER_ADMIN + FINANCE only (Founder/COO → SUPER_ADMIN)."""
    from app.api.deps import get_current_user

    def checker(user: User = Depends(get_current_user)) -> User:
        names = set(user.role_names or [])
        if not names.intersection(_CONTROL_TOWER_ROLES):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Finance Control Tower is limited to Finance and Super Admin roles.",
            )
        return user

    return checker


def require_finance_writable() -> Callable:
    """Loop 2 finance writable: FINANCE + SUPER_ADMIN; proposals require human confirm."""
    from app.api.deps import get_current_user

    def checker(user: User = Depends(get_current_user)) -> User:
        names = set(user.role_names or [])
        if not names.intersection(_CONTROL_TOWER_ROLES):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Finance corrections are limited to Finance and Super Admin roles.",
            )
        return user

    return checker


def payout_export_enabled() -> bool:
    return bool(getattr(settings, "payout_export_enabled", False))


def payout_release_enabled() -> bool:
    return bool(getattr(settings, "payout_release_enabled", False))


def require_payout_export_enabled() -> None:
    if not payout_export_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Payout batch export is disabled until cutover (PAYOUT_EXPORT_ENABLED).",
        )


def require_payout_release_enabled() -> None:
    if not payout_release_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Live payout release is disabled until final cutover (PAYOUT_RELEASE_ENABLED).",
        )
