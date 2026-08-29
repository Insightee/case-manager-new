#!/usr/bin/env python3
"""Tally live case rates vs as-of rates vs session activity for billing months.

Writes Excel to ~/Downloads (not the repo) so Cursor save issues do not block delivery.
"""
from __future__ import annotations

import sys
from calendar import monthrange
from datetime import date, datetime
from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import func, select

# Allow running from repo root or backend/
BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.billing_validation import client_amount_inr, resolve_therapist_pay
from app.core.database import SessionLocal
from app.models.case import Case
from app.models.case_billing_rate_change import CaseBillingRateChange
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.session import Session as TherapySession, SessionStatus
from app.services import billing_rate_history_service, finance_payout_preview_service as payout
from app.services.reports_export_helpers import month_bounds


def _months_to_check() -> list[str]:
    today = date.today()
    out: list[str] = []
    y, m = today.year, today.month
    for _ in range(3):
        out.append(f"{y}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(out))


def _approved_session_count(db, case_id: int, ym: str) -> int:
    start, end = month_bounds(ym)
    return int(
        db.scalar(
            select(func.count())
            .select_from(TherapySession)
            .join(DailyLog, DailyLog.session_id == TherapySession.id)
            .where(
                TherapySession.case_id == case_id,
                TherapySession.status == SessionStatus.COMPLETED,
                TherapySession.scheduled_date >= start,
                TherapySession.scheduled_date <= end,
                DailyLog.approval_status == LogApprovalStatus.APPROVED,
            )
        )
        or 0
    )


def main() -> Path:
    downloads = Path.home() / "Downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    out = downloads / f"billing_asof_tally_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    wb = Workbook()
    ws = wb.active
    ws.title = "asof_tally"
    headers = [
        "case_id",
        "case_code",
        "product_module",
        "billing_type",
        "month",
        "approved_sessions",
        "live_therapist_pay",
        "asof_therapist_pay",
        "live_client_amount",
        "asof_client_amount",
        "predicted_payout_live",
        "predicted_payout_asof",
        "payout_delta",
        "flag",
        "rate_history_rows",
        "notes",
    ]
    ws.append(headers)

    months = _months_to_check()
    discrepancy_count = 0

    with SessionLocal() as db:
        cases = list(db.scalars(select(Case).order_by(Case.id)).all())
        for case in cases:
            history_n = int(
                db.scalar(
                    select(func.count()).select_from(CaseBillingRateChange).where(
                        CaseBillingRateChange.case_id == case.id
                    )
                )
                or 0
            )
            live_t = resolve_therapist_pay(case)
            live_c = client_amount_inr(case)
            for ym in months:
                _ms, month_end = month_bounds(ym)
                sessions = _approved_session_count(db, case.id, ym)
                asof_t = billing_rate_history_service.resolve_therapist_pay_as_of(
                    db, case, month_end
                )
                asof_c = billing_rate_history_service.resolve_client_amount_as_of(
                    db, case, month_end
                )
                pred_live = payout.predicted_subtotal_inr(
                    case, approved_sessions=sessions
                )
                pred_asof = payout.predicted_subtotal_inr(
                    case, approved_sessions=sessions, db=db, as_of=month_end
                )
                delta = round(pred_asof - pred_live, 2)
                flags: list[str] = []
                notes: list[str] = []
                if history_n and abs(asof_t - live_t) > 0.009:
                    flags.append("THERAPIST_ASOF_DIFFERS_FROM_LIVE")
                    notes.append(
                        f"Live therapist ₹{live_t:.0f} vs as-of {month_end} ₹{asof_t:.0f}"
                    )
                if history_n and abs(asof_c - live_c) > 0.009:
                    flags.append("CLIENT_ASOF_DIFFERS_FROM_LIVE")
                    notes.append(
                        f"Live client ₹{live_c:.0f} vs as-of {month_end} ₹{asof_c:.0f}"
                    )
                if abs(delta) > 0.009 and sessions > 0:
                    flags.append("PAYOUT_DELTA")
                # Expected when history exists and month is before hike: asof < live after hike applied to case
                if flags:
                    discrepancy_count += 1
                ws.append(
                    [
                        case.id,
                        case.case_code,
                        case.product_module,
                        case.billing_type.value if case.billing_type else "",
                        ym,
                        sessions,
                        live_t,
                        asof_t,
                        live_c,
                        asof_c,
                        pred_live,
                        pred_asof,
                        delta,
                        "|".join(flags) if flags else "OK",
                        history_n,
                        "; ".join(notes),
                    ]
                )

        summary = wb.create_sheet("summary", 0)
        summary.append(["generated_at", datetime.now().isoformat()])
        summary.append(["months", ", ".join(months)])
        summary.append(["cases_scanned", len(cases)])
        summary.append(["flagged_rows", discrepancy_count])
        summary.append(
            [
                "interpretation",
                "THERAPIST_ASOF_DIFFERS_FROM_LIVE / CLIENT_ASOF_DIFFERS_FROM_LIVE "
                "mean the live case field would mis-price that month — as-of path must be used "
                "(now wired for invoice session lines, payout preview, client draft).",
            ]
        )

    wb.save(out)
    print(f"Wrote {out}")
    print(f"Flagged rows: {discrepancy_count}")
    return out


if __name__ == "__main__":
    main()
