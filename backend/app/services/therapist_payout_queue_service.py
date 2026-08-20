"""Finance therapist payout queue — composed read, engine SSOT for amounts."""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceStatus
from app.models.therapist_payout_settlement import TherapistPayoutTransfer
from app.models.therapist_statement_dispute import TherapistStatementDispute
from app.models.user import User
from app.services import (
    invoice_billing_service,
    payout_settlement_service,
    statement_dispute_service,
    therapist_payout_flag_service,
)
from app.services.invoice_billing_service import parse_month

_OPEN_DISPUTE_STATUSES = {"OPEN", "UNDER_REVIEW"}
_QUEUE_STATUSES = (
    InvoiceStatus.IN_REVIEW,
    InvoiceStatus.QUERIED,
    InvoiceStatus.APPROVED,
)


def _session_amount_map(breakdown: dict | None) -> dict[int, float]:
    out: dict[int, float] = {}
    if not breakdown:
        return out
    for case in breakdown.get("cases") or []:
        for line in case.get("session_lines") or []:
            if not line.get("included"):
                continue
            sid = line.get("session_id")
            if sid is None:
                continue
            out[int(sid)] = float(line.get("amount_inr") or 0)
    return out


def _compute_statement_balances(
    *,
    net_inr: float,
    disputed_session_ids: list[int],
    session_map: dict[int, float],
) -> dict:
    """Mirror client-side hold math: contested lines hold only their own amount."""
    contested = 0.0
    needs_review = False
    for sid in disputed_session_ids:
        amount = session_map.get(int(sid))
        if amount is None:
            needs_review = True
            continue
        contested += amount
    contested = round(contested, 2)
    if needs_review:
        return {
            "contestedInr": contested,
            "payableNowInr": None,
            "needsReview": True,
        }
    payable = max(0.0, round(net_inr - contested, 2))
    return {
        "contestedInr": contested,
        "payableNowInr": payable,
        "needsReview": False,
    }


def _open_disputes_for_invoice(
    disputes: list[TherapistStatementDispute],
    invoice_id: int | None,
    month: str,
    therapist_user_id: int,
) -> list[TherapistStatementDispute]:
    out: list[TherapistStatementDispute] = []
    for d in disputes:
        if d.status not in _OPEN_DISPUTE_STATUSES:
            continue
        if d.therapist_user_id != therapist_user_id or d.month != month:
            continue
        if invoice_id is not None and d.invoice_id not in (None, invoice_id):
            continue
        out.append(d)
    return out


def _latest_transfer_for_invoice(db: Session, invoice_id: int) -> TherapistPayoutTransfer | None:
    return db.scalar(
        select(TherapistPayoutTransfer)
        .where(TherapistPayoutTransfer.invoice_id == invoice_id)
        .order_by(TherapistPayoutTransfer.id.desc())
        .limit(1)
    )


def _statement_row(
    db: Session,
    invoice: Invoice,
    therapist: User | None,
    open_disputes: list[TherapistStatementDispute],
    therapist_payout_flagged: bool = False,
) -> dict:
    breakdown = invoice_billing_service.invoice_breakdown(db, invoice.id)
    session_map = _session_amount_map(breakdown)
    cases = breakdown.get("cases") or [] if breakdown else []
    sessions = int(breakdown.get("sessions_count") or invoice.sessions_count or 0) if breakdown else int(invoice.sessions_count or 0)

    settlement = payout_settlement_service.compute_invoice_settlement(db, invoice)
    gross = settlement["grossInr"]
    deductions = settlement["deductionsInr"]
    net = settlement["netInr"]
    tds_pending = bool(settlement.get("tdsPending"))
    tds_inr = settlement.get("tdsInr")
    tds_rate = settlement.get("tdsRatePercent")
    problem_blocked = bool(settlement.get("blocked"))
    export_blocked = bool(settlement.get("exportBlocked"))
    blocked_reason = settlement.get("blockedReason")

    held_ids: list[int] = []
    for d in open_disputes:
        held_ids.extend(int(x) for x in (d.disputed_session_ids or []))
    held_ids = list(dict.fromkeys(held_ids))

    balances = _compute_statement_balances(
        net_inr=net,
        disputed_session_ids=held_ids,
        session_map=session_map,
    )

    dispute_payloads = [statement_dispute_service.dispute_dict(d) for d in open_disputes]
    xfer = _latest_transfer_for_invoice(db, invoice.id)

    return {
        "invoiceId": invoice.id,
        "therapistUserId": invoice.therapist_user_id,
        "therapistName": (therapist.full_name if therapist else None) or f"Therapist #{invoice.therapist_user_id}",
        "month": invoice.month,
        "caseCount": len(cases),
        "sessionCount": sessions,
        "grossInr": round(gross, 2),
        "deductionsInr": round(deductions, 2),
        "tdsInr": None if tds_pending else (round(tds_inr, 2) if tds_inr is not None else None),
        "tdsPending": tds_pending,
        "tdsRatePercent": None if tds_pending else tds_rate,
        "tdsNote": None if tds_pending else (f"TDS {tds_rate}%" if tds_rate is not None else None),
        "holdbackInr": None,
        "holdbackNote": "Not yet configured",
        "expectedPaymentDate": None,
        "expectedPaymentDateNote": "Not yet configured",
        "netInr": round(net, 2),
        "status": invoice.status.value,
        "payableNowInr": balances["payableNowInr"],
        "contestedInr": balances["contestedInr"],
        "needsReview": bool(balances["needsReview"] or dispute_payloads or invoice.status == InvoiceStatus.QUERIED or problem_blocked),
        "blocked": problem_blocked,
        "exportBlocked": export_blocked,
        "blockedReason": blocked_reason,
        "exportBatchStatus": xfer.status if xfer else None,
        "exportTransferId": xfer.id if xfer else None,
        "exportBatchId": xfer.batch_id if xfer else None,
        "disputes": dispute_payloads,
        "hasOpenDispute": bool(dispute_payloads),
        "therapistPayoutFlagged": therapist_payout_flagged,
    }


def _month_filter_aliases(month: str) -> set[str]:
    raw = (month or "").strip()
    aliases = {raw}
    try:
        year, month_num, label = parse_month(raw)
        aliases.add(label)
        aliases.add(f"{year:04d}-{month_num:02d}")
        aliases.add(date(year, month_num, 1).strftime("%B %Y"))
    except ValueError:
        pass
    return {a for a in aliases if a}


def admin_payout_queue_summary(
    db: Session,
    *,
    month: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
) -> dict:
    stmt = select(Invoice).where(Invoice.status.in_(_QUEUE_STATUSES)).order_by(Invoice.created_at.desc())
    if status and status.upper() != "ALL":
        try:
            stmt = stmt.where(Invoice.status == InvoiceStatus(status.upper()))
        except ValueError:
            pass
    invoices = list(db.scalars(stmt).all())
    if month:
        aliases = _month_filter_aliases(month)
        invoices = [i for i in invoices if (i.month or "").strip() in aliases]

    therapist_ids = {i.therapist_user_id for i in invoices}
    therapists: dict[int, User] = {}
    if therapist_ids:
        for u in db.scalars(select(User).where(User.id.in_(therapist_ids))).all():
            therapists[u.id] = u

    if search:
        q = search.strip().lower()
        if q:
            filtered: list[Invoice] = []
            for inv in invoices:
                therapist = therapists.get(inv.therapist_user_id)
                name = (therapist.full_name or "").lower() if therapist else ""
                if q in name or q in str(inv.therapist_user_id) or q in (inv.month or "").lower():
                    filtered.append(inv)
            invoices = filtered

    all_disputes = list(db.scalars(select(TherapistStatementDispute)).all())
    flagged_keys = therapist_payout_flag_service.active_flagged_keys(db, invoices)

    rows: list[dict] = []
    totals = {
        "statementCount": 0,
        "approvedCount": 0,
        "disputedCount": 0,
        "pendingCount": 0,
        "needsReviewCount": 0,
        "totalNetInr": 0.0,
        "totalPayableNowInr": 0.0,
        "totalContestedInr": 0.0,
    }

    for inv in invoices:
        open_disputes = _open_disputes_for_invoice(
            all_disputes, inv.id, inv.month, inv.therapist_user_id
        )
        row = _statement_row(
            db,
            inv,
            therapists.get(inv.therapist_user_id),
            open_disputes,
            therapist_payout_flagged=therapist_payout_flag_service.is_invoice_flagged(
                inv, flagged_keys
            ),
        )
        rows.append(row)

        totals["statementCount"] += 1
        totals["totalNetInr"] += row["netInr"]
        totals["totalContestedInr"] += row["contestedInr"]
        if row["payableNowInr"] is not None:
            totals["totalPayableNowInr"] += row["payableNowInr"]
        if row["needsReview"]:
            totals["needsReviewCount"] += 1
        if inv.status == InvoiceStatus.APPROVED and not row["hasOpenDispute"]:
            totals["approvedCount"] += 1
        elif inv.status == InvoiceStatus.QUERIED or row["hasOpenDispute"]:
            totals["disputedCount"] += 1
        elif inv.status == InvoiceStatus.IN_REVIEW:
            totals["pendingCount"] += 1

    for key in ("totalNetInr", "totalPayableNowInr", "totalContestedInr"):
        totals[key] = round(totals[key], 2)

    return {"totals": totals, "statements": rows}
