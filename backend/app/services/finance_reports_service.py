"""Computed finance reports (read-only, no report tables)."""
from __future__ import annotations

import csv
import io
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.case import Case
from app.models.client_billing import (
    ClientInvoice,
    ClientInvoiceLine,
    ClientInvoiceStatus,
    ClientPayment,
)
from app.models.invoice import Invoice, InvoiceStatus
from app.models.invoice_manual_line import InvoiceManualLine
from app.models.ledger_billing import BillableStatus, BillingLedger
from app.models.user import User
from app.services import billing_composer_service, client_billing_service


REPORT_KEYS = frozenset(
    {
        "monthly-billing",
        "outstanding",
        "collections",
        "therapist-payouts",
        "pending-payout-approvals",
        "ledger-missing",
        "manual-adjustments",
        "revenue-by-service",
        "margin-by-case",
    }
)


def _ym(month: str | None) -> str:
    return billing_composer_service.normalize_billing_month(month or date.today().strftime("%Y-%m"))


def report_rows(db: Session, report_key: str, *, billing_month: str | None = None) -> list[dict]:
    if report_key not in REPORT_KEYS:
        raise ValueError(f"Unknown report: {report_key}")
    ym = _ym(billing_month)

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
        rows = db.scalars(
            select(ClientInvoice).where(
                ClientInvoice.status.in_(
                    [
                        ClientInvoiceStatus.SENT,
                        ClientInvoiceStatus.GENERATED,
                        ClientInvoiceStatus.PARTIALLY_PAID,
                        ClientInvoiceStatus.OVERDUE,
                    ]
                )
            )
        ).all()
        return [
            {
                "invoiceId": r.id,
                "invoiceNumber": r.invoice_number,
                "caseId": r.case_id,
                "billingMonth": r.billing_month,
                "status": r.status.value if r.status else "",
                "totalInr": float(r.total_inr or 0),
                "balanceInr": float(r.total_inr or 0) - float(r.amount_paid_inr or 0),
            }
            for r in rows
        ]

    if report_key == "collections":
        rows = db.scalars(select(ClientPayment).order_by(ClientPayment.id.desc()).limit(500)).all()
        return [
            {
                "paymentId": r.id,
                "invoiceId": r.client_invoice_id,
                "amountInr": float(r.amount_inr or 0),
                "status": r.status.value if r.status else "",
                "paidAt": r.paid_at.isoformat() if r.paid_at else "",
            }
            for r in rows
        ]

    if report_key == "therapist-payouts":
        rows = db.scalars(select(Invoice).order_by(Invoice.id.desc()).limit(500)).all()
        return [
            {
                "invoiceId": r.id,
                "therapistUserId": r.therapist_user_id,
                "month": r.month,
                "status": r.status.value if r.status else "",
                "amountInr": float(r.amount_inr or 0),
            }
            for r in rows
        ]

    if report_key == "pending-payout-approvals":
        rows = db.scalars(
            select(Invoice).where(Invoice.status == InvoiceStatus.IN_REVIEW).order_by(Invoice.id)
        ).all()
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
        cases = billing_composer_service.list_composer_cases(
            db, billing_month=ym, queue="not_invoiced_this_month", limit=200
        )
        out = []
        for c in cases:
            if (c.get("ledgerReadyCount") or 0) == 0 and (c.get("sessionsCompletedThisMonth") or 0) > 0:
                out.append(
                    {
                        "caseId": c["caseId"],
                        "caseCode": c.get("caseCode"),
                        "childName": c.get("childName"),
                        "sessionsCompleted": c.get("sessionsCompletedThisMonth"),
                        "billingMonth": ym,
                    }
                )
        return out

    if report_key == "manual-adjustments":
        client_lines = db.scalars(
            select(ClientInvoiceLine).where(
                ClientInvoiceLine.line_item_type.in_(["MANUAL_FEE", "DISCOUNT", "TAX", "OTHER"])
            ).limit(300)
        ).all()
        therapist_lines = db.scalars(select(InvoiceManualLine).limit(300)).all()
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
        from app.models.case import CaseStatus
        from app.services import billing_ledger_service

        case_ids = db.scalars(
            select(Case.id).where(Case.status == CaseStatus.ACTIVE).limit(100)
        ).all()
        out = []
        for cid in case_ids:
            rec = billing_ledger_service.reconcile_month(db, case_id=cid, billing_month=ym)
            out.append(
                {
                    "caseId": rec["caseId"],
                    "clientTotalInr": rec["ledgerBillableTotalInr"],
                    "therapistTotalInr": rec["therapistPayoutTotalInr"],
                    "marginInr": rec["marginInr"],
                    "sessionCount": rec["sessionCount"],
                }
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
