from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.appointment_usage import CaseAppointmentUsage
from app.models.assignment import BookingMode, CaseAssignment, CaseAssignmentStatus
from app.models.slot import TherapistSlot
from app.services.slot_calendar_service import WEEKDAY_KEYS, _weekday_key

MIN_CANCEL_HOURS = 6
MAX_RESCHEDULES_PER_MONTH = 2
PARENT_SLOT_DURATION_MINUTES = 60


@dataclass
class PolicyResult:
    allowed: bool
    reason: str = ""


def _slot_start_datetime(slot: TherapistSlot) -> datetime:
    start = slot.start_time
    dt = datetime.combine(slot.slot_date, start)
    return dt.replace(tzinfo=timezone.utc)


def hours_until_start(slot: TherapistSlot, now: Optional[datetime] = None) -> float:
    now = now or datetime.now(timezone.utc)
    start = _slot_start_datetime(slot)
    return (start - now).total_seconds() / 3600.0


def get_usage(db: Session, case_id: int, slot_date: date) -> CaseAppointmentUsage:
    row = db.scalars(
        select(CaseAppointmentUsage).where(
            CaseAppointmentUsage.case_id == case_id,
            CaseAppointmentUsage.year == slot_date.year,
            CaseAppointmentUsage.month == slot_date.month,
        )
    ).first()
    if row:
        return row
    row = CaseAppointmentUsage(
        case_id=case_id,
        year=slot_date.year,
        month=slot_date.month,
        reschedules_used=0,
    )
    db.add(row)
    db.flush()
    return row


def reschedules_remaining(db: Session, case_id: int, slot_date: date) -> int:
    usage = get_usage(db, case_id, slot_date)
    return max(0, MAX_RESCHEDULES_PER_MONTH - usage.reschedules_used)


def can_parent_cancel(slot: TherapistSlot, case_id: int, db: Session) -> PolicyResult:
    if slot.case_id != case_id:
        return PolicyResult(False, "Not your appointment")
    hours = hours_until_start(slot)
    if hours < MIN_CANCEL_HOURS:
        return PolicyResult(False, f"Cancel at least {MIN_CANCEL_HOURS} hours before the session")
    return PolicyResult(True)


def can_parent_reschedule(slot: TherapistSlot, case_id: int, db: Session) -> PolicyResult:
    cancel_check = can_parent_cancel(slot, case_id, db)
    if not cancel_check.allowed:
        return cancel_check
    remaining = reschedules_remaining(db, case_id, slot.slot_date)
    if remaining <= 0:
        return PolicyResult(False, f"Maximum {MAX_RESCHEDULES_PER_MONTH} reschedules per month reached")
    return PolicyResult(True)


def get_active_assignment_for_case(
    db: Session, case_id: int, therapist_user_id: int, *, case_service_id: int | None = None
) -> CaseAssignment | None:
    stmt = select(CaseAssignment).where(
        CaseAssignment.case_id == case_id,
        CaseAssignment.therapist_user_id == therapist_user_id,
        CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
    )
    if case_service_id is not None:
        stmt = stmt.where(CaseAssignment.case_service_id == case_service_id)
    return db.scalars(stmt).first()


def _time_in_range(t: time, start: time, end: time) -> bool:
    return start <= t < end


def slot_matches_fixed_window(slot: TherapistSlot, assignment: CaseAssignment) -> bool:
    if assignment.booking_mode != BookingMode.FIXED.value:
        return True
    weekdays = assignment.get_fixed_weekdays()
    if weekdays and _weekday_key(slot.slot_date) not in weekdays:
        return False
    if assignment.fixed_start_time and assignment.fixed_end_time:
        if not _time_in_range(slot.start_time, assignment.fixed_start_time, assignment.fixed_end_time):
            return False
    return True


def filter_slots_for_parent_booking(
    slots: list[TherapistSlot],
    assignment: CaseAssignment | None,
    *,
    parent_case_id: int | None = None,
) -> list[TherapistSlot]:
    """Keep 1h slots; apply FIXED window when not using pre-booked recurring."""
    result: list[TherapistSlot] = []
    for s in slots:
        duration = s.slot_duration_minutes or 30
        if duration < PARENT_SLOT_DURATION_MINUTES:
            continue
        if assignment and assignment.booking_mode == BookingMode.FIXED.value:
            if assignment.fixed_recurrence_group_id:
                if s.status.value == "BOOKED" and s.case_id == parent_case_id:
                    result.append(s)
                elif s.status.value == "AVAILABLE" and s.recurrence_group_id == assignment.fixed_recurrence_group_id:
                    result.append(s)
                continue
            if s.status.value == "AVAILABLE" and not slot_matches_fixed_window(s, assignment):
                continue
        result.append(s)
    return result


def assignment_booking_summary(assignment: CaseAssignment | None) -> dict:
    if not assignment or assignment.booking_mode != BookingMode.FIXED.value:
        return {"booking_mode": BookingMode.OPEN.value, "fixed_window_label": None}
    days = assignment.get_fixed_weekdays()
    day_labels = ", ".join(d.upper() for d in days) if days else "Scheduled days"
    start = assignment.fixed_start_time.strftime("%H:%M") if assignment.fixed_start_time else "—"
    end = assignment.fixed_end_time.strftime("%H:%M") if assignment.fixed_end_time else "—"
    return {
        "booking_mode": BookingMode.FIXED.value,
        "fixed_weekdays": days,
        "fixed_start_time": start,
        "fixed_end_time": end,
        "fixed_window_label": f"{day_labels} · {start}–{end}",
        "has_recurring": bool(assignment.fixed_recurrence_group_id),
    }
