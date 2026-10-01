"""Computed finance reports (read-only, no report tables)."""
from __future__ import annotations

import csv
import io
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.billing_month import (
    ist_month_utc_bounds,
    month_date_bounds,
    parse_billing_month,
    therapist_invoice_month_keys,
)
from app.models.case import Case
from app.models.client_billing import (
    ClientInvoice,
    ClientInvoiceLine,
    ClientInvoiceStatus,
    ClientPayment,
    ClientPaymentStatus,
)
from app.models.invoice import Invoice, InvoiceStatus
from app.models.invoice_manual_line import InvoiceManualLine
from app.models.ledger_billing import BillableStatus, BillingLedger
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.user import User
from app.services import billing_composer_service, client_billing_service, finance_payout_preview_service


REPORT_LABELS: dict[str, str] = {
    "monthly-billing": "Monthly billing",
    "outstanding": "Outstanding balances",
    "collections": "Collections",
    "therapist-payouts": "Therapist payouts",
    "therapist-payout-preview": "Therapist payout preview",
    "pending-payout-approvals": "Pending payout approvals",
    "ledger-missing": "Ledger missing",
    "manual-adjustments": "Manual adjustments",
    "revenue-by-service": "Revenue by service",
    "margin-by-case": "Margin by case",
}


REPORT_KEYS = frozenset(REPORT_LABELS.keys())


def _ym(month: str | None) -> str:
    return parse_billing_month(month)


def report_rows(
    db: Session,
    report_key: str,
    *,
    billing_month: str | None = None,
    user=None,
    product_module: str | None = None,
    case_id: int | None = None,
    therapist_user_id: int | None = None,
    date_basis: str | None = None,
) -> list[dict]:
    if report_key not in REPORT_KEYS:
        raise ValueError(f"Unknown report: {report_key}")
    ym = _ym(billing_month)
    month_keys = therapist_invoice_month_keys(ym)

    if report_key == "monthly-billing":
        rows = db.scalars(
            select(ClientInvoice)
            .where(ClientInvoice.billing_month == ym)
            .order_by(ClientInvoice.id.desc())
        ).all()
        return [
            {
                "invoiceId": r.id,
                "invoiceNumber": r.invoice_number,
                "caseId": r.case_id,
                "billingMonth": r.billing_month,
                "status": r.status.value if r.status else "",
                "totalInr": float(r.total_inr or 0),
                "serviceType": r.service_type or "",
            }
            for r in rows
        ]

    if report_key == "outstanding":
        open_statuses = [
            ClientInvoiceStatus.SENT,
            ClientInvoiceStatus.GENERATED,
            ClientInvoiceStatus.ISSUED,
            ClientInvoiceStatus.PARTIALLY_PAID,
            ClientInvoiceStatus.OVERDUE,
        ]
        stmt = select(ClientInvoice).where(ClientInvoice.status.in_(open_statuses))
        if billing_month:
            stmt = stmt.where(ClientInvoice.billing_month == ym)
        rows = db.scalars(stmt.order_by(ClientInvoice.id.desc())).all()
        return [
            {
                "invoiceId": r.id,
                "invoiceNumber": r.invoice_number,
                "caseId": r.case_id,
                "billingMonth": r.billing_month,
                "status": r.status.value if r.status else "",
                "totalInr": float(r.total_inr or 0),
                "balanceInr": float(r.total_inr or 0) - float(r.amount_paid_inr or 0),
                "dueDate": r.due_date.isoformat() if r.due_date else "",
                "dateBasis": "current_snapshot_for_invoice_month" if billing_month else "current_snapshot",
            }
            for r in rows
        ]

    if report_key == "collections":
        basis = (date_basis or "cash_period").strip().lower()
        stmt = (
            select(ClientPayment, ClientInvoice)
            .join(ClientInvoice, ClientPayment.client_invoice_id == ClientInvoice.id)
            .order_by(ClientPayment.id.desc())
        )
        if basis == "invoice_cohort":
            stmt = stmt.where(ClientInvoice.billing_month == ym)
        else:
            start_utc, end_utc = ist_month_utc_bounds(ym)
            stmt = stmt.where(ClientPayment.paid_at >= start_utc, ClientPayment.paid_at < end_utc)
        pairs = db.execute(stmt).all()
        return [
            {
                "paymentId": pay.id,
                "invoiceId": pay.client_invoice_id,
                "invoiceNumber": inv.invoice_number if inv else "",
                "caseId": inv.case_id if inv else None,
                "invoiceBillingMonth": inv.billing_month if inv else "",
                "amountInr": float(pay.amount_inr or 0),
                "paymentStatus": pay.payment_status.value if pay.payment_status else "",
                "paidAt": pay.paid_at.isoformat() if pay.paid_at else "",
                "confirmedAt": pay.confirmed_at.isoformat() if pay.confirmed_at else "",
                "method": pay.method.value if pay.method else "",
                "reference": pay.reference or "",
                "dateBasis": "invoice_cohort" if basis == "invoice_cohort" else "cash_period",
            }
            for pay, inv in pairs
        ]

    if report_key == "therapist-payouts":
        rows = db.scalars(
            select(Invoice).where(Invoice.month.in_(month_keys)).order_by(Invoice.id.desc())
        ).all()
        return [
            {
                "invoiceId": r.id,
                "therapistUserId": r.therapist_user_id,
                "month": r.month,
                "status": r.status.value if r.status else "",
                "amountInr": float(r.amount_inr or 0),
                "paidAmountInr": float(r.paid_amount_inr or 0),
            }
            for r in rows
        ]

    if report_key == "therapist-payout-preview":
        from app.services import billing_period_snapshot_service

        frozen = billing_period_snapshot_service.get_closed_payout_preview_rows(db, ym)
        if frozen is not None:
            rows = finance_payout_preview_service.apply_therapist_total_column(frozen)
        else:
            rows = finance_payout_preview_service.payout_preview_rows(
                db,
                ym,
                user=user,
                product_module=product_module,
                case_id=case_id,
                therapist_user_id=therapist_user_id,
            )
        if case_id:
            rows = [r for r in rows if int(r.get("caseId") or 0) == int(case_id)]
        return rows

    if report_key == "pending-payout-approvals":
        stmt = select(Invoice).where(Invoice.status == InvoiceStatus.IN_REVIEW)
        if billing_month:
            stmt = stmt.where(Invoice.month.in_(month_keys))
        rows = db.scalars(stmt.order_by(Invoice.id)).all()
        return [
            {
                "invoiceId": r.id,
                "therapistUserId": r.therapist_user_id,
                "month": r.month,
                "amountInr": float(r.amount_inr or 0),
            }
            for r in rows
        ]

    if report_key == "ledger-missing":
        start, end = month_date_bounds(ym)
        completed = {
            int(cid): int(n)
            for cid, n in db.execute(
                select(TherapySession.case_id, func.count(TherapySession.id))
                .where(
                    TherapySession.status == SessionStatus.COMPLETED,
                    TherapySession.scheduled_date >= start,
                    TherapySession.scheduled_date <= end,
                )
                .group_by(TherapySession.case_id)
            ).all()
        }
        ledger_cases = set(
            db.scalars(select(BillingLedger.case_id).where(BillingLedger.ledger_month == ym)).all()
        )
        out = []
        for cid, sessions_completed in completed.items():
            if cid in ledger_cases:
                continue
            case = db.get(Case, cid)
            out.append(
                {
                    "caseId": cid,
                    "caseCode": case.case_code if case else "",
                    "childName": "",
                    "sessionsCompleted": sessions_completed,
                    "billingMonth": ym,
                }
            )
        return out

    if report_key == "manual-adjustments":
        client_stmt = (
            select(ClientInvoiceLine)
            .join(ClientInvoice, ClientInvoiceLine.client_invoice_id == ClientInvoice.id)
            .where(ClientInvoiceLine.line_item_type.in_(["MANUAL_FEE", "DISCOUNT", "TAX", "OTHER"]))
        )
        therapist_stmt = select(InvoiceManualLine).join(Invoice, InvoiceManualLine.invoice_id == Invoice.id)
        if billing_month:
            client_stmt = client_stmt.where(ClientInvoice.billing_month == ym)
            therapist_stmt = therapist_stmt.where(Invoice.month.in_(month_keys))
        client_lines = db.scalars(client_stmt).all()
        therapist_lines = db.scalars(therapist_stmt).all()
        rows = []
        for ln in client_lines:
            rows.append(
                {
                    "source": "client",
                    "lineId": ln.id,
                    "invoiceId": ln.client_invoice_id,
                    "amountInr": float(ln.amount_inr or 0),
                    "type": ln.line_item_type or "",
                }
            )
        for ln in therapist_lines:
            rows.append(
                {
                    "source": "therapist",
                    "lineId": ln.id,
                    "invoiceId": ln.invoice_id,
                    "amountInr": float(ln.amount_inr or 0),
                    "type": "manual_line",
                }
            )
        return rows

    if report_key == "revenue-by-service":
        rows = db.execute(
            select(
                ClientInvoice.service_type,
                func.count(ClientInvoice.id),
                func.coalesce(func.sum(ClientInvoice.total_inr), 0),
            )
            .where(ClientInvoice.billing_month == ym)
            .group_by(ClientInvoice.service_type)
        ).all()
        return [
            {
                "serviceType": r[0] or "unknown",
                "invoiceCount": int(r[1] or 0),
                "totalInr": float(r[2] or 0),
            }
            for r in rows
        ]

    if report_key == "margin-by-case":
        from app.services import billing_period_snapshot_service

        frozen = billing_period_snapshot_service.margin_rows_from_case_snapshots(db, ym)
        if frozen is not None:
            return frozen

        from app.services import billing_ledger_service

        ledger_ids = set(
            db.scalars(select(BillingLedger.case_id).where(BillingLedger.ledger_month == ym)).all()
        )
        invoice_ids = set(
            db.scalars(select(ClientInvoice.case_id).where(ClientInvoice.billing_month == ym)).all()
        )
        case_ids = sorted(ledger_ids | invoice_ids)
        out = []
        for cid in case_ids:
            rec = billing_ledger_service.reconcile_month(db, case_id=cid, billing_month=ym)
            out.append(
                billing_period_snapshot_service.enrich_margin_row(
                    {
                        "caseId": rec["caseId"],
                        "clientTotalInr": rec["ledgerBillableTotalInr"],
                        "therapistTotalInr": rec["therapistPayoutTotalInr"],
                        "marginInr": rec["marginInr"],
                        "sessionCount": rec["sessionCount"],
                    }
                )
            )
        return out

    return []


def report_csv(report_key: str, rows: list[dict]) -> str:
    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def report_title(report_key: str) -> str:
    return REPORT_LABELS.get(report_key, report_key.replace("-", " ").title())


def report_subtitle(report_key: str, *, billing_month: str | None) -> str:
    ym = _ym(billing_month)
    base = f"Billing month {ym}"
    return base
