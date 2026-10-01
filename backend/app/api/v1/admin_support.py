from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.services import support_history_service as hist_svc
from app.services import support_ticket_report_service as ticket_report
from app.services.support_access_service import can_view_support_tickets, support_hub_capabilities, support_scope

router = APIRouter(prefix="/admin/support", tags=["admin-support"])


def _require_support_reports(user: User, db: Session) -> None:
    if support_scope(user, db) == "none":
        raise HTTPException(status_code=403, detail="Support reports access required")


def _require_ticket_report(user: User, db: Session) -> None:
    if not can_view_support_tickets(user, db):
        raise HTTPException(status_code=403, detail="Support ticket report is available to staff who handle tickets.")


@router.get("/capabilities")
def support_capabilities(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return support_hub_capabilities(user, db)


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
    _require_support_reports(user, db)
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
    _require_support_reports(user, db)
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


@router.get("/ticket-report")
def support_ticket_report(
    status: Optional[str] = None,
    category: Optional[str] = None,
    product_module: Optional[str] = None,
    assigned_to: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Read-only counts and queue. Does not reply, close, or change tickets."""
    _require_ticket_report(user, db)
    try:
        return ticket_report.build_support_ticket_report(
            db,
            user,
            status=status,
            category=category,
            product_module=product_module,
            assigned_to=assigned_to,
            date_from=date_from,
            date_to=date_to,
        )
    except ticket_report.ReportFilterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/ticket-report.xlsx")
def support_ticket_report_xlsx(
    status: Optional[str] = None,
    category: Optional[str] = None,
    product_module: Optional[str] = None,
    assigned_to: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_ticket_report(user, db)
    try:
        payload = ticket_report.build_support_ticket_report(
            db,
            user,
            status=status,
            category=category,
            product_module=product_module,
            assigned_to=assigned_to,
            date_from=date_from,
            date_to=date_to,
        )
    except ticket_report.ReportFilterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    filters = payload["filters"]
    filename = f"support-tickets-report-{filters['date_from']}-to-{filters['date_to']}.xlsx"
    data = ticket_report.report_to_xlsx(payload, user)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
