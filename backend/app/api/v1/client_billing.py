from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.module_write import ensure_billing_write_access
from app.core.permissions import RoleName, require_mutation_permission, require_permission
from app.models.user import User
from app.schemas.client_billing import (
    AdminClientInvoiceCreate,
    AdminClientInvoiceUpdate,
    AdminDisputeResolve,
    BillingDisputeCreate,
    ClientPaymentRecord,
    PaymentClaimReject,
)
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


@parent_router.get("/invoices/{invoice_id}/pdf")
def parent_invoice_pdf(
    invoice_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    _require_parent(user)
    try:
        inv = client_billing_service.get_invoice_detail(db, user, invoice_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Invoice not found")
    pdf = client_billing_service.client_invoice_pdf_bytes(inv)
    safe = inv.get("invoiceNumber", str(invoice_id)).replace("/", "-")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="invoice_{safe}.pdf"'},
    )


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


@parent_router.post("/invoices/{invoice_id}/payment-claims", status_code=201)
async def parent_submit_payment_claim(
    invoice_id: int,
    request: Request,
    amount_inr: float = Form(...),
    method: str = Form(...),
    reference: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    proof: Optional[UploadFile] = File(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent(user)
    try:
        payment = await client_billing_service.submit_payment_claim(
            db, user, invoice_id, amount_inr, method, reference, notes, proof
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="payment_claim",
        entity_type="client_payment",
        entity_id=payment.id,
        **meta,
    )
    db.commit()
    return {"id": payment.id, "paymentStatus": payment.payment_status.value.lower()}


@parent_router.get("/payments/{payment_id}/proof")
def parent_payment_proof(
    payment_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    _require_parent(user)
    try:
        return client_billing_service.payment_proof_download(db, user, payment_id, admin=False)
    except ValueError:
        raise HTTPException(status_code=404, detail="Proof not found")


@admin_router.get("/summary")
def admin_billing_summary(
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    return client_billing_service.admin_summary(db)


def _invoice_list_params(
    month: Optional[str] = None,
    year: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    case_id: Optional[int] = None,
    status: Optional[str] = None,
    invoice_type: Optional[str] = None,
    module: Optional[str] = None,
    search: Optional[str] = None,
) -> dict:
    return {
        "month": month,
        "year": year,
        "date_from": date_from,
        "date_to": date_to,
        "case_id": case_id,
        "status": status,
        "invoice_type": invoice_type,
        "module": module,
        "search": search,
    }


@admin_router.get("/invoices/filter-options")
def admin_invoice_filter_options(
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    return client_billing_service.admin_invoice_filter_options(db)


@admin_router.get("/invoices/export/xlsx")
def admin_export_invoices_xlsx(
    month: Optional[str] = None,
    year: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    case_id: Optional[int] = None,
    status: Optional[str] = None,
    invoice_type: Optional[str] = None,
    module: Optional[str] = None,
    search: Optional[str] = None,
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    import openpyxl
    from io import BytesIO

    rows = client_billing_service.admin_list_invoices(db, **_invoice_list_params(
        month=month, year=year, date_from=date_from, date_to=date_to,
        case_id=case_id, status=status, invoice_type=invoice_type, module=module, search=search,
    ))
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Client Invoices"
    ws.append(
        [
            "Invoice #",
            "Child",
            "Case",
            "Parent",
            "Month",
            "Type",
            "Status",
            "Total INR",
            "Paid INR",
            "Balance INR",
            "Due Date",
        ]
    )
    for r in rows:
        ws.append(
            [
                r.get("invoiceNumber"),
                r.get("childName"),
                r.get("caseId"),
                r.get("parentName"),
                r.get("billingMonth"),
                r.get("invoiceType"),
                r.get("status"),
                r.get("totalInr"),
                r.get("amountPaidInr"),
                r.get("balanceInr"),
                r.get("dueDate") or "",
            ]
        )
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=client_invoices.xlsx"},
    )


@admin_router.get("/invoices/export/pdf")
def admin_export_invoices_pdf(
    month: Optional[str] = None,
    year: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    case_id: Optional[int] = None,
    status: Optional[str] = None,
    invoice_type: Optional[str] = None,
    module: Optional[str] = None,
    search: Optional[str] = None,
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet

    rows = client_billing_service.admin_list_invoices(db, **_invoice_list_params(
        month=month, year=year, date_from=date_from, date_to=date_to,
        case_id=case_id, status=status, invoice_type=invoice_type, module=module, search=search,
    ))
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=30, rightMargin=30, topMargin=40, bottomMargin=30)
    styles = getSampleStyleSheet()
    elements = [Paragraph("Client Invoices Report", styles["Title"]), Spacer(1, 12)]
    table_data = [
        ["Invoice #", "Child", "Case", "Parent", "Month", "Type", "Status", "Total", "Balance", "Due"]
    ]
    for r in rows:
        table_data.append(
            [
                r.get("invoiceNumber", ""),
                (r.get("childName") or "")[:20],
                r.get("caseId", ""),
                (r.get("parentName") or "")[:18],
                r.get("billingMonth", ""),
                r.get("invoiceType", ""),
                r.get("status", ""),
                f"₹{r.get('totalInr', 0):,.0f}",
                f"₹{r.get('balanceInr', 0):,.0f}",
                r.get("dueDate") or "",
            ]
        )
    t = Table(table_data, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6366f1")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ]
        )
    )
    elements.append(t)
    doc.build(elements)
    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=client_invoices.pdf"},
    )


@admin_router.get("/invoices")
def admin_list_client_invoices(
    month: Optional[str] = None,
    year: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    case_id: Optional[int] = None,
    status: Optional[str] = None,
    invoice_type: Optional[str] = None,
    module: Optional[str] = None,
    search: Optional[str] = None,
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    return client_billing_service.admin_list_invoices(db, **_invoice_list_params(
        month=month, year=year, date_from=date_from, date_to=date_to,
        case_id=case_id, status=status, invoice_type=invoice_type, module=module, search=search,
    ))


@admin_router.post("/invoices")
def admin_create_client_invoice(
    payload: AdminClientInvoiceCreate,
    request: Request,
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    ensure_billing_write_access(user)
    try:
        inv = client_billing_service.admin_create_invoice(
            db,
            case_id=payload.case_id,
            invoice_type=payload.invoice_type,
            billing_month=payload.billing_month,
            due_date=payload.due_date,
            lines=[ln.model_dump() for ln in payload.lines],
            notes=payload.notes,
            discount_inr=payload.discount_inr,
            admin_user_id=user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="create_client_invoice",
        entity_type="client_invoice",
        entity_id=inv.id,
        **meta,
    )
    db.commit()
    return client_billing_service.admin_get_invoice_detail(db, inv.id)


@admin_router.get("/invoices/{invoice_id}")
def admin_get_client_invoice(
    invoice_id: int,
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    try:
        return client_billing_service.admin_get_invoice_detail(db, invoice_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Invoice not found")


@admin_router.patch("/invoices/{invoice_id}")
def admin_patch_client_invoice(
    invoice_id: int,
    payload: AdminClientInvoiceUpdate,
    request: Request,
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    ensure_billing_write_access(user)
    try:
        inv = client_billing_service.admin_update_invoice(
            db, invoice_id, payload.model_dump(exclude_unset=True)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="update_client_invoice",
        entity_type="client_invoice",
        entity_id=invoice_id,
        **meta,
    )
    db.commit()
    return client_billing_service.admin_get_invoice_detail(db, inv.id)


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
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    ensure_billing_write_access(user)
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
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    ensure_billing_write_access(user)
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


@admin_router.post("/payments/{payment_id}/confirm")
def admin_confirm_payment_claim(
    payment_id: int,
    request: Request,
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    ensure_billing_write_access(user)
    try:
        client_billing_service.confirm_payment_claim(db, payment_id, user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="confirm_payment", entity_type="client_payment", entity_id=payment_id, **meta)
    db.commit()
    return {"status": "confirmed"}


@admin_router.post("/payments/{payment_id}/reject")
def admin_reject_payment_claim(
    payment_id: int,
    payload: PaymentClaimReject,
    request: Request,
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    ensure_billing_write_access(user)
    try:
        client_billing_service.reject_payment_claim(db, payment_id, user.id, payload.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="reject_payment", entity_type="client_payment", entity_id=payment_id, **meta)
    db.commit()
    return {"status": "rejected"}


@admin_router.get("/payments/{payment_id}/proof")
def admin_payment_proof(
    payment_id: int,
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    try:
        return client_billing_service.payment_proof_download(db, user, payment_id, admin=True)
    except ValueError:
        raise HTTPException(status_code=404, detail="Proof not found")


@admin_router.post("/disputes/{dispute_id}/resolve")
def admin_resolve_dispute(
    dispute_id: int,
    payload: AdminDisputeResolve,
    request: Request,
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    ensure_billing_write_access(user)
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
