from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.module_write import ensure_billing_write_access
from app.core.permissions import RoleName, require_mutation_permission, require_permission
from app.models.client_billing import ClientInvoice, ClientInvoiceLine
from app.models.user import User
from app.schemas.client_billing import (
    AdminClientInvoiceCreate,
    AdminClientInvoiceUpdate,
    AdminDisputeResolve,
    BillingDisputeCreate,
    DisputeCorrectionProposalBody,
    ClientInvoiceLinePatch,
    ClientInvoiceLineUpsert,
    ClientPaymentRecord,
    PaymentClaimReject,
    RemindTherapistRequest,
    OnboardingInvoiceDraftRequest,
    SaveCaseBillingPreferences,
)
from app.core.config import settings
from app.core.feature_flags import billing_ledger_writes_enabled, require_billing_ledger_writes
from app.services import billing_composer_service, client_billing_service, client_invoice_draft_service, finance_correction_service
from app.services import audit_service
from app.services.bookkeeping_provider import get_bookkeeping_provider

parent_router = APIRouter(prefix="/parent/billing", tags=["parent-billing"])
admin_router = APIRouter(prefix="/admin/client-billing", tags=["admin-client-billing"])


def _require_parent(user: User):
    if RoleName.PARENT.value not in user.role_names:
        raise HTTPException(status_code=403, detail="Parent access only")


def _billing_runtime_config() -> dict:
    from app.services import zoho_client_sync

    return {
        "billingEnabled": bool(settings.enable_billing),
        "ledgerWritesEnabled": billing_ledger_writes_enabled(),
        "cutoverComplete": bool(settings.finance_cutover_complete),
        "zohoConfigured": zoho_client_sync.zoho_configured(),
        "zohoBooksLivePush": bool(getattr(settings, "zoho_books_live_push", False)),
        "provisional": not bool(settings.finance_cutover_complete),
        "payoutExportEnabled": bool(getattr(settings, "payout_export_enabled", False)),
        "payoutReleaseEnabled": bool(getattr(settings, "payout_release_enabled", False)),
        "payoutProviderLive": bool(getattr(settings, "payout_provider_live", False)),
    }


@parent_router.get("/runtime-config")
def parent_billing_runtime_config(user: User = Depends(get_current_user)):
    """Parent-safe liveness flags (no internal write keys)."""
    _require_parent(user)
    cfg = _billing_runtime_config()
    return {
        "cutoverComplete": cfg["cutoverComplete"],
        "provisional": cfg["provisional"],
    }


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
        line_ids = payload.line_ids
        if line_ids is None and payload.line_id is not None:
            line_ids = [payload.line_id]
        result = client_billing_service.create_dispute(
            db,
            user,
            invoice_id,
            payload.reason_code,
            payload.message.strip(),
            line_id=payload.line_id,
            line_ids=line_ids,
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


@parent_router.post("/invoices/{invoice_id}/pay-gateway")
def parent_pay_gateway(
    invoice_id: int,
    request: Request,
    reference: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent(user)
    if not settings.enable_billing:
        raise HTTPException(status_code=403, detail="Billing is not enabled")
    try:
        result = client_billing_service.initiate_gateway_payment(
            db, user, invoice_id, reference=reference
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    if result.get("success") and result.get("paymentId"):
        log_audit(
            db,
            actor_user_id=user.id,
            action="gateway_payment",
            entity_type="client_payment",
            entity_id=result["paymentId"],
            **meta,
        )
    db.commit()
    return result


@parent_router.get("/payments/{payment_id}/receipt")
def parent_payment_receipt(
    payment_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    _require_parent(user)
    try:
        pdf, filename = client_billing_service.get_payment_receipt(db, user, payment_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Receipt not available")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@admin_router.get("/summary")
def admin_billing_summary(
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
    return client_billing_service.admin_summary(
        db,
        month=month,
        year=year,
        date_from=date_from,
        date_to=date_to,
        case_id=case_id,
        status=status,
        invoice_type=invoice_type,
        module=module,
        search=search,
    )


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
    claims_pending: Optional[bool] = None,
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
        "claims_pending": bool(claims_pending),
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
    claims_pending: Optional[bool] = Query(None),
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    return client_billing_service.admin_list_invoices(db, **_invoice_list_params(
        month=month, year=year, date_from=date_from, date_to=date_to,
        case_id=case_id, status=status, invoice_type=invoice_type, module=module, search=search,
        claims_pending=claims_pending,
    ))


@admin_router.post("/invoices")
def admin_create_client_invoice(
    payload: AdminClientInvoiceCreate,
    request: Request,
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    ensure_billing_write_access(user)
    require_billing_ledger_writes()
    ym = billing_composer_service.normalize_billing_month(payload.billing_month)
    blocking = billing_composer_service.blocking_calc_exceptions_for_case(
        db, case_id=payload.case_id, billing_month=ym
    )
    if blocking:
        codes = ", ".join(sorted({b["code"] for b in blocking}))
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot create invoice: open calculation exception(s) ({codes}). "
                "Resolve exceptions before generating a client invoice."
            ),
        )
    if not payload.lines:
        try:
            result = client_billing_service.create_draft_from_case_defaults(
                db,
                case_id=payload.case_id,
                billing_month=payload.billing_month,
                admin_user_id=user.id,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        meta = get_request_meta(request)
        log_audit(
            db,
            actor_user_id=user.id,
            action="create_client_invoice",
            entity_type="client_invoice",
            entity_id=result["id"],
            **meta,
        )
        db.commit()
        return result
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
                "lineId": d.client_invoice_line_id,
                "reasonCode": d.reason_code,
                "message": d.message,
                "status": d.status.value,
                "createdAt": d.created_at.isoformat() if d.created_at else None,
                "supportTicketId": d.support_ticket_id,
                "caseId": inv.case_id if inv else None,
                "billingMonth": inv.billing_month if inv else None,
            }
        )
    return result


@admin_router.post("/disputes/{dispute_id}/correction-proposal")
def admin_dispute_correction_proposal(
    dispute_id: int,
    payload: DisputeCorrectionProposalBody,
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    from app.models.client_billing import BillingDispute, ClientInvoice

    ensure_billing_write_access(user)
    require_billing_ledger_writes()
    dispute = db.get(BillingDispute, dispute_id)
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    inv = db.get(ClientInvoice, dispute.client_invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    try:
        proposal = finance_correction_service.create_correct_reshare_proposal(
            db,
            case_id=inv.case_id,
            billing_month=inv.billing_month,
            wrong_side=payload.wrong_side,
            reason=payload.reason,
            user_id=user.id,
            billing_dispute_id=dispute.id,
        )
        db.commit()
        return proposal
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e


@admin_router.get("/runtime-config")
def admin_billing_runtime_config(
    user: User = Depends(require_permission("invoice.approve")),
):
    """Single coherent answer for visible/live-or-provisional/writes/Zoho."""
    _ = user
    return _billing_runtime_config()


@admin_router.get("/composer-cases")
def admin_composer_cases(
    billing_month: str = Query(..., description="YYYY-MM or Mon YYYY"),
    queue: str = Query("all"),
    module: Optional[str] = None,
    search: Optional[str] = None,
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    return billing_composer_service.list_composer_cases(
        db, billing_month=billing_month, queue=queue, module=module, search=search
    )


@admin_router.get("/composer-preview")
def admin_composer_preview(
    case_id: int = Query(...),
    billing_month: str = Query(...),
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    try:
        return billing_composer_service.get_composer_preview(
            db, case_id=case_id, billing_month=billing_month
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@admin_router.get("/cases/{case_id}/billing-summary")
def admin_case_billing_summary(
    case_id: int,
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    try:
        return client_billing_service.case_billing_summary(db, case_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@admin_router.post("/cases/{case_id}/onboarding-invoice-draft", status_code=201)
def admin_onboarding_invoice_draft(
    case_id: int,
    payload: OnboardingInvoiceDraftRequest,
    request: Request,
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    ensure_billing_write_access(user)
    if payload.send_to_queue_only:
        return {
            "queued": True,
            "message": "Case will appear in Finance composer under New clients / Not invoiced.",
            "caseId": case_id,
        }
    ym = billing_composer_service.normalize_billing_month(
        payload.billing_month or date.today().strftime("%Y-%m")
    )
    try:
        result = client_billing_service.create_draft_from_case_defaults(
            db,
            case_id=case_id,
            billing_month=ym,
            admin_user_id=user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="onboarding_invoice_draft",
        entity_type="client_invoice",
        entity_id=result.get("id"),
        case_id=case_id,
        **meta,
    )
    db.commit()
    return result


@admin_router.post("/cases/{case_id}/build-from-ledger", status_code=201)
def admin_build_draft_from_ledger_for_case(
    case_id: int,
    request: Request,
    billing_month: str = Query(...),
    include_pending: bool = Query(False),
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    ensure_billing_write_access(user)
    require_billing_ledger_writes()
    ym = billing_composer_service.normalize_billing_month(billing_month)
    blocking = billing_composer_service.blocking_calc_exceptions_for_case(
        db, case_id=case_id, billing_month=ym
    )
    if blocking:
        codes = ", ".join(sorted({b["code"] for b in blocking}))
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot build invoice: open calculation exception(s) ({codes}). "
                "Resolve exceptions before generating a client invoice."
            ),
        )
    try:
        result = client_invoice_draft_service.generate_draft_from_ledger(
            db,
            case_id=case_id,
            billing_month=ym,
            actor_user_id=user.id,
            include_pending=include_pending,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="build_from_ledger",
        entity_type="client_invoice",
        entity_id=result["id"],
        case_id=case_id,
        **meta,
    )
    db.commit()
    detail = client_billing_service.admin_get_invoice_detail(db, result["id"])
    zoho = get_bookkeeping_provider().push_client_invoice(
        result["id"], payload={"event": "build_from_ledger"}, db=db
    )
    detail["zohoSync"] = {
        "status": zoho.status,
        "message": zoho.message,
        "externalId": zoho.external_id,
    }
    return detail


@admin_router.post("/remind-therapist")
def admin_remind_therapist(
    payload: RemindTherapistRequest,
    request: Request,
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    ensure_billing_write_access(user)
    try:
        result = billing_composer_service.remind_therapist(
            db,
            case_id=payload.case_id,
            billing_month=payload.billing_month,
            actor_user_id=user.id,
            message=payload.message,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="remind_therapist_billing",
        entity_type="case",
        entity_id=payload.case_id,
        new_value={"billing_month": payload.billing_month},
        **meta,
    )
    db.commit()
    return result


@admin_router.post("/invoices/{invoice_id}/lines", status_code=201)
def admin_add_invoice_line(
    invoice_id: int,
    payload: ClientInvoiceLineUpsert,
    request: Request,
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    ensure_billing_write_access(user)
    try:
        line = client_billing_service.admin_add_invoice_line(
            db, invoice_id, payload.model_dump()
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="add_invoice_line",
        entity_type="client_invoice_line",
        entity_id=line.id,
        new_value=client_billing_service._serialize_line(line),
        case_id=db.get(ClientInvoice, invoice_id).case_id if db.get(ClientInvoice, invoice_id) else None,
        **meta,
    )
    db.commit()
    return client_billing_service.admin_get_invoice_detail(db, invoice_id)


@admin_router.patch("/invoices/{invoice_id}/lines/{line_id}")
def admin_patch_invoice_line(
    invoice_id: int,
    line_id: int,
    payload: ClientInvoiceLinePatch,
    request: Request,
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    ensure_billing_write_access(user)
    try:
        line = client_billing_service.admin_patch_invoice_line(
            db, invoice_id, line_id, payload.model_dump(exclude_unset=True)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    before = getattr(line, "_audit_before", None)
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="update_invoice_line",
        entity_type="client_invoice_line",
        entity_id=line_id,
        old_value=before,
        new_value=client_billing_service._serialize_line(line),
        **meta,
    )
    db.commit()
    return client_billing_service.admin_get_invoice_detail(db, invoice_id)


@admin_router.delete("/invoices/{invoice_id}/lines/{line_id}")
def admin_delete_invoice_line(
    invoice_id: int,
    line_id: int,
    request: Request,
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    ensure_billing_write_access(user)
    line = db.get(ClientInvoiceLine, line_id)
    old = client_billing_service._serialize_line(line) if line else None
    try:
        client_billing_service.admin_delete_invoice_line(db, invoice_id, line_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="delete_invoice_line",
        entity_type="client_invoice_line",
        entity_id=line_id,
        old_value=old,
        **meta,
    )
    db.commit()
    return client_billing_service.admin_get_invoice_detail(db, invoice_id)


@admin_router.post("/invoices/{invoice_id}/recalculate")
def admin_recalculate_invoice(
    invoice_id: int,
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    ensure_billing_write_access(user)
    try:
        client_billing_service.recalculate_client_invoice(db, invoice_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return client_billing_service.admin_get_invoice_detail(db, invoice_id)


@admin_router.get("/invoices/{invoice_id}/audit-trail")
def admin_invoice_audit_trail(
    invoice_id: int,
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    inv = db.scalar(
        select(ClientInvoice)
        .where(ClientInvoice.id == invoice_id)
        .options(selectinload(ClientInvoice.lines))
    )
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    try:
        payload = audit_service.list_audit_events(
            db, user, case_id=inv.case_id, limit=100
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")
    line_ids = {str(ln.id) for ln in (inv.lines or [])}
    items = [
        it
        for it in payload.get("items", [])
        if it.get("entity_type") == "client_invoice" and it.get("entity_id") == str(invoice_id)
        or it.get("entity_type") == "client_invoice_line" and it.get("entity_id") in line_ids
        or it.get("action") in ("build_from_ledger", "create_client_invoice", "notify_parent_invoice")
    ]
    return {"items": items[:50], "next_cursor": payload.get("next_cursor")}


@admin_router.put("/cases/{case_id}/billing-preferences")
def admin_save_billing_preferences(
    case_id: int,
    payload: SaveCaseBillingPreferences,
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    ensure_billing_write_access(user)
    client_billing_service.save_case_billing_preferences(db, case_id, payload.model_dump(exclude_unset=True))
    db.commit()
    return billing_composer_service.get_saved_preferences(db, case_id)


@admin_router.post("/invoices/{invoice_id}/notify-parent")
def admin_notify_parent_invoice(
    invoice_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    resend: bool = Query(False, description="Send again even if already notified"),
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    ensure_billing_write_access(user)
    try:
        result = client_billing_service.notify_parent_invoice_issued(
            db, invoice_id, background_tasks, resend=resend
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    zoho = get_bookkeeping_provider().push_client_invoice(
        invoice_id, payload={"event": "notify_parent"}, db=db
    )
    if isinstance(result, dict):
        result = {
            **result,
            "zohoSync": {
                "status": zoho.status,
                "message": zoho.message,
                "externalId": zoho.external_id,
            },
        }
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


@admin_router.get("/receivables")
def admin_receivables(
    month: Optional[str] = None,
    year: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    case_id: Optional[int] = None,
    status: Optional[str] = None,
    invoice_type: Optional[str] = None,
    module: Optional[str] = None,
    search: Optional[str] = None,
    overdue_only: bool = Query(False),
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    return client_billing_service.admin_receivables_summary(
        db,
        month=month,
        year=year,
        date_from=date_from,
        date_to=date_to,
        case_id=case_id,
        status=status,
        invoice_type=invoice_type,
        module=module,
        search=search,
        overdue_only=overdue_only,
    )


@admin_router.post("/invoices/{invoice_id}/payment-reminder")
def admin_send_payment_reminder(
    invoice_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    ensure_billing_write_access(user)
    try:
        result = client_billing_service.send_payment_reminder(db, invoice_id, background_tasks)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="payment_reminder",
        entity_type="client_invoice",
        entity_id=invoice_id,
        **meta,
    )
    db.commit()
    return result


@admin_router.post("/invoices/{invoice_id}/push-zoho")
def admin_push_zoho_invoice(
    invoice_id: int,
    request: Request,
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    ensure_billing_write_access(user)
    try:
        result = client_billing_service.admin_push_zoho_invoice(db, invoice_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="push_zoho_invoice",
        entity_type="client_invoice",
        entity_id=invoice_id,
        new_value={"externalId": result.get("externalId"), "status": result.get("status")},
        **meta,
    )
    db.commit()
    return result


@admin_router.delete("/invoices/{invoice_id}/lines/{line_id}/late-fee")
def admin_remove_late_fee(
    invoice_id: int,
    line_id: int,
    request: Request,
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    ensure_billing_write_access(user)
    try:
        client_billing_service.admin_remove_late_fee_line(db, invoice_id, line_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="remove_late_fee",
        entity_type="client_invoice_line",
        entity_id=line_id,
        **meta,
    )
    db.commit()
    return {"status": "removed"}


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


@admin_router.post("/invoices/{invoice_id}/late-fee")
def admin_add_late_fee(
    invoice_id: int,
    request: Request,
    amount_inr: float = Query(..., gt=0),
    finance_note: Optional[str] = Query(None),
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    ensure_billing_write_access(user)
    try:
        line = client_billing_service.admin_add_late_fee_line(
            db, invoice_id, amount_inr, finance_note=finance_note
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="add_late_fee",
        entity_type="client_invoice_line",
        entity_id=line.id,
        **meta,
    )
    db.commit()
    return {"lineId": line.id, "amountInr": float(line.amount_inr)}


@admin_router.post("/payments/{payment_id}/confirm")
def admin_confirm_payment_claim(
    payment_id: int,
    request: Request,
    amount_inr: Optional[float] = Query(
        None,
        gt=0,
        description="Optional cap — confirm up to this amount (max claim, max collectible). "
        "Use when collectible dropped after parent submitted the claim.",
    ),
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    ensure_billing_write_access(user)
    try:
        result = client_billing_service.confirm_payment_claim(
            db, payment_id, user.id, confirm_amount_inr=amount_inr
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="confirm_payment", entity_type="client_payment", entity_id=payment_id, **meta)
    db.commit()
    return result


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
    resolution = (payload.resolution or "").strip()
    if payload.status.upper() == "REJECTED" and not resolution:
        raise HTTPException(status_code=400, detail="Rejection comment is required")
    try:
        client_billing_service.resolve_dispute(
            db, dispute_id, payload.status, resolution, payload.adjustment_inr
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="resolve_dispute", entity_type="billing_dispute", entity_id=dispute_id, **meta)
    db.commit()
    return {"status": payload.status.lower()}
