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
