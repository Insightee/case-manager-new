"""Scheduled-session leave dates and case×day occupancy.

Shadow leave counts a calendar day only when that case had a session or
booked slot. One active leave or child absence is allowed per case×day;
disjoint cases on the same day stay allowed.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.leave import LeaveStatus, TherapistLeave
from app.models.session import Session
from app.models.session import SessionStatus
from app.models.session_absence import SessionAbsenceRequest, SessionAbsenceStatus
from app.models.slot import SlotStatus, TherapistSlot

_COUNTED_SESSION_STATUSES = {
    SessionStatus.SCHEDULED,
    SessionStatus.IN_PROGRESS,
    SessionStatus.COMPLETED,
    SessionStatus.CLIENT_ABSENT,
    SessionStatus.THERAPIST_LEAVE,
}

_ACTIVE_LEAVE = {LeaveStatus.PENDING, LeaveStatus.APPROVED}
_ACTIVE_ABSENCE = {SessionAbsenceStatus.PENDING_APPROVAL, SessionAbsenceStatus.APPROVED}
SHADOW_MODULE = "shadow_support"


def iter_calendar_days(start: date, end: date):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def case_has_scheduled_presence(
    db: DbSession,
    case_id: int,
    day: date,
    *,
    leave_id: int | None = None,
) -> bool:
    """True when the case had a booked session or slot on this date."""
    sessions = db.scalars(
        select(Session).where(Session.case_id == case_id, Session.scheduled_date == day)
    ).all()
    leave_tag = f"leave:{leave_id}" if leave_id else None
    for session in sessions:
        if session.status in _COUNTED_SESSION_STATUSES:
            return True
        if (
            leave_tag
            and session.status == SessionStatus.CANCELLED
            and (session.cancellation_reason or "").strip() == leave_tag
        ):
            return True
    slot = db.scalars(
        select(TherapistSlot).where(
            TherapistSlot.case_id == case_id,
            TherapistSlot.slot_date == day,
            TherapistSlot.status == SlotStatus.BOOKED,
        )
    ).first()
    return slot is not None


def leave_scope_case_ids(leave: TherapistLeave) -> list[int] | None:
    """None means therapist-wide (all assigned cases)."""
    ids = [int(x) for x in (leave.case_ids or []) if x is not None]
    if leave.case_id is not None and int(leave.case_id) not in ids:
        ids.insert(0, int(leave.case_id))
    return ids or None


def assigned_case_ids(
    db: DbSession,
    therapist_user_id: int,
    *,
    shadow_only: bool = False,
) -> list[int]:
    stmt = (
        select(CaseAssignment.case_id)
        .join(Case, Case.id == CaseAssignment.case_id)
        .where(
            CaseAssignment.therapist_user_id == therapist_user_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
    )
    if shadow_only:
        stmt = stmt.where(Case.product_module == SHADOW_MODULE)
    return [int(r[0]) for r in db.execute(stmt).all()]


def scheduled_dates_in_range(
    db: DbSession,
    *,
    therapist_user_id: int,
    start: date,
    end: date,
    case_ids: list[int] | None = None,
    shadow_only: bool = False,
    leave_id: int | None = None,
) -> list[date]:
    """Dates in [start, end] that had a scheduled session or booked slot."""
    if end < start:
        return []
    candidate_ids = list(case_ids) if case_ids is not None else assigned_case_ids(
        db, therapist_user_id, shadow_only=shadow_only
    )
    if shadow_only and case_ids is not None and candidate_ids:
        rows = db.scalars(
            select(Case.id).where(Case.id.in_(candidate_ids), Case.product_module == SHADOW_MODULE)
        ).all()
        candidate_ids = [int(cid) for cid in rows]
    if not candidate_ids:
        return []
    return [
        day
        for day in iter_calendar_days(start, end)
        if any(case_has_scheduled_presence(db, cid, day, leave_id=leave_id) for cid in candidate_ids)
    ]


def billable_leave_dates(
    db: DbSession,
    leave: TherapistLeave,
    *,
    case_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    shadow_only: bool = False,
) -> list[date]:
    """Dates in the leave range that had a scheduled session or booked slot.

    When ``case_id`` is set, only that case's presence counts (invoice /
    case month math). Otherwise any scoped case counts (credit consumption).
    ``shadow_only`` restricts the any-case scan to shadow_support cases.
    """
    start = max(leave.start_date, from_date) if from_date else leave.start_date
    end = min(leave.end_date, to_date) if to_date else leave.end_date
    if end < start:
        return []

    scoped = leave_scope_case_ids(leave)
    if case_id is not None:
        if scoped is not None and case_id not in scoped:
            return []
        return scheduled_dates_in_range(
            db,
            therapist_user_id=leave.therapist_user_id,
            start=start,
            end=end,
            case_ids=[case_id],
            shadow_only=False,
            leave_id=leave.id,
        )

    return scheduled_dates_in_range(
        db,
        therapist_user_id=leave.therapist_user_id,
        start=start,
        end=end,
        case_ids=scoped,
        shadow_only=shadow_only,
        leave_id=leave.id,
    )


def unpaid_billable_dates(
    db: DbSession,
    leave: TherapistLeave,
    *,
    case_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[date]:
    """Billable dates after the leave's paid-day prefix (full-leave order)."""
    all_dates = billable_leave_dates(db, leave, case_id=case_id)
    paid = max(0, int(leave.paid_days or 0))
    unpaid = set(all_dates[paid:])
    return [
        day
        for day in all_dates
        if day in unpaid
        and (from_date is None or day >= from_date)
        and (to_date is None or day <= to_date)
    ]


def active_leave_for_case_day(
    db: DbSession,
    therapist_user_id: int,
    case_id: int,
    day: date,
) -> TherapistLeave | None:
    leaves = db.scalars(
        select(TherapistLeave).where(
            TherapistLeave.therapist_user_id == therapist_user_id,
            TherapistLeave.status.in_(_ACTIVE_LEAVE),
            TherapistLeave.start_date <= day,
            TherapistLeave.end_date >= day,
        )
    ).all()
    for leave in leaves:
        scoped = leave_scope_case_ids(leave)
        if scoped is None or case_id in scoped:
            return leave
    return None


def overlapping_active_leaves(
    db: DbSession,
    therapist_user_id: int,
    start: date,
    end: date,
) -> list[TherapistLeave]:
    return list(
        db.scalars(
            select(TherapistLeave).where(
                TherapistLeave.therapist_user_id == therapist_user_id,
                TherapistLeave.status.in_(_ACTIVE_LEAVE),
                TherapistLeave.start_date <= end,
                TherapistLeave.end_date >= start,
            )
        ).all()
    )


def active_absence_on_case_day(
    db: DbSession,
    case_id: int,
    day: date,
) -> SessionAbsenceRequest | None:
    return db.scalars(
        select(SessionAbsenceRequest)
        .join(Session, Session.id == SessionAbsenceRequest.session_id)
        .where(
            Session.case_id == case_id,
            Session.scheduled_date == day,
            SessionAbsenceRequest.status.in_(_ACTIVE_ABSENCE),
        )
    ).first()


def lock_leave_and_absence_rows(db: DbSession, therapist_user_id: int) -> None:
    db.scalars(
        select(TherapistLeave)
        .where(TherapistLeave.therapist_user_id == therapist_user_id)
        .with_for_update()
    ).all()
    db.scalars(
        select(SessionAbsenceRequest)
        .where(SessionAbsenceRequest.therapist_user_id == therapist_user_id)
        .with_for_update()
    ).all()


def raise_if_absence_blocks_leave(
    db: DbSession,
    *,
    therapist_user_id: int,
    start: date,
    end: date,
    case_ids: list[int] | None,
) -> None:
    """Block leave when an active child absence already occupies a scoped case×day."""
    scoped = list(case_ids) if case_ids else assigned_case_ids(db, therapist_user_id)
    for day in iter_calendar_days(start, end):
        for cid in scoped:
            if active_absence_on_case_day(db, cid, day):
                raise ValueError(
                    f"A child absence is already logged for this case on {day.isoformat()}. "
                    "One leave or child absence is allowed per case each day."
                )
