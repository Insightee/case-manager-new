from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.module_access import user_has_feature
from app.core.permissions import require_permission, user_has_permission
from app.models.invoice import Invoice, InvoiceStatus
from app.models.review import ReviewDecision
from app.models.user import User
from app.schemas.invoice import InvoiceRead, PaymentUpdate
from app.schemas.billing import InvoiceSubmitRequest, LateSessionCreate
from app.schemas.report import ReviewAction
from app.services import invoice_service
from app.services import invoice_billing_service

router = APIRouter(prefix="/invoices", tags=["invoices"])


def _invoice_read(i: Invoice, db: Optional[Session] = None) -> InvoiceRead:
    therapist_name = None
    if db:
        u = db.get(User, i.therapist_user_id)
        therapist_name = u.full_name if u else None
    return InvoiceRead(
        id=i.id,
        therapist_user_id=i.therapist_user_id,
        therapist_name=therapist_name,
        month=i.month,
        amount_inr=float(i.amount_inr),
        paid_amount_inr=float(i.paid_amount_inr) if i.paid_amount_inr else None,
        sessions_count=i.sessions_count,
        status=i.status,
        reviewer_comment=i.reviewer_comment,
        created_at=i.created_at,
        subtotal_inr=float(i.subtotal_inr) if i.subtotal_inr else None,
        leave_deduction_inr=float(i.leave_deduction_inr) if i.leave_deduction_inr else None,
        adjustment_inr=float(i.adjustment_inr) if i.adjustment_inr else None,
        notes=i.notes,
    )


@router.get("", response_model=list[InvoiceRead])
def list_invoices(
    status: Optional[InvoiceStatus] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user_has_permission(user, "invoice.approve") and not user_has_permission(user, "invoice.generate"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    if user_has_permission(user, "invoice.approve") and not user_has_feature(user, "invoices"):
        raise HTTPException(status_code=403, detail="Billing module access required")
    invoices = invoice_service.list_invoices(db, status)
    if user_has_permission(user, "invoice.generate") and not user_has_permission(user, "invoice.approve"):
        invoices = [i for i in invoices if i.therapist_user_id == user.id]
    return [_invoice_read(i, db) for i in invoices]


@router.get("/preview")
def preview_invoice(
    month: str = Query(..., description="YYYY-MM or Mon YYYY"),
    user: User = Depends(require_permission("invoice.generate")),
    db: Session = Depends(get_db),
):
    return invoice_billing_service.build_month_preview(db, user.id, month)


@router.post("/late-sessions", status_code=status.HTTP_201_CREATED)
def create_late_session(
    payload: LateSessionCreate,
    request: Request,
    user: User = Depends(require_permission("invoice.generate")),
    db: Session = Depends(get_db),
):
    try:
        result = invoice_billing_service.create_late_session(
            db,
            user.id,
            case_id=payload.case_id,
            month=payload.month,
            session_date=payload.session_date,
            start_time=payload.start_time,
            end_time=payload.end_time,
            attendance_status=payload.attendance_status,
            activities_done=payload.activities_done,
            observations=payload.observations,
            late_reason=payload.late_reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="create",
        entity_type="session",
        entity_id=result["session_id"],
        new_value=payload.model_dump(mode="json"),
        **meta,
    )
    db.commit()
    return result


@router.delete("/late-sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_late_session(
    session_id: int,
    request: Request,
    user: User = Depends(require_permission("invoice.generate")),
    db: Session = Depends(get_db),
):
    try:
        invoice_billing_service.delete_late_session(db, user.id, session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="delete", entity_type="session", entity_id=session_id, **meta)
    db.commit()
    return None


@router.post("/submit", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
def submit_invoice(
    payload: InvoiceSubmitRequest,
    request: Request,
    user: User = Depends(require_permission("invoice.generate")),
    db: Session = Depends(get_db),
):
    preview = invoice_billing_service.build_month_preview(db, user.id, payload.month)
    if payload.edits:
        edits_dict = payload.edits.model_dump()
        preview = invoice_billing_service.apply_preview_edits(preview, edits_dict)
    try:
        invoice = invoice_billing_service.submit_invoice_from_preview(db, user.id, preview, payload.notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="submit", entity_type="invoice", entity_id=invoice.id, **meta)
    db.commit()
    db.refresh(invoice)
    return _invoice_read(invoice, db)


@router.get("/{invoice_id}/breakdown")
def invoice_breakdown(
    invoice_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if user_has_permission(user, "invoice.generate") and not user_has_permission(user, "invoice.approve"):
        if invoice.therapist_user_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")
    elif not user_has_permission(user, "invoice.approve") and not user_has_permission(user, "therapist.read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    data = invoice_billing_service.invoice_breakdown(db, invoice_id)
    if not data:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return data


@router.post("/{invoice_id}/approve")
def approve_invoice(
    invoice_id: int,
    payload: ReviewAction,
    request: Request,
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    invoice_service.review_invoice(db, invoice, user.id, ReviewDecision.APPROVE, payload.comment)
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="approve", entity_type="invoice", entity_id=invoice.id, **meta)
    db.commit()
    return {"status": "approved"}


@router.post("/{invoice_id}/reject")
def reject_invoice(
    invoice_id: int,
    payload: ReviewAction,
    request: Request,
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    invoice_service.review_invoice(db, invoice, user.id, ReviewDecision.REJECT, payload.comment)
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="reject", entity_type="invoice", entity_id=invoice.id, **meta)
    db.commit()
    return {"status": "rejected"}


@router.patch("/{invoice_id}/payment")
def update_payment(
    invoice_id: int,
    payload: PaymentUpdate,
    request: Request,
    user: User = Depends(require_permission("payout.override")),
    db: Session = Depends(get_db),
):
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    old = {"paid_amount_inr": float(invoice.paid_amount_inr) if invoice.paid_amount_inr else None}
    invoice.paid_amount_inr = payload.paid_amount_inr
    invoice.status = payload.status
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="payment_override", entity_type="invoice", entity_id=invoice.id, old_value=old, new_value=payload.model_dump(), **meta)
    db.commit()
    return {"status": "updated"}
