from __future__ import annotations

from datetime import date, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assignment import BookingMode, CaseAssignment, CaseAssignmentStatus


def list_assignments(db: Session, case_id: int) -> list[CaseAssignment]:
    stmt = select(CaseAssignment).where(CaseAssignment.case_id == case_id).order_by(CaseAssignment.start_date.desc())
    return list(db.scalars(stmt).all())


def create_assignment(
    db: Session,
    *,
    case_id: int,
    therapist_user_id: int,
    assigned_by_user_id: int,
    start_date: date,
    reason_for_change: str | None = None,
    notes: str | None = None,
) -> CaseAssignment:
    active = db.scalars(
        select(CaseAssignment).where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
    ).all()
    for a in active:
        a.status = CaseAssignmentStatus.TRANSFERRED
        a.end_date = start_date
        a.reason_for_change = reason_for_change or "Reassigned"

    assignment = CaseAssignment(
        case_id=case_id,
        therapist_user_id=therapist_user_id,
        assigned_by_user_id=assigned_by_user_id,
        start_date=start_date,
        status=CaseAssignmentStatus.ACTIVE,
        reason_for_change=reason_for_change,
        notes=notes,
    )
    db.add(assignment)
    db.flush()
    return assignment


def _parse_time(value: str | None) -> time | None:
    if not value:
        return None
    parts = value.strip().split(":")
    return time(int(parts[0]), int(parts[1]))


def update_assignment_booking(db: Session, assignment_id: int, data: dict) -> CaseAssignment:
    assignment = db.get(CaseAssignment, assignment_id)
    if not assignment:
        raise ValueError("Assignment not found")
    if data.get("booking_mode") is not None:
        mode = data["booking_mode"]
        if mode not in (BookingMode.OPEN.value, BookingMode.FIXED.value):
            raise ValueError("booking_mode must be OPEN or FIXED")
        assignment.booking_mode = mode
    if "fixed_weekdays" in data:
        days = data.get("fixed_weekdays") or []
        assignment.set_fixed_weekdays(days)
    if data.get("fixed_start_time") is not None:
        assignment.fixed_start_time = _parse_time(data["fixed_start_time"])
    if data.get("fixed_end_time") is not None:
        assignment.fixed_end_time = _parse_time(data["fixed_end_time"])
    if "fixed_recurrence_group_id" in data:
        assignment.fixed_recurrence_group_id = data.get("fixed_recurrence_group_id")
    db.flush()
    return assignment


def assignment_to_read_dict(assignment: CaseAssignment, therapist_name: str | None = None) -> dict:
    from app.services.appointment_policy import assignment_booking_summary

    summary = assignment_booking_summary(assignment)
    return {
        "id": assignment.id,
        "case_id": assignment.case_id,
        "therapist_user_id": assignment.therapist_user_id,
        "therapist_name": therapist_name,
        "assigned_by_user_id": assignment.assigned_by_user_id,
        "start_date": assignment.start_date,
        "end_date": assignment.end_date,
        "status": assignment.status.value,
        "reason_for_change": assignment.reason_for_change,
        "notes": assignment.notes,
        "booking_mode": assignment.booking_mode,
        "fixed_weekdays": assignment.get_fixed_weekdays(),
        "fixed_start_time": assignment.fixed_start_time.strftime("%H:%M") if assignment.fixed_start_time else None,
        "fixed_end_time": assignment.fixed_end_time.strftime("%H:%M") if assignment.fixed_end_time else None,
        "fixed_recurrence_group_id": assignment.fixed_recurrence_group_id,
        "fixed_window_label": summary.get("fixed_window_label"),
    }
