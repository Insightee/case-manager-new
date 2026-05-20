from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.permissions import RoleName, require_permission
from app.models.user import User
from app.schemas.client_billing import AdminDisputeResolve, BillingDisputeCreate, ClientPaymentRecord
from app.services import client_billing_service

parent_router = APIRouter(prefix="/parent/billing", tags=["parent-billing"])
admin_router = APIRouter(prefix="/admin/client-billing", tags=["admin-client-billing"])


def _require_parent(user: User):
    if RoleName.PARENT.value not in user.role_names:
        raise HTTPException(status_code=403, detail="Parent access only")


@parent_router.get("/dashboard")
def parent_billing_dashboard(
    month: Optional[str] = None,
    case_id: Optional[int] = None,
    service: Optional[str] = None,
    payment_bucket: Optional[str] = Query(
        None,
        description="Filter: paid | unpaid | partial | disputed | needs_payment (unpaid+partial)",
    ),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent(user)
    return client_billing_service.get_dashboard(
        db, user, month=month, case_id=case_id, service=service, payment_bucket=payment_bucket
    )


@parent_router.get("/invoices")
def parent_list_invoices(
    month: Optional[str] = None,
    case_id: Optional[int] = None,
    service: Optional[str] = None,
    payment_bucket: Optional[str] = Query(None, description="paid | unpaid | partial | disputed | needs_payment"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent(user)
    return client_billing_service.list_invoices(
        db, user, month=month, case_id=case_id, service=service, payment_bucket=payment_bucket
    )


@parent_router.get("/invoices/{invoice_id}")
def parent_invoice_detail(
    invoice_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    _require_parent(user)
    try:
        return client_billing_service.get_invoice_detail(db, user, invoice_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Invoice not found")


@parent_router.get("/invoices/{invoice_id}/print", response_class=HTMLResponse)
def parent_invoice_print(
    invoice_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    _require_parent(user)
    try:
        inv = client_billing_service.get_invoice_detail(db, user, invoice_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Invoice not found")
    rows = "".join(
        f"<tr><td>{l['sessionDate']}</td><td>{l['therapistName']}</td>"
        f"<td>{l['serviceLabel']}</td><td>{l['sessionStatus']}</td>"
        f"<td>₹{l['amountInr']:,.0f}</td></tr>"
        for l in inv["lines"]
    )
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>{inv['invoiceNumber']}</title>
    <style>body{{font-family:system-ui;padding:24px}}table{{width:100%;border-collapse:collapse}}
    th,td{{border:1px solid #ddd;padding:8px;text-align:left}}th{{background:#f3f4f6}}</style></head>
    <body><h1>{inv['invoiceNumber']}</h1><p>{inv['childName']} · {inv['caseId']} · {inv['month']}</p>
    <p>Type: {inv['invoiceType']} · Status: {inv['status']} · Due: {inv.get('dueDate') or '—'}</p>
    <table><thead><tr><th>Date</th><th>Therapist</th><th>Service</th><th>Status</th><th>Cost</th></tr></thead>
    <tbody>{rows}</tbody></table>
    <p><strong>Total:</strong> ₹{inv['totalInr']:,.0f} · Paid: ₹{inv['amountPaidInr']:,.0f} · Balance: ₹{inv['balanceInr']:,.0f}</p>
    </body></html>"""
    return HTMLResponse(html)


@parent_router.get("/lines/{line_id}/session")
def parent_line_session(line_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_parent(user)
    try:
        return client_billing_service.get_line_session_detail(db, user, line_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found")


@parent_router.get("/packages")
def parent_packages(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_parent(user)
    return client_billing_service.list_packages(db, user)


@parent_router.post("/invoices/{invoice_id}/disputes")
def parent_create_dispute(
    invoice_id: int,
    payload: BillingDisputeCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent(user)
    try:
        result = client_billing_service.create_dispute(
            db, user, invoice_id, payload.reason_code, payload.message.strip(), payload.line_id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="billing_dispute", entity_type="client_invoice", entity_id=invoice_id, **meta)
    db.commit()
    return result


@admin_router.get("/disputes")
def admin_list_disputes(
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    from sqlalchemy import select
    from app.models.client_billing import BillingDispute, BillingDisputeStatus, ClientInvoice
    from app.models.case import Case

    rows = db.scalars(
        select(BillingDispute)
        .where(BillingDispute.status.in_([BillingDisputeStatus.OPEN, BillingDisputeStatus.UNDER_REVIEW]))
        .order_by(BillingDispute.created_at.desc())
    ).all()
    result = []
    for d in rows:
        inv = db.get(ClientInvoice, d.client_invoice_id)
        case = db.get(Case, inv.case_id) if inv else None
        result.append(
            {
                "id": d.id,
                "invoiceId": d.client_invoice_id,
                "invoiceNumber": inv.invoice_number if inv else "",
                "caseCode": case.case_code if case else "",
                "reasonCode": d.reason_code,
                "message": d.message,
                "status": d.status.value,
                "createdAt": d.created_at.isoformat() if d.created_at else None,
            }
        )
    return result


@admin_router.post("/invoices/{invoice_id}/notify-parent")
def admin_notify_parent_invoice(
    invoice_id: int,
    request: Request,
    resend: bool = Query(False, description="Send again even if already notified"),
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    try:
        result = client_billing_service.notify_parent_invoice_issued(db, invoice_id, resend=resend)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="notify_parent_invoice",
        entity_type="client_invoice",
        entity_id=invoice_id,
        **meta,
    )
    db.commit()
    return result


@admin_router.post("/invoices/{invoice_id}/payments")
def admin_record_payment(
    invoice_id: int,
    payload: ClientPaymentRecord,
    request: Request,
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    try:
        client_billing_service.record_payment(
            db,
            invoice_id,
            payload.amount_inr,
            payload.method,
            payload.reference,
            payload.notes,
            user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="record_payment", entity_type="client_invoice", entity_id=invoice_id, **meta)
    db.commit()
    return {"status": "recorded"}


@admin_router.post("/disputes/{dispute_id}/resolve")
def admin_resolve_dispute(
    dispute_id: int,
    payload: AdminDisputeResolve,
    request: Request,
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    try:
        client_billing_service.resolve_dispute(
            db, dispute_id, payload.status, payload.resolution.strip(), payload.adjustment_inr
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="resolve_dispute", entity_type="billing_dispute", entity_id=dispute_id, **meta)
    db.commit()
    return {"status": payload.status.lower()}
