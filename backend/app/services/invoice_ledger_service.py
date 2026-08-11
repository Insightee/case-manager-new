"""Therapist statement ledger — enriched rows for filtering (year / month / client)."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.case import Case
from app.models.invoice import Invoice, InvoiceStatus
from app.models.invoice_line import InvoiceCaseLine


_MONTH_RE = re.compile(
    r"^(?:(?P<ym>\d{4})-(?P<mnum>\d{2})|(?P<mon>[A-Za-z]+)\s+(?P<year>\d{4}))$"
)


def _parse_period(month_label: str) -> tuple[Optional[int], Optional[str], Optional[str]]:
    """Return (year, month_key e.g. Jul, sort_key YYYY-MM)."""
    raw = (month_label or "").strip()
    if not raw:
        return None, None, None
    m = _MONTH_RE.match(raw)
    if not m:
        return None, None, None
    if m.group("ym"):
        year = int(m.group("ym"))
        month_num = int(m.group("mnum"))
        try:
            dt = datetime(year, month_num, 1)
            mon = dt.strftime("%b")
            return year, mon, dt.strftime("%Y-%m")
        except ValueError:
            return year, None, f"{year}-{m.group('mnum')}"
    year = int(m.group("year"))
    mon = m.group("mon")[:3].title()
    try:
        dt = datetime.strptime(f"{m.group('mon')} {year}", "%b %Y")
    except ValueError:
        try:
            dt = datetime.strptime(f"{m.group('mon')} {year}", "%B %Y")
        except ValueError:
            return year, mon, None
    return year, dt.strftime("%b"), dt.strftime("%Y-%m")


def _case_summaries(db: Session, invoice: Invoice) -> list[dict]:
    lines = list(invoice.case_lines or [])
    if not lines:
        return []
    case_ids = {cl.case_id for cl in lines}
    cases = {
        c.id: c
        for c in db.scalars(
            select(Case).where(Case.id.in_(case_ids)).options(selectinload(Case.child))
        ).all()
    }
    out: list[dict] = []
    seen: set[int] = set()
    for cl in lines:
        if cl.case_id in seen:
            continue
        seen.add(cl.case_id)
        case_row = cases.get(cl.case_id)
        child_name = None
        if case_row and case_row.child:
            child_name = case_row.child.full_name
        out.append(
            {
                "caseId": cl.case_id,
                "caseCode": cl.case_code,
                "childName": child_name,
                "therapistShareInr": float(cl.therapist_share_inr or 0),
                "sessionCount": int(cl.included_sessions or 0) + int(cl.additional_sessions or 0),
            }
        )
    out.sort(key=lambda x: (x.get("childName") or x.get("caseCode") or "").lower())
    return out


def _client_label(cases: list[dict]) -> str:
    if not cases:
        return "—"
    names = [c.get("childName") or c.get("caseCode") for c in cases if c.get("childName") or c.get("caseCode")]
    if not names:
        return "—"
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]}, {names[1]}"
    return f"{names[0]} +{len(names) - 1} more"


def therapist_ledger_row(db: Session, invoice: Invoice) -> dict:
    cases = _case_summaries(db, invoice)
    year, month_key, sort_key = _parse_period(invoice.month)
    gross = float(invoice.subtotal_inr if invoice.subtotal_inr is not None else invoice.amount_inr or 0)
    return {
        "id": invoice.id,
        "therapistUserId": invoice.therapist_user_id,
        "month": invoice.month,
        "periodYear": year,
        "periodMonth": month_key,
        "periodSortKey": sort_key,
        "amountInr": float(invoice.amount_inr or 0),
        "subtotalInr": gross,
        "leaveDeductionInr": float(invoice.leave_deduction_inr or 0) if invoice.leave_deduction_inr else None,
        "adjustmentInr": float(invoice.adjustment_inr or 0) if invoice.adjustment_inr else None,
        "paidAmountInr": float(invoice.paid_amount_inr) if invoice.paid_amount_inr is not None else None,
        "sessionsCount": int(invoice.sessions_count or 0),
        "status": invoice.status.value,
        "reviewerComment": invoice.reviewer_comment,
        "notes": invoice.notes,
        "createdAt": invoice.created_at.isoformat() if invoice.created_at else None,
        "cases": cases,
        "clientLabel": _client_label(cases),
        "caseCount": len(cases),
    }


def list_therapist_ledger(
    db: Session,
    therapist_user_id: int,
    *,
    year: Optional[int] = None,
    month: Optional[str] = None,
    case_id: Optional[int] = None,
    status: Optional[str] = None,
) -> list[dict]:
    stmt = (
        select(Invoice)
        .where(Invoice.therapist_user_id == therapist_user_id)
        .options(selectinload(Invoice.case_lines).selectinload(InvoiceCaseLine.session_lines))
        .order_by(Invoice.created_at.desc())
    )
    if year:
        stmt = stmt.where(Invoice.month.contains(str(year)))
    if month:
        stmt = stmt.where(Invoice.month.contains(month))
    if status:
        try:
            status_enum = InvoiceStatus(status.upper())
            stmt = stmt.where(Invoice.status == status_enum)
        except ValueError:
            stmt = stmt.where(Invoice.status == status)
    rows = list(db.scalars(stmt).all())
    ledger = [therapist_ledger_row(db, inv) for inv in rows]
    if case_id:
        ledger = [r for r in ledger if any(c.get("caseId") == case_id for c in r.get("cases") or [])]
    ledger.sort(
        key=lambda r: (r.get("periodSortKey") or "", r.get("createdAt") or ""),
        reverse=True,
    )
    return ledger


def ledger_summary(rows: list[dict]) -> dict:
    gross = sum(float(r.get("subtotalInr") or r.get("amountInr") or 0) for r in rows)
    net = sum(float(r.get("amountInr") or 0) for r in rows)
    paid = sum(
        float(r.get("paidAmountInr") or r.get("amountInr") or 0)
        for r in rows
        if str(r.get("status") or "").upper() == "PAID"
    )
    pending = sum(
        float(r.get("amountInr") or 0)
        for r in rows
        if str(r.get("status") or "").upper() in {"IN_REVIEW", "DRAFT", "APPROVED"}
    )
    sessions = sum(int(r.get("sessionsCount") or 0) for r in rows)
    return {
        "rowCount": len(rows),
        "sessionCount": sessions,
        "grossInr": round(gross, 2),
        "netInr": round(net, 2),
        "paidInr": round(paid, 2),
        "pendingInr": round(pending, 2),
    }


def ledger_filter_options(rows: list[dict]) -> dict:
    years: set[int] = set()
    months: set[str] = set()
    clients: dict[int, str] = {}
    statuses: set[str] = set()
    for r in rows:
        if r.get("periodYear"):
            years.add(int(r["periodYear"]))
        if r.get("periodMonth"):
            months.add(r["periodMonth"])
        statuses.add(str(r.get("status") or ""))
        for c in r.get("cases") or []:
            cid = c.get("caseId")
            label = c.get("childName") or c.get("caseCode")
            if cid and label:
                clients[int(cid)] = label
    month_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return {
        "years": sorted(years, reverse=True),
        "months": sorted(months, key=lambda m: month_order.index(m) if m in month_order else 99),
        "clients": [{"caseId": k, "label": v} for k, v in sorted(clients.items(), key=lambda x: x[1].lower())],
        "statuses": sorted(s for s in statuses if s),
    }


def therapist_ledger_payload(
    db: Session,
    therapist_user_id: int,
    *,
    year: Optional[int] = None,
    month: Optional[str] = None,
    case_id: Optional[int] = None,
    status: Optional[str] = None,
) -> dict:
    all_rows = list_therapist_ledger(db, therapist_user_id)
    filtered = list_therapist_ledger(
        db,
        therapist_user_id,
        year=year,
        month=month,
        case_id=case_id,
        status=status,
    )
    return {
        "rows": filtered,
        "filters": ledger_filter_options(all_rows),
        "summary": ledger_summary(filtered),
    }
