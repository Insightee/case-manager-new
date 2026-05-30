from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.module_write import ensure_billing_write_access
from app.core.permissions import require_mutation_permission, require_permission
from app.models.user import User
from app.services import finance_bulk_service, finance_overview_service, finance_reports_service

router = APIRouter(prefix="/admin", tags=["admin-finance"])


@router.get("/finance-overview/summary")
def finance_overview(
    billing_month: Optional[str] = None,
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    return finance_overview_service.finance_overview_summary(db, billing_month=billing_month)


@router.get("/finance-reports/{report_key}")
def finance_report(
    report_key: str,
    billing_month: Optional[str] = None,
    format: str = Query("json", pattern="^(json|csv)$"),
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    try:
        rows = finance_reports_service.report_rows(db, report_key, billing_month=billing_month)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if format == "csv":
        csv_text = finance_reports_service.report_csv(report_key, rows)
        return Response(
            content=csv_text,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{report_key}.csv"'},
        )
    return {"reportKey": report_key, "rows": rows, "count": len(rows)}


class BulkClientInvoicesBody(BaseModel):
    action: str = Field(..., description="build_from_ledger")
    case_ids: list[int] = Field(min_length=1)
    billing_month: str
    include_pending: bool = False


@router.post("/finance-bulk/client-invoices")
def bulk_client_invoices(
    payload: BulkClientInvoicesBody,
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    ensure_billing_write_access(user)
    result = finance_bulk_service.bulk_client_invoices(
        db,
        action=payload.action,
        case_ids=payload.case_ids,
        billing_month=payload.billing_month,
        admin_user_id=user.id,
        include_pending=payload.include_pending,
    )
    db.commit()
    return result


class BulkTherapistPayoutsBody(BaseModel):
    action: str = Field(..., description="approve | mark_paid")
    invoice_ids: list[int] = Field(min_length=1)
    paid_amounts: Optional[dict[int, float]] = None


@router.post("/finance-bulk/therapist-payouts")
def bulk_therapist_payouts(
    payload: BulkTherapistPayoutsBody,
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    ensure_billing_write_access(user)
    result = finance_bulk_service.bulk_therapist_payouts(
        db,
        action=payload.action,
        invoice_ids=payload.invoice_ids,
        reviewer_user_id=user.id,
        paid_amount_by_id=payload.paid_amounts,
    )
    db.commit()
    return result
