from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.module_write import ensure_billing_write_access
from app.core.permissions import require_mutation_permission, require_permission
from app.models.user import User
from app.services import (
    finance_bulk_service,
    finance_monday_brief_service,
    finance_overview_service,
    finance_reports_service,
    statement_dispute_service,
    therapist_payout_queue_service,
)
from app.services.export_document_service import export_meta
from app.services import reports_export_service

router = APIRouter(prefix="/admin", tags=["admin-finance"])


@router.get("/finance-overview/summary")
def finance_overview(
    billing_month: Optional[str] = None,
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    return finance_overview_service.finance_overview_summary(db, billing_month=billing_month)


@router.get("/finance-overview/monday-brief")
def finance_monday_brief(
    billing_month: Optional[str] = None,
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    return finance_monday_brief_service.monday_finance_brief(db, billing_month=billing_month)


@router.get("/therapist-payouts/queue")
def therapist_payout_queue(
    month: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    return therapist_payout_queue_service.admin_payout_queue_summary(
        db, month=month, status=status, search=search
    )


class StatementDisputeResolveBody(BaseModel):
    status: str = Field(..., description="RESOLVED | REJECTED")
    resolution: str = Field(..., min_length=1, max_length=2000)


@router.post("/therapist-payouts/statement-disputes/{dispute_id}/resolve")
def resolve_statement_dispute(
    dispute_id: int,
    payload: StatementDisputeResolveBody,
    request: Request,
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    ensure_billing_write_access(user)
    resolution = (payload.resolution or "").strip()
    if payload.status.upper() == "REJECTED" and not resolution:
        raise HTTPException(status_code=400, detail="Rejection comment is required")
    try:
        dispute = statement_dispute_service.resolve_statement_dispute(
            db,
            dispute_id,
            status=payload.status,
            resolution=resolution,
            resolved_by_user_id=user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="resolve_statement_dispute",
        entity_type="statement_dispute",
        entity_id=dispute.id,
        new_value={"status": payload.status.upper(), "invoice_id": dispute.invoice_id},
        **meta,
    )
    db.commit()
    return statement_dispute_service.dispute_dict(dispute)


class CloseBillingMonthBody(BaseModel):
    billing_month: str = Field(..., min_length=7, max_length=7)
    notes: Optional[str] = None
    force: bool = False


@router.get("/finance-reports/billing-month-close")
def billing_month_close_status(
    billing_month: str,
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    from app.services import billing_period_snapshot_service

    row = billing_period_snapshot_service.get_month_close(db, billing_month)
    if not row:
        return {
            "billingMonth": billing_period_snapshot_service.normalize_billing_month(billing_month),
            "closed": False,
        }
    return {"closed": True, **billing_period_snapshot_service.month_close_dict(row)}


@router.post("/finance-reports/close-billing-month")
def close_billing_month(
    payload: CloseBillingMonthBody,
    request: Request,
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    ensure_billing_write_access(user)
    from app.services import billing_period_snapshot_service

    try:
        result = billing_period_snapshot_service.close_billing_month(
            db,
            billing_month=payload.billing_month,
            actor_user_id=user.id,
            notes=payload.notes,
            force=payload.force,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="billing_month.close",
        entity_type="billing_month_close",
        entity_id=payload.billing_month,
        **meta,
    )
    db.commit()
    return result


@router.get("/finance-reports/{report_key}")
def finance_report(
    report_key: str,
    billing_month: Optional[str] = None,
    format: str = Query("json", pattern="^(json|csv|xlsx)$"),
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    try:
        rows = finance_reports_service.report_rows(db, report_key, billing_month=billing_month)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    meta = export_meta(user)
    title = finance_reports_service.report_title(report_key)
    subtitle = finance_reports_service.report_subtitle(report_key, billing_month=billing_month)

    from app.services import billing_period_snapshot_service

    ym = finance_reports_service._ym(billing_month)
    month_closed = billing_period_snapshot_service.is_billing_month_closed(db, ym)
    snapshot_reports = frozenset({"therapist-payout-preview", "margin-by-case"})
    data_source = "snapshot" if month_closed and report_key in snapshot_reports else "live"
    if month_closed:
        subtitle = f"{subtitle} · closed snapshot"

    if format == "csv":
        csv_text = finance_reports_service.report_csv(report_key, rows)
        return Response(
            content=csv_text,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{report_key}.csv"'},
        )

    if format == "xlsx":
        content = reports_export_service.payload_to_xlsx(
            title=title,
            subtitle=subtitle,
            user=user,
            rows=rows,
        )
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{report_key}.xlsx"'},
        )

    return {
        "reportKey": report_key,
        "title": title,
        "rows": rows,
        "count": len(rows),
        "generatedBy": meta["generated_by"],
        "generatedAt": meta["generated_at"],
        "billingMonthClosed": month_closed,
        "dataSource": data_source,
    }


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
