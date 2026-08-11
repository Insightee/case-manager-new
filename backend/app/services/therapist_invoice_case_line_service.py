"""Ensure therapist invoice case lines exist for finance corrections and payout ladder."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.invoice import Invoice, InvoiceStatus
from app.models.invoice_line import InvoiceCaseLine
from app.services import billing_composer_service


def _active_therapist_user_id(db: Session, case_id: int) -> int | None:
    row = db.scalars(
        select(CaseAssignment)
        .where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
        .order_by(CaseAssignment.start_date.desc())
        .limit(1)
    ).first()
    return row.therapist_user_id if row else None


def find_therapist_invoice_case_line(
    db: Session, *, case_id: int, billing_month: str
) -> tuple[Invoice | None, InvoiceCaseLine | None]:
    ym = billing_composer_service.normalize_billing_month(billing_month)
    row = db.scalars(
        select(InvoiceCaseLine)
        .join(Invoice, InvoiceCaseLine.invoice_id == Invoice.id)
        .where(InvoiceCaseLine.case_id == case_id, Invoice.month == ym)
        .order_by(Invoice.id.desc())
        .limit(1)
    ).first()
    if not row:
        return None, None
    inv = db.get(Invoice, row.invoice_id)
    return inv, row


def resolve_case_payout_gross_inr(
    db: Session,
    *,
    case_id: int,
    billing_month: str,
    therapist_user_id: int | None = None,
) -> float:
    """Gross therapist share for case-month from therapist invoice case line."""
    _, case_line = find_therapist_invoice_case_line(db, case_id=case_id, billing_month=billing_month)
    if case_line and case_line.therapist_share_inr is not None:
        return round(float(case_line.therapist_share_inr), 2)
    return 0.0


def ensure_therapist_invoice_case_line(
    db: Session,
    *,
    case: Case,
    billing_month: str,
    payout_inr: float,
    therapist_user_id: int | None = None,
) -> tuple[Invoice, InvoiceCaseLine]:
    """Create therapist invoice + case line when client correction needs linked payout."""
    ym = billing_composer_service.normalize_billing_month(billing_month)
    therapist_id = therapist_user_id or _active_therapist_user_id(db, case.id)
    if not therapist_id:
        raise ValueError("No active therapist assignment for this case — cannot create payout line")

    inv, case_line = find_therapist_invoice_case_line(db, case_id=case.id, billing_month=ym)
    payout = round(float(payout_inr), 2)

    if case_line and inv:
        return inv, case_line

    if inv is None:
        inv = db.scalars(
            select(Invoice)
            .where(Invoice.therapist_user_id == therapist_id, Invoice.month == ym)
            .order_by(Invoice.id.desc())
            .limit(1)
        ).first()

    if inv is None:
        inv = Invoice(
            therapist_user_id=therapist_id,
            month=ym,
            amount_inr=payout,
            subtotal_inr=payout,
            status=InvoiceStatus.IN_REVIEW,
            sessions_count=1,
            notes="[Finance correction] Therapist statement created for linked payout edit",
        )
        db.add(inv)
        db.flush()

    billing_type = case.billing_type.value if case.billing_type else "PER_SESSION"
    case_line = InvoiceCaseLine(
        invoice_id=inv.id,
        case_id=case.id,
        case_code=case.case_code or f"C-{case.id}",
        billing_type=billing_type,
        included_sessions=1,
        therapist_share_inr=payout,
        billing_snapshot={"source": "finance_correction_ensure"},
    )
    db.add(case_line)
    db.flush()

    all_lines = db.scalars(select(InvoiceCaseLine).where(InvoiceCaseLine.invoice_id == inv.id)).all()
    inv.amount_inr = round(sum(float(cl.therapist_share_inr or 0) for cl in all_lines), 2)
    inv.subtotal_inr = inv.amount_inr
    db.flush()
    return inv, case_line
