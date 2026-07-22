from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.permissions import require_any_permission
from app.core.reports_catalog import REPORT_KEYS, catalog_payload, report_definition
from app.models.user import User
from app.services import hr_reports_service, reports_export_service
from app.services.reports_export_helpers import default_export_month, month_long_label, normalize_month

router = APIRouter(prefix="/admin", tags=["admin-hr"])


def _report_subtitle(
    report_key: str,
    *,
    month: str | None,
    date_from: str | None,
    date_to: str | None,
) -> str:
    if report_key in {"session-log-detail"}:
        return f"Period: {date_from or '—'} to {date_to or '—'}"
    ym = normalize_month(month)
    return f"Month: {month_long_label(ym)}"


@router.get("/hr-reports/catalog")
def hr_report_catalog(
    user: User = Depends(require_any_permission("hr_report.export", "user.manage")),
):
    return catalog_payload()


@router.get("/hr-reports/{report_key}")
def hr_report(
    report_key: str,
    category: Optional[str] = None,
    month: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    product_module: Optional[str] = None,
    case_manager_user_id: Optional[int] = None,
    therapist_user_id: Optional[int] = None,
    case_id: Optional[int] = None,
    format: str = Query("json", pattern="^(json|csv|xlsx|pdf)$"),
    user: User = Depends(require_any_permission("hr_report.export", "user.manage")),
    db: Session = Depends(get_db),
):
    if report_key not in REPORT_KEYS:
        raise HTTPException(status_code=404, detail=f"Unknown report: {report_key}")

    definition = report_definition(report_key) or {}
    allowed_formats = definition.get("formats") or ["csv"]
    if format != "json" and format not in allowed_formats:
        raise HTTPException(status_code=400, detail=f"Format '{format}' is not supported for this report")

    try:
        payload = hr_reports_service.run_hr_report(
            db,
            report_key,
            category=category,
            month=month or default_export_month(),
            date_from=date_from,
            date_to=date_to,
            product_module=product_module,
            case_manager_user_id=case_manager_user_id,
            therapist_user_id=therapist_user_id,
            case_id=case_id,
            user=user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if format == "json":
        return {
            "reportKey": report_key,
            "category": category,
            "rows": payload.get("rows") or [],
            "summaryRows": payload.get("summaryRows") or [],
            "count": payload.get("count", 0),
        }

    subtitle = _report_subtitle(
        report_key,
        month=month,
        date_from=date_from,
        date_to=date_to,
    )
    try:
        content, media_type, stem = reports_export_service.export_payload(
            report_key,
            payload,
            format,
            user=user,
            subtitle=subtitle,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    ext = format if format != "xlsx" else "xlsx"
    filename = f"{stem}.{ext}"
    if format == "csv":
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
