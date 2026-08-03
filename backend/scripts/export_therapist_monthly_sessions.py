#!/usr/bin/env python3
"""Read-only therapist session extraction and finance reconciliation report.

Usage (from backend/):
  python -m scripts.export_therapist_monthly_sessions \\
    --from 2026-07-01 --to 2026-08-01 --timezone Asia/Kolkata \\
    --output ../exports/insightecase_july_2026_therapist_sessions.xlsx

No database writes. No status changes. No ledger or invoice generation.
"""
from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from sqlalchemy import Select, and_, or_, select, text
from sqlalchemy.orm import Session, selectinload

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal  # noqa: E402
from app.models.assignment import CaseAssignment, CaseAssignmentStatus  # noqa: E402
from app.models.case import BillingType, Case, CompensationMode  # noqa: E402
from app.models.child import Child  # noqa: E402
from app.models.client_billing import ClientInvoiceLine  # noqa: E402
from app.models.daily_log import LogApprovalStatus  # noqa: E402
from app.models.invoice import Invoice  # noqa: E402
from app.models.invoice_line import InvoiceCaseLine, InvoiceSessionLine, SessionLineSource, SessionLineType  # noqa: E402
from app.models.ledger_billing import BillingLedger  # noqa: E402
from app.models.session import Session as TherapySession  # noqa: E402
from app.models.session import SessionStatus  # noqa: E402
from app.models.session_absence import SessionAbsenceRequest, SessionAbsenceType  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.invoice_billing_service import (  # noqa: E402
    compute_session_line_amount,
    parse_month,
    session_duration_minutes,
)

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")
OCCURRED_CONFIRMED = "CONFIRMED_OCCURRED"
OCCURRED_REVIEW = "LIKELY_OCCURRED_REVIEW"
OCCURRED_NOT = "DID_NOT_OCCUR"

CANCELLED_STATUSES = {
    SessionStatus.CANCELLED,
    SessionStatus.RESCHEDULED,
    SessionStatus.NO_SHOW,
}
ABSENT_CLIENT_STATUSES = {SessionStatus.CLIENT_ABSENT, SessionStatus.NO_SHOW}
ABSENT_THERAPIST_STATUSES = {SessionStatus.THERAPIST_LEAVE}

# Sessions with actual_start this many days outside scheduled_date are flagged.
SCHEDULE_DRIFT_DAYS = 3
LONG_SESSION_MINUTES = 240
ZERO_DURATION_THRESHOLD = 0


@dataclass
class PeriodWindow:
    start: datetime  # inclusive, timezone-aware IST
    end: datetime  # exclusive, timezone-aware IST
    label: str

    @classmethod
    def from_args(cls, from_date: date, to_date: date, tz_name: str) -> PeriodWindow:
        tz = ZoneInfo(tz_name)
        start = datetime.combine(from_date, time.min, tzinfo=tz)
        end = datetime.combine(to_date, time.min, tzinfo=tz)
        return cls(start=start, end=end, label=f"{from_date.isoformat()}..{to_date.isoformat()}")


@dataclass
class LogSnapshot:
    """Minimal daily_log projection — avoids ORM columns missing on production."""

    id: int
    session_id: int
    attendance_status: str
    approval_status: str
    submitted_at: datetime | None
    created_at: datetime | None
    late_addition: bool = False


def effective_times_for_export(
    session: TherapySession,
    log: LogSnapshot | None,
) -> tuple[datetime | None, datetime | None]:
    edited_start = getattr(session, "edited_start_at", None)
    edited_end = getattr(session, "edited_end_at", None)
    if (
        log is not None
        and log.approval_status == LogApprovalStatus.APPROVED.value
        and edited_start is not None
        and edited_end is not None
    ):
        return edited_start, edited_end
    return session.actual_start_at, session.actual_end_at


def _ensure_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _to_ist(dt: datetime | None) -> datetime | None:
    aware = _ensure_aware(dt)
    return aware.astimezone(IST) if aware else None


def _fmt_dt(dt: datetime | None) -> str:
    ist = _to_ist(dt)
    return ist.isoformat() if ist else ""


def _fmt_date(d: date | None) -> str:
    return d.isoformat() if d else ""


def _combine_scheduled(session: TherapySession) -> datetime | None:
    if session.scheduled_date and session.start_time:
        naive = datetime.combine(session.scheduled_date, session.start_time)
        return naive.replace(tzinfo=IST)
    if session.scheduled_date:
        return datetime.combine(session.scheduled_date, time.min, tzinfo=IST)
    return None


def _combine_scheduled_end(session: TherapySession) -> datetime | None:
    if session.scheduled_date and session.end_time:
        naive = datetime.combine(session.scheduled_date, session.end_time)
        return naive.replace(tzinfo=IST)
    return None


def resolve_reporting_start(
    session: TherapySession,
    log: LogSnapshot | None,
) -> tuple[datetime | None, str]:
    """Return (reporting_start_ist, source_label) using the mandated fallback chain."""
    eff_start, _ = effective_times_for_export(session, log)
    if session.actual_start_at or eff_start:
        return _to_ist(session.actual_start_at or eff_start), "actual_check_in"

    if log and log.attendance_status:
        # No separate attendance timestamp table; attendance status implies a log exists.
        if log.submitted_at:
            return _to_ist(log.submitted_at), "daily_log_submitted"
        if log.created_at:
            return _to_ist(log.created_at), "daily_log_created"

    if session.status == SessionStatus.COMPLETED and session.actual_end_at:
        return _to_ist(session.actual_end_at), "session_completion"

    if log:
        if log.submitted_at:
            return _to_ist(log.submitted_at), "daily_log_submitted"
        if log.created_at:
            return _to_ist(log.created_at), "daily_log_created"

    scheduled = _combine_scheduled(session)
    if scheduled:
        return scheduled, "scheduled_start_review_only"
    return None, "none"


def duration_minutes(
    session: TherapySession,
    log: LogSnapshot | None,
    start: datetime | None,
    end: datetime | None,
) -> int | None:
    if start and end:
        s, e = _ensure_aware(start), _ensure_aware(end)
        if s and e:
            return int((e - s).total_seconds() / 60)
    return session_duration_minutes(session, None)


def _status_val(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value) if value is not None else ""


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compute_payout(case: Case | None) -> float | None:
    if not case or not case.billing_type:
        return None
    from app.models.invoice_line import SessionLineType

    line_type = (
        SessionLineType.PER_SESSION
        if case.billing_type == BillingType.PER_SESSION
        else SessionLineType.INCLUDED
    )
    return compute_session_line_amount(case, line_type)


def _compute_client_billable(case: Case | None) -> float | None:
    if not case:
        return None
    return _safe_float(case.client_rate_per_session_inr)


def classify_occurrence(
    session: TherapySession,
    log: LogSnapshot | None,
    reporting_start: datetime | None,
    reporting_source: str,
    duration_mins: int | None,
) -> tuple[str, str, str]:
    """Return (classification, inclusion_reason, exclusion_or_review_reason)."""
    status = session.status
    reasons: list[str] = []

    if status in CANCELLED_STATUSES:
        return OCCURRED_NOT, "cancelled_or_rescheduled", session.cancellation_reason or _status_val(status)

    if status in ABSENT_THERAPIST_STATUSES:
        return OCCURRED_NOT, "therapist_absent", _status_val(status)

    if status in ABSENT_CLIENT_STATUSES:
        # Retain for finance review — not auto-excluded from all counts.
        return OCCURRED_REVIEW, "client_absent_review", _status_val(status)

    has_start = bool(session.actual_start_at or session.edited_start_at)
    has_end = bool(session.actual_end_at or session.edited_end_at)
    auto_closed = bool(session.auto_ended)

    if has_start and (has_end or auto_closed):
        if status == SessionStatus.COMPLETED or (has_start and has_end):
            return OCCURRED_CONFIRMED, "check_in_and_check_out", ""
        reasons.append("timestamps_present_status_not_completed")

    if has_start and not has_end and not auto_closed:
        reasons.append("missing_checkout")
    if has_end and not has_start:
        reasons.append("missing_checkin")

    if status == SessionStatus.COMPLETED and (not has_start or not has_end):
        reasons.append("completed_status_incomplete_timestamps")

    if log and log.attendance_status and log.attendance_status not in ("PRESENT", "LATE", "PARTIAL"):
        reasons.append(f"attendance_{log.attendance_status}")

    if session.actual_times_edited or session.is_additional_visit or (log and log.late_addition):
        reasons.append("manual_or_backdated")

    if auto_closed:
        reasons.append("auto_closed")

    if duration_mins is not None and duration_mins > LONG_SESSION_MINUTES:
        reasons.append("long_duration")

    if duration_mins is not None and duration_mins <= ZERO_DURATION_THRESHOLD:
        reasons.append("zero_or_negative_duration")

    if reporting_source == "scheduled_start_review_only":
        reasons.append("scheduled_only_no_attendance_evidence")
        return OCCURRED_REVIEW, "scheduled_only", "; ".join(reasons)

    if status == SessionStatus.IN_PROGRESS:
        return OCCURRED_REVIEW, "in_progress", "; ".join(reasons) or "session_still_in_progress"

    if status == SessionStatus.SCHEDULED:
        return OCCURRED_NOT, "never_started", "scheduled_no_evidence"

    if reasons or status == SessionStatus.COMPLETED:
        return OCCURRED_REVIEW, "partial_evidence", "; ".join(reasons) or "incomplete_record"

    if not has_start and not has_end:
        return OCCURRED_NOT, "no_attendance_evidence", "no_timestamps"

    return OCCURRED_REVIEW, "unclassified_review", "; ".join(reasons)


def assignment_on_date(
    assignments_by_case: dict[int, list[CaseAssignment]],
    case_id: int,
    on_date: date,
    therapist_user_id: int,
) -> CaseAssignment | None:
    active: list[CaseAssignment] = []
    for a in assignments_by_case.get(case_id, []):
        if a.start_date > on_date:
            continue
        if a.end_date and a.end_date < on_date:
            continue
        active.append(a)
    for a in active:
        if a.therapist_user_id == therapist_user_id and a.status == CaseAssignmentStatus.ACTIVE:
            return a
    for a in active:
        if a.status == CaseAssignmentStatus.ACTIVE:
            return a
    return active[0] if active else None


def fetch_sessions(db: Session, window: PeriodWindow) -> list[TherapySession]:
    """Broad fetch with buffer; IST window applied in Python."""
    buffer_start = (window.start.date() - timedelta(days=3))
    buffer_end = (window.end.date() + timedelta(days=3))
    stmt: Select = (
        select(TherapySession)
        .where(
            or_(
                and_(
                    TherapySession.scheduled_date >= buffer_start,
                    TherapySession.scheduled_date <= buffer_end,
                ),
                TherapySession.actual_start_at.isnot(None),
            )
        )
        .options(selectinload(TherapySession.case).selectinload(Case.child))
        .order_by(TherapySession.id)
    )
    logger.info(
        "SQL sessions fetch: scheduled_date BETWEEN %s AND %s OR actual_start_at IS NOT NULL",
        buffer_start,
        buffer_end,
    )
    return list(db.scalars(stmt).all())


def fetch_log_snapshots(db: Session, session_ids: list[int]) -> dict[int, LogSnapshot]:
    """Load daily_logs via raw SQL — production-safe when ORM schema is ahead of DB."""
    if not session_ids:
        return {}
    logs: dict[int, LogSnapshot] = {}
    chunk_size = 500
    for offset in range(0, len(session_ids), chunk_size):
        chunk = session_ids[offset : offset + chunk_size]
        placeholders = ", ".join(f":sid{i}" for i in range(len(chunk)))
        params = {f"sid{i}": sid for i, sid in enumerate(chunk)}
        sql = text(
            f"""
            SELECT id, session_id, attendance_status, approval_status,
                   submitted_at, created_at, late_addition
            FROM daily_logs
            WHERE session_id IN ({placeholders})
            """
        )
        logger.info("SQL daily_logs fetch: session_id IN (%d ids)", len(chunk))
        for row in db.execute(sql, params).mappings():
            snap = LogSnapshot(
                id=int(row["id"]),
                session_id=int(row["session_id"]),
                attendance_status=str(row["attendance_status"] or ""),
                approval_status=str(row["approval_status"] or ""),
                submitted_at=row["submitted_at"],
                created_at=row["created_at"],
                late_addition=bool(row["late_addition"]),
            )
            logs[snap.session_id] = snap
    return logs


def fetch_related_maps(db: Session, session_ids: list[int], case_ids: list[int]) -> dict[str, Any]:
    users = {u.id: u for u in db.scalars(select(User)).all()}
    assignments: dict[int, list[CaseAssignment]] = defaultdict(list)
    for a in db.scalars(select(CaseAssignment).where(CaseAssignment.case_id.in_(case_ids))).all():
        assignments[a.case_id].append(a)

    ledger_by_session: dict[int, BillingLedger] = {}
    if session_ids:
        for bl in db.scalars(select(BillingLedger).where(BillingLedger.session_id.in_(session_ids))).all():
            if bl.session_id:
                ledger_by_session[bl.session_id] = bl

    invoice_line_by_session: dict[int, InvoiceSessionLine] = {}
    if session_ids:
        stmt = (
            select(InvoiceSessionLine)
            .where(InvoiceSessionLine.session_id.in_(session_ids))
            .options(selectinload(InvoiceSessionLine.case_line).selectinload(InvoiceCaseLine.invoice))
        )
        for isl in db.scalars(stmt).all():
            if isl.session_id:
                invoice_line_by_session[isl.session_id] = isl

    client_line_by_session: dict[int, ClientInvoiceLine] = {}
    if session_ids:
        for cil in db.scalars(
            select(ClientInvoiceLine).where(ClientInvoiceLine.session_id.in_(session_ids))
        ).all():
            if cil.session_id:
                client_line_by_session[cil.session_id] = cil

    absences_by_session: dict[int, SessionAbsenceRequest] = {}
    if session_ids:
        for ar in db.scalars(
            select(SessionAbsenceRequest).where(SessionAbsenceRequest.session_id.in_(session_ids))
        ).all():
            absences_by_session[ar.session_id] = ar

    cm_users: dict[int, User] = {}
    for case in db.scalars(select(Case).where(Case.id.in_(case_ids))).all():
        if case.case_manager_user_id and case.case_manager_user_id in users:
            cm_users[case.id] = users[case.case_manager_user_id]

    logs_by_session = fetch_log_snapshots(db, session_ids)

    return {
        "users": users,
        "assignments": assignments,
        "ledger_by_session": ledger_by_session,
        "invoice_line_by_session": invoice_line_by_session,
        "client_line_by_session": client_line_by_session,
        "absences_by_session": absences_by_session,
        "cm_users": cm_users,
        "logs_by_session": logs_by_session,
    }


def build_raw_row(
    session: TherapySession,
    maps: dict[str, Any],
    window: PeriodWindow,
) -> dict[str, Any] | None:
    log: LogSnapshot | None = maps["logs_by_session"].get(session.id)
    reporting_start, reporting_source = resolve_reporting_start(session, log)

    if reporting_start is None:
        in_window = False
    else:
        in_window = window.start <= reporting_start < window.end

    # Also include scheduled-in-window sessions for completeness (classified separately).
    scheduled_in_window = (
        session.scheduled_date >= window.start.date()
        and session.scheduled_date < window.end.date()
    )
    if not in_window and not scheduled_in_window:
        return None

    eff_start, eff_end = effective_times_for_export(session, log)
    dur = duration_minutes(session, log, eff_start, eff_end)
    classification, inclusion_reason, review_reason = classify_occurrence(
        session, log, reporting_start, reporting_source, dur
    )

    case = session.case
    child = case.child if case else None
    users: dict[int, User] = maps["users"]
    therapist = users.get(session.therapist_user_id)
    assignment = assignment_on_date(
        maps["assignments"],
        session.case_id,
        session.scheduled_date,
        session.therapist_user_id,
    )
    assigned_therapist_id = assignment.therapist_user_id if assignment else None
    is_replacement = bool(
        assigned_therapist_id and assigned_therapist_id != session.therapist_user_id
    )

    ledger = maps["ledger_by_session"].get(session.id)
    inv_line = maps["invoice_line_by_session"].get(session.id)
    client_line = maps["client_line_by_session"].get(session.id)
    absence = maps["absences_by_session"].get(session.id)
    cm = maps["cm_users"].get(session.case_id)

    calc_payout = _compute_payout(case)
    calc_client = _compute_client_billable(case)
    existing_inv_amt = _safe_float(inv_line.amount_inr) if inv_line else None
    existing_ledger_amt = _safe_float(ledger.total_inr) if ledger else None

    payout_discrepancy = (
        calc_payout is not None
        and existing_inv_amt is not None
        and abs(calc_payout - existing_inv_amt) > 0.01
    )
    billing_discrepancy = (
        calc_client is not None
        and existing_ledger_amt is not None
        and abs(calc_client - existing_ledger_amt) > 0.01
    )

    test_flag = bool(
        session.data_quality_flag
        and any(x in (session.data_quality_flag or "").lower() for x in ("test", "duplicate", "sandbox"))
    )

    row = {
        "session_id": session.id,
        "attendance_record_id": log.id if log else "",
        "daily_log_id": log.id if log else "",
        "billing_ledger_id": ledger.id if ledger else "",
        "therapist_invoice_line_id": inv_line.id if inv_line else "",
        "client_invoice_line_id": client_line.id if client_line else "",
        "case_id": session.case_id,
        "client_id": case.child_id if case else "",
        "therapist_user_id": session.therapist_user_id,
        "employee_staff_id": therapist.external_employee_id if therapist else "",
        "original_assigned_therapist_id": assigned_therapist_id or "",
        "actual_attending_therapist_id": session.therapist_user_id,
        "replacement_therapist_flag": "yes" if is_replacement else "no",
        "therapist_name": therapist.full_name if therapist else "",
        "client_name": child.full_name if child else "",
        "service_category": case.service_type if case else "",
        "service_product": case.product_module if case else "",
        "session_type": _status_val(session.mode),
        "assignment_id": assignment.id if assignment else "",
        "case_manager": cm.full_name if cm else "",
        "billing_type": _status_val(case.billing_type) if case else "",
        "payout_type": _status_val(case.compensation_mode) if case else "",
        "scheduled_session_date": _fmt_date(session.scheduled_date),
        "scheduled_start": _combine_scheduled(session).isoformat() if _combine_scheduled(session) else "",
        "scheduled_end": _combine_scheduled_end(session).isoformat() if _combine_scheduled_end(session) else "",
        "actual_check_in": _fmt_dt(session.actual_start_at),
        "actual_checkout": _fmt_dt(session.actual_end_at),
        "edited_check_in": _fmt_dt(session.edited_start_at),
        "edited_checkout": _fmt_dt(session.edited_end_at),
        "effective_check_in": _fmt_dt(eff_start),
        "effective_checkout": _fmt_dt(eff_end),
        "session_completed_timestamp": _fmt_dt(session.actual_end_at if session.status == SessionStatus.COMPLETED else None),
        "daily_log_created": _fmt_dt(log.created_at if log else None),
        "daily_log_submitted": _fmt_dt(log.submitted_at if log else None),
        "daily_log_approved": _fmt_dt(None),  # no approved_at column; use approval_status
        "total_actual_duration_minutes": dur if dur is not None else "",
        "july_reporting_date_ist": reporting_start.date().isoformat() if reporting_start else "",
        "reporting_start_source": reporting_source,
        "session_status": _status_val(session.status),
        "attendance_status": log.attendance_status if log else "",
        "attendance_verified": "yes" if log and log.attendance_status in ("PRESENT", "LATE", "PARTIAL") else "no",
        "daily_log_exists": "yes" if log else "no",
        "daily_log_status": log.approval_status if log else "",
        "daily_log_approved": "yes" if log and log.approval_status == LogApprovalStatus.APPROVED.value else "no",
        "billing_ledger_exists": "yes" if ledger else "no",
        "billing_ledger_status": _status_val(ledger.billable_status) if ledger else "",
        "therapist_invoice_line_exists": "yes" if inv_line else "no",
        "therapist_invoice_status": (
            _status_val(inv_line.case_line.invoice.status)
            if inv_line and inv_line.case_line and inv_line.case_line.invoice
            else ""
        ),
        "auto_closed": "yes" if session.auto_ended else "no",
        "auto_close_reason": session.auto_end_reason or "",
        "manual_backdated_session": "yes"
        if session.actual_times_edited or session.is_additional_visit or (log and log.late_addition)
        else "no",
        "client_absent": "yes"
        if session.status in ABSENT_CLIENT_STATUSES
        or (absence and absence.absence_type == SessionAbsenceType.CLIENT_ABSENT)
        else "no",
        "therapist_absent": "yes"
        if session.status in ABSENT_THERAPIST_STATUSES
        or (absence and absence.absence_type == SessionAbsenceType.THERAPIST_LEAVE)
        else "no",
        "cancellation_reason": session.cancellation_reason or "",
        "absence_reason": absence.reason if absence else "",
        "deleted_test_record_flag": "yes" if test_flag else "no",
        "client_billing_rate": calc_client if calc_client is not None else "",
        "therapist_payout_rate": _safe_float(case.pay_share_amount_inr or case.therapist_fixed_pay_inr) if case else "",
        "rate_type": _status_val(case.compensation_mode) if case else "",
        "calculated_client_billable": calc_client if calc_client is not None else "",
        "calculated_therapist_payable": calc_payout if calc_payout is not None else "",
        "existing_ledger_amount": existing_ledger_amt if existing_ledger_amt is not None else "",
        "existing_therapist_invoice_line_amount": existing_inv_amt if existing_inv_amt is not None else "",
        "existing_client_invoice_line_amount": _safe_float(client_line.amount_inr) if client_line else "",
        "manual_adjustment_amount": "",
        "leave_deduction": "",
        "tds_amount": "",
        "occurrence_classification": classification,
        "inclusion_reason": inclusion_reason,
        "exclusion_or_review_reason": review_reason,
        "duplicate_flag": "no",
        "overlapping_session_flag": "no",
        "missing_timestamp_flag": "yes"
        if not session.actual_start_at and not session.actual_end_at
        else "no",
        "duration_anomaly_flag": "yes"
        if dur is not None and (dur <= 0 or dur > LONG_SESSION_MINUTES)
        else "no",
        "rate_missing_flag": "yes" if case and not case.billing_type else "no",
        "assignment_mismatch_flag": "yes" if is_replacement else "no",
        "billing_discrepancy_flag": "yes" if billing_discrepancy else "no",
        "payout_discrepancy_flag": "yes" if payout_discrepancy else "no",
        "geolocation_checkin": f"{session.checkin_lat},{session.checkin_lng}"
        if session.checkin_lat is not None
        else "",
        "geolocation_checkout": f"{session.checkout_lat},{session.checkout_lng}"
        if session.checkout_lat is not None
        else "",
        "data_quality_flag": session.data_quality_flag or "",
        "in_reporting_window": "yes" if in_window else "no",
    }
    return row


def mark_duplicates_and_overlaps(rows: list[dict[str, Any]]) -> None:
    by_key: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        key = (
            r["therapist_user_id"],
            r["client_id"],
            r.get("july_reporting_date_ist") or r["scheduled_session_date"],
        )
        by_key[key].append(r)

    for group in by_key.values():
        if len(group) > 1:
            for r in group:
                r["duplicate_flag"] = "yes"

    by_therapist: dict[int, list[dict]] = defaultdict(list)
    for r in rows:
        if r["occurrence_classification"] in (OCCURRED_CONFIRMED, OCCURRED_REVIEW):
            by_therapist[r["therapist_user_id"]].append(r)

    for therapist_rows in by_therapist.values():
        parsed: list[tuple[dict, datetime, datetime]] = []
        for r in therapist_rows:
            start_s = r.get("effective_check_in") or r.get("actual_check_in") or r.get("scheduled_start")
            end_s = r.get("effective_checkout") or r.get("actual_checkout") or r.get("scheduled_end")
            if not start_s:
                continue
            try:
                start = datetime.fromisoformat(start_s)
                end = datetime.fromisoformat(end_s) if end_s else start + timedelta(hours=1)
            except ValueError:
                continue
            parsed.append((r, start, end))
        for i, (r1, s1, e1) in enumerate(parsed):
            for r2, s2, e2 in parsed[i + 1 :]:
                if s1 < e2 and s2 < e1:
                    r1["overlapping_session_flag"] = "yes"
                    r2["overlapping_session_flag"] = "yes"


def therapist_summary(rows: list[dict[str, Any]], maps: dict[str, Any]) -> list[dict[str, Any]]:
    users = maps["users"]
    by_tid: dict[int, list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("in_reporting_window") == "yes":
            by_tid[r["therapist_user_id"]].append(r)

    summaries: list[dict[str, Any]] = []
    for tid in sorted(by_tid.keys()):
        trows = by_tid[tid]
        user = users.get(tid)
        confirmed = [r for r in trows if r["occurrence_classification"] == OCCURRED_CONFIRMED]
        review = [r for r in trows if r["occurrence_classification"] == OCCURRED_REVIEW]
        cancelled = [r for r in trows if r["session_status"] in ("CANCELLED", "RESCHEDULED")]
        client_abs = [r for r in trows if r["client_absent"] == "yes"]
        therapist_abs = [r for r in trows if r["therapist_absent"] == "yes"]
        approved_logs = [r for r in trows if r["daily_log_approved"] == "yes"]
        in_ledger = [r for r in trows if r["billing_ledger_exists"] == "yes"]
        in_invoice = [r for r in trows if r["therapist_invoice_line_exists"] == "yes"]
        confirmed_mins = sum(
            int(r["total_actual_duration_minutes"])
            for r in confirmed
            if r["total_actual_duration_minutes"] != ""
        )
        existing_payout = sum(
            float(r["existing_therapist_invoice_line_amount"])
            for r in in_invoice
            if r["existing_therapist_invoice_line_amount"] != ""
        )
        recalc_payout = sum(
            float(r["calculated_therapist_payable"])
            for r in confirmed
            if r["calculated_therapist_payable"] != ""
        )
        exceptions = sum(
            1
            for r in trows
            if r["occurrence_classification"] == OCCURRED_REVIEW
            or r["duplicate_flag"] == "yes"
            or r["overlapping_session_flag"] == "yes"
            or r["rate_missing_flag"] == "yes"
        )
        assigned_clients = len({r["case_id"] for r in trows})
        served_clients = len({r["case_id"] for r in confirmed + review})

        summaries.append(
            {
                "employee_staff_id": user.external_employee_id if user else "",
                "therapist_id": tid,
                "therapist_name": user.full_name if user else "",
                "active_status": _status_val(user.employment_status) if user else "",
                "assigned_clients": assigned_clients,
                "unique_clients_served": served_clients,
                "scheduled_sessions": len(trows),
                "confirmed_occurred": len(confirmed),
                "likely_occurred_review": len(review),
                "cancelled_sessions": len(cancelled),
                "client_absent_sessions": len(client_abs),
                "therapist_absent_sessions": len(therapist_abs),
                "sessions_with_approved_logs": len(approved_logs),
                "sessions_without_approved_logs": len(trows) - len(approved_logs),
                "sessions_in_billing_ledger": len(in_ledger),
                "sessions_missing_from_ledger": len(confirmed + review) - len(in_ledger),
                "sessions_in_therapist_invoice": len(in_invoice),
                "sessions_missing_from_invoice": len(confirmed + review) - len(in_invoice),
                "total_confirmed_minutes": confirmed_mins,
                "total_confirmed_hours": round(confirmed_mins / 60, 2),
                "existing_calculated_payout": round(existing_payout, 2),
                "recalculated_session_payout": round(recalc_payout, 2),
                "payout_difference": round(recalc_payout - existing_payout, 2),
                "missing_bank_pan_rate_info": "yes" if any(r["rate_missing_flag"] == "yes" for r in trows) else "no",
                "exceptions_requiring_review": exceptions,
            }
        )
    return summaries


def client_therapist_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    key_rows: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("in_reporting_window") != "yes":
            continue
        key = (r["therapist_user_id"], r["case_id"], r.get("assignment_id") or 0)
        key_rows[key].append(r)

    out: list[dict[str, Any]] = []
    for (tid, case_id, asg_id), group in sorted(key_rows.items()):
        confirmed = [r for r in group if r["occurrence_classification"] == OCCURRED_CONFIRMED]
        review = [r for r in group if r["occurrence_classification"] == OCCURRED_REVIEW]
        client_abs = [r for r in group if r["client_absent"] == "yes"]
        total_mins = sum(
            int(r["total_actual_duration_minutes"])
            for r in confirmed
            if r["total_actual_duration_minutes"] != ""
        )
        client_rate = next((r["client_billing_rate"] for r in group if r["client_billing_rate"] != ""), "")
        payout_rate = next((r["therapist_payout_rate"] for r in group if r["therapist_payout_rate"] != ""), "")
        expected_client = float(client_rate) * len(confirmed) if client_rate != "" else ""
        expected_payout = sum(
            float(r["calculated_therapist_payable"])
            for r in confirmed
            if r["calculated_therapist_payable"] != ""
        )
        existing_client = sum(
            float(r["existing_ledger_amount"]) for r in group if r["existing_ledger_amount"] != ""
        )
        existing_payout = sum(
            float(r["existing_therapist_invoice_line_amount"])
            for r in group
            if r["existing_therapist_invoice_line_amount"] != ""
        )
        sample = group[0]
        out.append(
            {
                "therapist_id": tid,
                "employee_id": sample["employee_staff_id"],
                "therapist_name": sample["therapist_name"],
                "client_id": sample["client_id"],
                "client_name": sample["client_name"],
                "case_id": case_id,
                "assignment_id": asg_id or "",
                "service_category": sample["service_category"],
                "confirmed_sessions": len(confirmed),
                "review_sessions": len(review),
                "client_absent_sessions": len(client_abs),
                "scheduled_sessions": len(group),
                "total_confirmed_duration_minutes": total_mins,
                "client_billing_rate": client_rate,
                "therapist_payout_rate": payout_rate,
                "expected_client_billing": expected_client,
                "expected_therapist_payout": round(expected_payout, 2) if expected_payout != "" else "",
                "existing_client_billing": round(existing_client, 2) if existing_client else "",
                "existing_therapist_payout": round(existing_payout, 2) if existing_payout else "",
                "billing_variance": (
                    round(float(expected_client) - existing_client, 2)
                    if expected_client != "" and existing_client
                    else ""
                ),
                "payout_variance": (
                    round(float(expected_payout) - existing_payout, 2)
                    if expected_payout != "" and existing_payout
                    else ""
                ),
                "exception_reason": "; ".join(
                    sorted({r["exclusion_or_review_reason"] for r in review if r["exclusion_or_review_reason"]})
                ),
            }
        )
    return out


def definition_comparison(rows: list[dict[str, Any]]) -> dict[str, Any]:
    in_window = [r for r in rows if r.get("in_reporting_window") == "yes"]

    def count_ts_completed() -> int:
        return sum(
            1
            for r in in_window
            if r["occurrence_classification"] == OCCURRED_CONFIRMED
        )

    def count_status_completed() -> int:
        return sum(1 for r in in_window if r["session_status"] == "COMPLETED")

    def count_approved_logs() -> int:
        return sum(1 for r in in_window if r["daily_log_approved"] == "yes")

    def count_in_invoice() -> int:
        return sum(1 for r in in_window if r["therapist_invoice_line_exists"] == "yes")

    totals = {
        "timestamp_confirmed_occurred": count_ts_completed(),
        "session_table_completed": count_status_completed(),
        "approved_daily_logs": count_approved_logs(),
        "therapist_invoice_lines": count_in_invoice(),
    }
    totals["ts_vs_completed"] = totals["timestamp_confirmed_occurred"] - totals["session_table_completed"]
    totals["completed_vs_logs"] = totals["session_table_completed"] - totals["approved_daily_logs"]
    totals["logs_vs_invoice"] = totals["approved_daily_logs"] - totals["therapist_invoice_lines"]

    per_therapist: dict[int, dict] = {}
    for r in in_window:
        tid = r["therapist_user_id"]
        if tid not in per_therapist:
            per_therapist[tid] = {
                "therapist_name": r["therapist_name"],
                "timestamp_confirmed": 0,
                "status_completed": 0,
                "approved_logs": 0,
                "invoice_lines": 0,
            }
        pt = per_therapist[tid]
        if r["occurrence_classification"] == OCCURRED_CONFIRMED:
            pt["timestamp_confirmed"] += 1
        if r["session_status"] == "COMPLETED":
            pt["status_completed"] += 1
        if r["daily_log_approved"] == "yes":
            pt["approved_logs"] += 1
        if r["therapist_invoice_line_exists"] == "yes":
            pt["invoice_lines"] += 1

    return {"totals": totals, "per_therapist": per_therapist}


def write_sheet(wb: Workbook, title: str, headers: list[str], data: list[dict[str, Any]]) -> None:
    ws = wb.create_sheet(title=title[:31])
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for row in data:
        ws.append([row.get(h, "") for h in headers])
    for col_idx, _ in enumerate(headers, 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = 18


RAW_HEADERS = [
    "session_id", "attendance_record_id", "daily_log_id", "billing_ledger_id",
    "therapist_invoice_line_id", "client_invoice_line_id", "case_id", "client_id",
    "therapist_user_id", "employee_staff_id", "original_assigned_therapist_id",
    "actual_attending_therapist_id", "replacement_therapist_flag", "therapist_name",
    "client_name", "service_category", "service_product", "session_type", "assignment_id",
    "case_manager", "billing_type", "payout_type", "scheduled_session_date", "scheduled_start",
    "scheduled_end", "actual_check_in", "actual_checkout", "edited_check_in", "edited_checkout",
    "effective_check_in", "effective_checkout", "session_completed_timestamp",
    "daily_log_created", "daily_log_submitted", "total_actual_duration_minutes",
    "july_reporting_date_ist", "reporting_start_source", "session_status", "attendance_status",
    "attendance_verified", "daily_log_exists", "daily_log_status", "daily_log_approved",
    "billing_ledger_exists", "billing_ledger_status", "therapist_invoice_line_exists",
    "therapist_invoice_status", "auto_closed", "auto_close_reason", "manual_backdated_session",
    "client_absent", "therapist_absent", "cancellation_reason", "absence_reason",
    "deleted_test_record_flag", "client_billing_rate", "therapist_payout_rate", "rate_type",
    "calculated_client_billable", "calculated_therapist_payable", "existing_ledger_amount",
    "existing_therapist_invoice_line_amount", "existing_client_invoice_line_amount",
    "occurrence_classification", "inclusion_reason", "exclusion_or_review_reason",
    "duplicate_flag", "overlapping_session_flag", "missing_timestamp_flag",
    "duration_anomaly_flag", "rate_missing_flag", "assignment_mismatch_flag",
    "billing_discrepancy_flag", "payout_discrepancy_flag", "geolocation_checkin",
    "geolocation_checkout", "data_quality_flag", "in_reporting_window",
]


def run_export(
    *,
    from_date: date,
    to_date: date,
    tz_name: str,
    output_path: Path,
) -> dict[str, Any]:
    window = PeriodWindow.from_args(from_date, to_date, tz_name)
    db = SessionLocal()
    try:
        sessions = fetch_sessions(db, window)
        case_ids = list({s.case_id for s in sessions})
        session_ids = [s.id for s in sessions]
        maps = fetch_related_maps(db, session_ids, case_ids)

        rows: list[dict[str, Any]] = []
        for session in sessions:
            row = build_raw_row(session, maps, window)
            if row:
                rows.append(row)

        mark_duplicates_and_overlaps(rows)
        t_summary = therapist_summary(rows, maps)
        ct_summary = client_therapist_summary(rows)
        comparison = definition_comparison(rows)

        # Exception subsets
        missing_logs = [
            r for r in rows
            if r.get("in_reporting_window") == "yes"
            and r["occurrence_classification"] in (OCCURRED_CONFIRMED, OCCURRED_REVIEW)
            and (r["daily_log_exists"] == "no" or r["daily_log_approved"] == "no")
        ]
        missing_billing = [
            r for r in rows
            if r.get("in_reporting_window") == "yes"
            and r["occurrence_classification"] in (OCCURRED_CONFIRMED, OCCURRED_REVIEW)
            and r["billing_ledger_exists"] == "no"
        ]
        missing_payout = [
            r for r in rows
            if r.get("in_reporting_window") == "yes"
            and r["occurrence_classification"] in (OCCURRED_CONFIRMED, OCCURRED_REVIEW)
            and r["therapist_invoice_line_exists"] == "no"
        ]
        ts_exceptions = [
            r for r in rows
            if r.get("in_reporting_window") == "yes"
            and (
                r["missing_timestamp_flag"] == "yes"
                or r["duration_anomaly_flag"] == "yes"
                or r["auto_closed"] == "yes"
                or r["overlapping_session_flag"] == "yes"
            )
        ]
        duplicates = [r for r in rows if r["duplicate_flag"] == "yes"]
        rate_issues = [
            r for r in rows
            if r.get("in_reporting_window") == "yes"
            and (
                r["rate_missing_flag"] == "yes"
                or r["assignment_mismatch_flag"] == "yes"
                or r["replacement_therapist_flag"] == "yes"
            )
        ]

        # Orphan checks: approved logs / invoice lines without session in window
        orphan_sql = text(
            """
            SELECT id, session_id
            FROM daily_logs
            WHERE approval_status = :approved
              AND submitted_at >= :start_at
              AND submitted_at < :end_at
            """
        )
        orphan_logs = db.execute(
            orphan_sql,
            {
                "approved": LogApprovalStatus.APPROVED.value,
                "start_at": window.start,
                "end_at": window.end,
            },
        ).mappings().all()
        session_id_set = {r["session_id"] for r in rows}
        orphan_log_rows = [
            {
                "daily_log_id": int(lg["id"]),
                "session_id": int(lg["session_id"]),
                "note": "approved_log_outside_session_window",
            }
            for lg in orphan_logs
            if int(lg["session_id"]) not in session_id_set
        ]

        wb = Workbook()
        wb.remove(wb.active)

        # 00 Definition comparison
        comp_rows = [
            {"metric": "Sessions with completed/valid timestamps (CONFIRMED_OCCURRED)", "count": comparison["totals"]["timestamp_confirmed_occurred"]},
            {"metric": "Sessions marked COMPLETED in session table", "count": comparison["totals"]["session_table_completed"]},
            {"metric": "Sessions with approved daily logs", "count": comparison["totals"]["approved_daily_logs"]},
            {"metric": "Sessions in therapist payout invoice lines", "count": comparison["totals"]["therapist_invoice_lines"]},
            {"metric": "Delta: timestamp confirmed − table completed", "count": comparison["totals"]["ts_vs_completed"]},
            {"metric": "Delta: table completed − approved logs", "count": comparison["totals"]["completed_vs_logs"]},
            {"metric": "Delta: approved logs − invoice lines", "count": comparison["totals"]["logs_vs_invoice"]},
        ]
        for tid, pt in sorted(comparison["per_therapist"].items()):
            comp_rows.append(
                {
                    "metric": f"Therapist {pt['therapist_name']} (id={tid})",
                    "timestamp_confirmed": pt["timestamp_confirmed"],
                    "status_completed": pt["status_completed"],
                    "approved_logs": pt["approved_logs"],
                    "invoice_lines": pt["invoice_lines"],
                }
            )
        comp_headers = [
            "metric", "count", "timestamp_confirmed", "status_completed",
            "approved_logs", "invoice_lines",
        ]
        write_sheet(wb, "00_Definition_Comparison", comp_headers, comp_rows)

        write_sheet(wb, "01_Raw_Sessions", RAW_HEADERS, rows)

        t_headers = list(t_summary[0].keys()) if t_summary else ["therapist_id"]
        write_sheet(wb, "02_Therapist_Summary", t_headers, t_summary)

        ct_headers = list(ct_summary[0].keys()) if ct_summary else ["therapist_id"]
        write_sheet(wb, "03_Client_Therapist_Summary", ct_headers, ct_summary)

        exc_headers = RAW_HEADERS
        write_sheet(wb, "04_Missing_Logs", exc_headers, missing_logs)
        write_sheet(wb, "05_Missing_From_Billing", exc_headers, missing_billing)
        write_sheet(wb, "06_Missing_From_Payout", exc_headers, missing_payout)
        write_sheet(wb, "07_Timestamp_Exceptions", exc_headers, ts_exceptions)
        write_sheet(wb, "08_Duplicates_Overlaps", exc_headers, duplicates)
        write_sheet(wb, "09_Rate_Assignment_Issues", exc_headers, rate_issues)
        if orphan_log_rows:
            write_sheet(wb, "10_Orphan_Approved_Logs", ["daily_log_id", "session_id", "note"], orphan_log_rows)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(output_path)
        logger.info("Wrote %s (%d raw rows)", output_path, len(rows))

        return {
            "output": str(output_path),
            "raw_row_count": len(rows),
            "comparison": comparison,
            "rows": rows,
            "orphan_logs": orphan_log_rows,
        }
    finally:
        db.close()


def validate_export(result: dict[str, Any], rows: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    ids = [r["session_id"] for r in rows]
    if any(not i for i in ids):
        errors.append("Row missing session_id")
    dup_ids = {i for i in ids if ids.count(i) > 1}
    if dup_ids:
        errors.append(f"Duplicate session_ids in raw sheet: {sorted(dup_ids)}")

    in_window = [r for r in rows if r.get("in_reporting_window") == "yes"]
    confirmed = [r for r in in_window if r["occurrence_classification"] == OCCURRED_CONFIRMED]
    ts_total = result["comparison"]["totals"]["timestamp_confirmed_occurred"]
    if len(confirmed) != ts_total:
        errors.append(f"Summary mismatch: confirmed count {len(confirmed)} vs comparison {ts_total}")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Export therapist session reconciliation report (read-only).")
    parser.add_argument("--from", dest="from_date", required=True, help="Start date YYYY-MM-DD (inclusive, IST)")
    parser.add_argument("--to", dest="to_date", required=True, help="End date YYYY-MM-DD (exclusive, IST)")
    parser.add_argument("--timezone", default="Asia/Kolkata")
    parser.add_argument("--output", required=True, help="Output XLSX path")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    from_d = date.fromisoformat(args.from_date)
    to_d = date.fromisoformat(args.to_date)
    output = Path(args.output)

    result = run_export(from_date=from_d, to_date=to_d, tz_name=args.timezone, output_path=output)
    errors = validate_export(result, result["rows"])
    if errors:
        for e in errors:
            logger.warning("Validation: %s", e)
    else:
        logger.info("Validation passed")

    print(f"Export complete: {result['output']} ({result['raw_row_count']} sessions)")
    comp = result["comparison"]["totals"]
    print(
        f"Definitions — timestamps:{comp['timestamp_confirmed_occurred']} | "
        f"completed:{comp['session_table_completed']} | "
        f"approved_logs:{comp['approved_daily_logs']} | "
        f"invoice_lines:{comp['therapist_invoice_lines']}"
    )


if __name__ == "__main__":
    main()
