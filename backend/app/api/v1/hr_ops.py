from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.user import User
from app.services import hr_reports_service

router = APIRouter(prefix="/admin", tags=["admin-hr"])


@router.get("/hr-reports/{report_key}")
def hr_report(
    report_key: str,
    category: Optional[str] = None,
    month: Optional[str] = None,
    product_module: Optional[str] = None,
    format: str = Query("json", pattern="^(json|csv)$"),
    user: User = Depends(require_permission("hr_report.export")),
    db: Session = Depends(get_db),
):
    try:
        rows = hr_reports_service.report_rows(
            db,
            report_key,
            category=category,
            month=month,
            product_module=product_module,
            user=user,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if format == "csv":
        csv_text = hr_reports_service.report_csv(report_key, rows)
        return Response(
            content=csv_text,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{report_key}.csv"'},
        )
    return {"reportKey": report_key, "category": category, "rows": rows, "count": len(rows)}
