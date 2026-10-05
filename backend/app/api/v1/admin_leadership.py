from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.permissions import RoleName, user_has_permission
from app.models.user import User
from app.services import admin_leadership_overview_service as lead_svc
from app.services import data_exceptions_service as exc_svc
from app.services import therapist_attention_service as attn_svc

router = APIRouter(prefix="/admin/leadership", tags=["admin-leadership"])


def _admin_dashboard_user(user: User = Depends(get_current_user)) -> User:
    roles = set(user.role_names or [])
    if RoleName.SPOT.value in roles:
        return user
    if not (
        user_has_permission(user, "case.read.all")
        or user_has_permission(user, "case.read.team")
        or user_has_permission(user, "admin.override")
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return user


def _require_attention(user: User) -> User:
    if not attn_svc.can_view_therapist_attention(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Therapist attention access required")
    return user


def _require_exceptions(user: User) -> User:
    if not exc_svc.can_view_data_exceptions(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Data exceptions access required")
    return user


@router.get("/overview")
def leadership_overview(
    period_month: Optional[str] = Query(None),
    product_module: Optional[str] = Query(None),
    user: User = Depends(_admin_dashboard_user),
    db: Session = Depends(get_db),
):
    return lead_svc.build_leadership_overview(
        db, user, period_month=period_month, product_module=product_module
    )


@router.get("/therapist-attention")
def therapist_attention(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    window_days: int = Query(14, ge=1, le=90),
    user: User = Depends(_admin_dashboard_user),
    db: Session = Depends(get_db),
):
    _require_attention(user)
    return attn_svc.list_therapist_attention(
        db, user, page=page, page_size=page_size, window_days=window_days
    )


@router.get("/data-exceptions")
def data_exceptions(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    confirmation: Optional[str] = Query(None),
    user: User = Depends(_admin_dashboard_user),
    db: Session = Depends(get_db),
):
    _require_exceptions(user)
    return exc_svc.list_data_exceptions(
        db, user, page=page, page_size=page_size, confirmation=confirmation
    )
