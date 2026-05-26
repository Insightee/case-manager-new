from __future__ import annotations

import secrets
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.case import Case
from app.models.client_billing import (
    ClientInvoice,
    ClientInvoiceLine,
    ClientInvoiceStatus,
    ClientInvoiceType,
)
from app.models.daily_log import DailyLog
from app.models.ledger_billing import BillableStatus, BillingLedger, ProductBillingModel
from app.models.session import Session as TherapySession
from app.models.user import User
from app.services import billing_ledger_service, product_billing_rule_service


def _invoice_number() -> str:
    return f"CI-{secrets.token_hex(4).upper()}"


def generate_draft_from_ledger(
    db: Session,
    *,
    case_id: int,
    billing_month: str,
    actor_user_id: int,
    include_pending: bool = False,
) -> dict:
    if not getattr(settings, "billing_ledger_drafts", True):
        raise ValueError("Ledger draft generation is disabled")

    case = db.get(Case, case_id)
    if not case:
        raise ValueError("Case not found")

    statuses = [BillableStatus.BILLABLE]
    if include_pending:
        statuses.append(BillableStatus.PENDING_REVIEW)

    rows = db.scalars(
        select(BillingLedger)
        .where(
            BillingLedger.case_id == case_id,
            BillingLedger.ledger_month == billing_month,
            BillingLedger.billable_status.in_(statuses),
            BillingLedger.client_invoice_id.is_(None),
        )
        .order_by(BillingLedger.event_date)
    ).all()
    if not rows:
        raise ValueError("No billable ledger rows for this case and month")

    rule = None
    if case.product_billing_rule_id:
        rule = product_billing_rule_service.get_rule(db, case.product_billing_rule_id)

    inv_type = ClientInvoiceType.POSTPAID
    if rule:
        if rule.billing_model == ProductBillingModel.MONTHLY_FIXED:
            inv_type = ClientInvoiceType.MONTHLY_FIXED
        elif rule.billing_model == ProductBillingModel.PREPAID_PACKAGE:
            inv_type = ClientInvoiceType.PREPAID

    parent_id = rows[0].parent_user_id or billing_ledger_service._parent_for_case(db, case)
    if not parent_id:
        raise ValueError("No parent linked to case")

    subtotal = sum(float(r.amount_inr) for r in rows)
    tax = sum(float(r.gst_amount_inr or 0) for r in rows)
    total = sum(float(r.total_inr) for r in rows)

    inv = ClientInvoice(
        invoice_number=_invoice_number(),
        parent_user_id=parent_id,
        case_id=case_id,
        invoice_type=inv_type,
        status=ClientInvoiceStatus.DRAFT,
        billing_month=billing_month,
        service_type=case.service_type,
        product_module=case.product_module,
        subtotal_inr=subtotal,
        tax_inr=tax,
        total_inr=total,
        amount_paid_inr=0,
        approved_by_user_id=actor_user_id,
    )
    db.add(inv)
    db.flush()

    sort = 0
    for row in rows:
        session = db.get(TherapySession, row.session_id) if row.session_id else None
        therapist_name = "—"
        if row.therapist_user_id:
            u = db.get(User, row.therapist_user_id)
            therapist_name = u.full_name if u and u.full_name else f"User {row.therapist_user_id}"
        status_label = row.event_type.value.replace("_", " ").title()
        line = ClientInvoiceLine(
            client_invoice_id=inv.id,
            session_id=row.session_id,
            daily_log_id=row.daily_log_id,
            session_date=row.event_date,
            therapist_name=therapist_name,
            service_label=case.service_type,
            session_status=status_label,
            amount_inr=float(row.total_inr),
            billing_ledger_id=row.id,
            gst_rate_percent=row.gst_rate_percent,
            gst_amount_inr=row.gst_amount_inr,
            hsn_sac_code=row.hsn_sac_code,
            taxable_amount_inr=row.amount_inr,
            sort_order=sort,
        )
        sort += 1
        db.add(line)
        row.billable_status = BillableStatus.INVOICED
        row.client_invoice_id = inv.id

    db.flush()
    return {
        "id": inv.id,
        "invoiceNumber": inv.invoice_number,
        "status": inv.status.value.lower(),
        "lineCount": sort,
        "totalInr": float(inv.total_inr),
    }
