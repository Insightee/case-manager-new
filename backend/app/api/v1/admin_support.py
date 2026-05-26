from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.permissions import user_has_permission
from app.models.user import User
from app.services import support_history_service as hist_svc

router = APIRouter(prefix="/admin/support", tags=["admin-support"])


def _require_support_reports(user: User) -> None:
    if not (
        user_has_permission(user, "ticket.manage")
        or user_has_permission(user, "incident.read_sensitive")
        or user_has_permission(user, "admin.override")
    ):
        raise HTTPException(status_code=403, detail="Support reports access required")


@router.get("/history")
def support_history(
    record_type: Literal["all", "tickets", "incidents"] = "all",
    status: Optional[str] = None,
    product_module: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    therapist_user_id: Optional[int] = None,
    child_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_support_reports(user)
    return hist_svc.list_support_history(
        db,
        user,
        record_type=record_type,
        status=status,
        product_module=product_module,
        date_from=date_from,
        date_to=date_to,
        therapist_user_id=therapist_user_id,
        child_id=child_id,
        page=page,
        page_size=page_size,
    )


@router.get("/history/export.csv")
def support_history_export(
    record_type: Literal["all", "tickets", "incidents"] = "all",
    status: Optional[str] = None,
    product_module: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    therapist_user_id: Optional[int] = None,
    child_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_support_reports(user)
    csv_text = hist_svc.export_support_history_csv(
        db,
        user,
        record_type=record_type,
        status=status,
        product_module=product_module,
        date_from=date_from,
        date_to=date_to,
        therapist_user_id=therapist_user_id,
        child_id=child_id,
    )
    return PlainTextResponse(
        csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=support-history.csv"},
    )
