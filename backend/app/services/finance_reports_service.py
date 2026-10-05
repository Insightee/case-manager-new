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
    "client-invoice-vs-calculation": "Client invoice vs calculation",
    "therapist-invoice-vs-calculation": "Therapist invoice vs calculation",
}


REPORT_KEYS = frozenset(REPORT_LABELS.keys())


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

    if report_key == "therapist-payout-preview":
        from app.services import billing_period_snapshot_service

        frozen = billing_period_snapshot_service.get_closed_payout_preview_rows(db, ym)
        if frozen is not None:
            return finance_payout_preview_service.apply_therapist_total_column(frozen)
        return finance_payout_preview_service.payout_preview_rows(db, ym)

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
        from app.services import billing_period_snapshot_service

        frozen = billing_period_snapshot_service.margin_rows_from_case_snapshots(db, ym)
        if frozen is not None:
            return frozen

        from app.models.case import CaseStatus
        from app.services import billing_ledger_service

        case_ids = db.scalars(
            select(Case.id).where(Case.status == CaseStatus.ACTIVE).limit(100)
        ).all()
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

    if report_key == "client-invoice-vs-calculation":
        return client_invoice_vs_calculation_rows(db, ym)

    if report_key == "therapist-invoice-vs-calculation":
        return therapist_invoice_vs_calculation_rows(db, ym)

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


def _money(value) -> float:
    if value in (None, ""):
        return 0.0
    return round(float(value), 2)


def client_invoice_vs_calculation_rows(db: Session, ym: str) -> list[dict]:
    """Client invoice submitted for the month against the finance calculation, one row per case."""
    preview = finance_payout_preview_service.payout_preview_rows(db, ym)
    by_case: dict[int, dict] = {}
    for row in preview:
        cid = row.get("caseId")
        if cid is None:
            continue
        bucket = by_case.setdefault(
            int(cid),
            {
                "caseId": int(cid),
                "Case ID": row.get("Case ID") or "",
                "Client Name": row.get("Client Name") or "",
                "Service Type": row.get("Service Type") or "",
                "Case Status": row.get("Case Status") or "",
                "Calculated Client (INR)": 0.0,
            },
        )
        bucket["Calculated Client (INR)"] = round(
            bucket["Calculated Client (INR)"] + _money(row.get("Calculated Client (INR)")),
            2,
        )

    invoices = db.scalars(select(ClientInvoice).where(ClientInvoice.billing_month == ym)).all()
    invoices_by_case: dict[int, list] = {}
    for inv in invoices:
        invoices_by_case.setdefault(int(inv.case_id), []).append(inv)

    rows: list[dict] = []
    seen: set[int] = set()
    for cid, bucket in by_case.items():
        seen.add(cid)
        invs = invoices_by_case.get(cid, [])
        submitted = round(sum(float(inv.total_inr or 0) for inv in invs), 2)
        calculated = bucket["Calculated Client (INR)"]
        rows.append(
            {
                **bucket,
                "Invoice Count": len(invs),
                "Invoice Numbers": ", ".join(inv.invoice_number for inv in invs),
                "Invoice Status": ", ".join(inv.status.value if inv.status else "" for inv in invs),
                "Submitted (INR)": submitted,
                "Difference (Submitted − Calculated)": round(submitted - calculated, 2),
            }
        )
    for cid, invs in invoices_by_case.items():
        if cid in seen:
            continue
        submitted = round(sum(float(inv.total_inr or 0) for inv in invs), 2)
        rows.append(
            {
                "caseId": cid,
                "Case ID": "",
                "Client Name": "",
                "Service Type": invs[0].service_type or "",
                "Case Status": "",
                "Calculated Client (INR)": 0.0,
                "Invoice Count": len(invs),
                "Invoice Numbers": ", ".join(inv.invoice_number for inv in invs),
                "Invoice Status": ", ".join(inv.status.value if inv.status else "" for inv in invs),
                "Submitted (INR)": submitted,
                "Difference (Submitted − Calculated)": submitted,
            }
        )
    rows.sort(key=lambda r: (r.get("Client Name") or "", r.get("Case ID") or ""))
    return rows


def therapist_invoice_vs_calculation_rows(db: Session, ym: str) -> list[dict]:
    """Therapist payout invoice submitted for the month against the finance calculation."""
    from app.services.invoice_billing_service import parse_month

    _year, _month, label = parse_month(ym)
    preview = finance_payout_preview_service.payout_preview_rows(db, ym)
    by_therapist: dict[int, dict] = {}
    for row in preview:
        tid = row.get("therapistUserId")
        if tid is None:
            continue
        bucket = by_therapist.setdefault(
            int(tid),
            {
                "therapistUserId": int(tid),
                "Therapist ID": row.get("Therapist ID") or "",
                "Therapist Name": row.get("Therapist Name") or "",
                "Case Count": 0,
                "Logged Sessions": 0,
                "Child Absence": 0,
                "Leave taken": 0,
                "Calculated Therapist (INR)": 0.0,
            },
        )
        bucket["Case Count"] += 1
        bucket["Logged Sessions"] += int(row.get("Logged Sessions") or 0)
        bucket["Child Absence"] += int(row.get("Child Absence") or 0)
        bucket["Leave taken"] += int(row.get("Leave taken") or 0)
        bucket["Calculated Therapist (INR)"] = round(
            bucket["Calculated Therapist (INR)"] + _money(row.get("Predicted Total")),
            2,
        )

    invoices = db.scalars(select(Invoice).where(Invoice.month.in_([label, ym]))).all()
    invoices_by_therapist: dict[int, list] = {}
    for inv in invoices:
        invoices_by_therapist.setdefault(int(inv.therapist_user_id), []).append(inv)

    rows: list[dict] = []
    seen: set[int] = set()
    for tid, bucket in by_therapist.items():
        seen.add(tid)
        invs = invoices_by_therapist.get(tid, [])
        submitted = round(sum(float(inv.amount_inr or 0) for inv in invs), 2)
        calculated = bucket["Calculated Therapist (INR)"]
        rows.append(
            {
                **bucket,
                "Invoice Count": len(invs),
                "Invoice Status": ", ".join(inv.status.value if inv.status else "" for inv in invs),
                "Submitted (INR)": submitted,
                "Difference (Submitted − Calculated)": round(submitted - calculated, 2),
            }
        )
    for tid, invs in invoices_by_therapist.items():
        if tid in seen:
            continue
        submitted = round(sum(float(inv.amount_inr or 0) for inv in invs), 2)
        rows.append(
            {
                "therapistUserId": tid,
                "Therapist ID": "",
                "Therapist Name": "",
                "Case Count": 0,
                "Logged Sessions": 0,
                "Child Absence": 0,
                "Leave taken": 0,
                "Calculated Therapist (INR)": 0.0,
                "Invoice Count": len(invs),
                "Invoice Status": ", ".join(inv.status.value if inv.status else "" for inv in invs),
                "Submitted (INR)": submitted,
                "Difference (Submitted − Calculated)": submitted,
            }
        )
    rows.sort(key=lambda r: (r.get("Therapist Name") or "", str(r.get("Therapist ID") or "")))
    return rows
