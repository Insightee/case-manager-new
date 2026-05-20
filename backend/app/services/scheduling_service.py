from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.permissions import get_active_assignment
from app.models.appointment_reschedule import AppointmentReschedule
from app.models.assignment import BookingMode, CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.recurring_schedule import RecurringScheduleAssignment, RecurringScheduleStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.slot import BookingSource, SlotStatus, TherapistSlot
from app.models.user import User
from app.services import appointment_booking_service as appt_booking
from app.services import appointment_notification_service as appt_notify
from app.services import appointment_policy as policy
from app.services import slot_calendar_service as cal


def _slot_to_dict(slot: TherapistSlot) -> dict[str, Any]:
    data = cal._slot_to_dict(slot)
    data["session_id"] = slot.session_id
    data["rescheduled_to_slot_id"] = slot.rescheduled_to_slot_id
    return data


def get_unified_calendar(
    db: Session,
    therapist_user_id: int,
    from_date: date,
    to_date: date,
    *,
    case_id: Optional[int] = None,
) -> dict[str, Any]:
    return cal.get_calendar_view(db, therapist_user_id, from_date, to_date)


def create_slot(
    db: Session,
    therapist_user_id: int,
    *,
    slot_date: date,
    start_time: time,
    end_time: time,
    notes: Optional[str] = None,
    status: SlotStatus = SlotStatus.AVAILABLE,
) -> TherapistSlot:
    if end_time <= start_time:
        raise ValueError("end_time must be after start_time")
    if cal.is_day_on_leave(db, therapist_user_id, slot_date) and status == SlotStatus.AVAILABLE:
        raise ValueError("Cannot add availability on a leave day")
    existing = db.scalars(
        select(TherapistSlot).where(
            TherapistSlot.therapist_user_id == therapist_user_id,
            TherapistSlot.slot_date == slot_date,
            TherapistSlot.start_time == start_time,
        )
    ).first()
    if existing:
        raise ValueError("A slot already exists at this date and time")
    duration = int(
        (datetime.combine(date.today(), end_time) - datetime.combine(date.today(), start_time)).total_seconds()
        // 60
    )
    slot = TherapistSlot(
        therapist_user_id=therapist_user_id,
        slot_date=slot_date,
        start_time=start_time,
        end_time=end_time,
        status=status,
        notes=notes,
        slot_duration_minutes=duration,
    )
    db.add(slot)
    db.flush()
    return slot


def update_slot(
    db: Session,
    slot_id: int,
    *,
    slot_date: Optional[date] = None,
    start_time: Optional[time] = None,
    end_time: Optional[time] = None,
    status: Optional[SlotStatus] = None,
    notes: Optional[str] = None,
) -> TherapistSlot:
    slot = db.scalars(
        select(TherapistSlot)
        .where(TherapistSlot.id == slot_id)
        .options(selectinload(TherapistSlot.case).selectinload(Case.child))
    ).first()
    if not slot:
        raise ValueError("Slot not found")
    if slot_date is not None:
        slot.slot_date = slot_date
    if start_time is not None:
        slot.start_time = start_time
    if end_time is not None:
        slot.end_time = end_time
    if slot.end_time <= slot.start_time:
        raise ValueError("end_time must be after start_time")
    if status is not None:
        if status == SlotStatus.BLOCKED and slot.status == SlotStatus.BOOKED:
            raise ValueError("Cancel booking before blocking")
        slot.status = status
    if notes is not None:
        slot.notes = notes
    if slot.status == SlotStatus.BOOKED and slot.session_id:
        appt_booking.sync_session_for_slot(db, slot)
    slot.updated_at = datetime.now(timezone.utc)
    db.flush()
    return slot


def cancel_booking_with_reason(
    db: Session,
    slot_id: int,
    *,
    cancelled_by_user_id: Optional[int] = None,
    reason: Optional[str] = None,
    therapist_user_id: Optional[int] = None,
) -> TherapistSlot:
    slot = db.get(TherapistSlot, slot_id)
    if not slot:
        raise ValueError("Slot not found")
    if therapist_user_id and slot.therapist_user_id != therapist_user_id:
        raise ValueError("Access denied")
    if slot.status != SlotStatus.BOOKED:
        raise ValueError("Slot is not booked")
    appt_booking.cancel_session_for_slot(db, slot)
    slot.status = SlotStatus.CANCELLED
    slot.case_id = None
    slot.booked_by_user_id = None
    slot.booking_source = None
    slot.cancelled_at = datetime.now(timezone.utc)
    slot.cancelled_by_user_id = cancelled_by_user_id
    slot.cancellation_reason = reason
    slot.updated_at = datetime.now(timezone.utc)
    db.flush()
    return slot


def reschedule_appointment(
    db: Session,
    *,
    from_slot_id: int,
    to_slot_id: int,
    case_id: int,
    requested_by_user_id: int,
    requested_by_role: str,
    reason: Optional[str] = None,
    policy_check: Optional[policy.PolicyResult] = None,
) -> TherapistSlot:
    old_slot = db.get(TherapistSlot, from_slot_id)
    if not old_slot or old_slot.case_id != case_id:
        raise ValueError("Appointment not found")
    if policy_check and not policy_check.allowed:
        raise ValueError(policy_check.reason)

    new_slot = db.get(TherapistSlot, to_slot_id)
    if not new_slot or not cal.is_slot_bookable(db, new_slot):
        raise ValueError("Selected time is not available")
    if new_slot.therapist_user_id != old_slot.therapist_user_id:
        raise ValueError("Must reschedule with the same therapist")

    old_session_id = old_slot.session_id
    if old_slot.session_id:
        sess = db.get(TherapySession, old_slot.session_id)
        if sess:
            sess.status = SessionStatus.RESCHEDULED

    old_slot.status = SlotStatus.RESCHEDULED
    old_slot.case_id = None
    old_slot.booked_by_user_id = None
    old_slot.booking_source = None
    old_slot.session_id = None
    old_slot.rescheduled_to_slot_id = to_slot_id
    old_slot.updated_at = datetime.now(timezone.utc)

    source = BookingSource.PARENT
    if requested_by_role in ("ADMIN", "SUPER_ADMIN", "CASE_MANAGER"):
        source = BookingSource.ADMIN
    elif requested_by_role == "THERAPIST":
        source = BookingSource.THERAPIST

    booked = appt_booking.book_with_session(db, to_slot_id, case_id, requested_by_user_id, source)
    old_slot.rescheduled_to_slot_id = booked.id

    record = AppointmentReschedule(
        case_id=case_id,
        therapist_user_id=old_slot.therapist_user_id,
        from_slot_id=from_slot_id,
        to_slot_id=to_slot_id,
        from_session_id=old_session_id,
        to_session_id=booked.session_id,
        requested_by_user_id=requested_by_user_id,
        requested_by_role=requested_by_role,
        reason=reason,
    )
    db.add(record)
    db.flush()
    if requested_by_role == "PARENT":
        booked.approval_status = "PENDING_THERAPIST"
        parent_u = db.get(User, requested_by_user_id)
        appt_notify.notify_therapist_reschedule_pending(
            db,
            old_slot=old_slot,
            new_slot=booked,
            parent_name=parent_u.full_name if parent_u else "Parent",
        )
        appt_notify.notify_parents_reschedule_pending(db, old_slot=old_slot, new_slot=booked)
        db.flush()
    return booked


def assign_recurring_schedule(
    db: Session,
    *,
    case_id: int,
    therapist_user_id: int,
    weekdays: list[str],
    start_time: time,
    end_time: time,
    start_date: date,
    end_date: date,
    created_by_user_id: int,
) -> RecurringScheduleAssignment:
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date")
    if end_time <= start_time:
        raise ValueError("end_time must be after start_time")
    if not weekdays:
        raise ValueError("Select at least one weekday")
    if not get_active_assignment(db, case_id, therapist_user_id):
        raise ValueError("Therapist is not actively assigned to this case")

    case = db.get(Case, case_id)
    if not case:
        raise ValueError("Case not found")

    group_id = str(uuid.uuid4())
    duration = int(
        (datetime.combine(date.today(), end_time) - datetime.combine(date.today(), start_time)).total_seconds()
        // 60
    )
    existing_keys = cal._existing_slot_keys(db, therapist_user_id, start_date, end_date)
    booked_count = 0
    d = start_date
    while d <= end_date:
        if cal._weekday_key(d) not in weekdays:
            d += timedelta(days=1)
            continue
        if cal.is_day_on_leave(db, therapist_user_id, d):
            d += timedelta(days=1)
            continue
        key = (d, start_time)
        slot = db.scalars(
            select(TherapistSlot).where(
                TherapistSlot.therapist_user_id == therapist_user_id,
                TherapistSlot.slot_date == d,
                TherapistSlot.start_time == start_time,
            )
        ).first()
        if slot:
            if slot.status == SlotStatus.BOOKED:
                if slot.case_id == case_id:
                    d += timedelta(days=1)
                    continue
                raise ValueError(f"Slot on {d.isoformat()} is booked for another case")
            if slot.status not in (SlotStatus.AVAILABLE, SlotStatus.CANCELLED):
                d += timedelta(days=1)
                continue
            if slot.status == SlotStatus.CANCELLED:
                slot.status = SlotStatus.AVAILABLE
                slot.case_id = None
                slot.booked_by_user_id = None
                slot.booking_source = None
        else:
            slot = TherapistSlot(
                therapist_user_id=therapist_user_id,
                slot_date=d,
                start_time=start_time,
                end_time=end_time,
                status=SlotStatus.AVAILABLE,
                recurrence_group_id=group_id,
                slot_duration_minutes=duration,
            )
            db.add(slot)
            db.flush()
            existing_keys.add(key)

        if slot:
            slot.recurrence_group_id = group_id
            slot.end_time = end_time
            slot.slot_duration_minutes = duration
            appt_booking.book_with_session(db, slot.id, case_id, created_by_user_id, BookingSource.ADMIN)
            booked_count += 1
        d += timedelta(days=1)

    assignment_row = db.scalars(
        select(CaseAssignment).where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.therapist_user_id == therapist_user_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
    ).first()
    if assignment_row:
        assignment_row.booking_mode = BookingMode.FIXED.value
        assignment_row.set_fixed_weekdays(weekdays)
        assignment_row.fixed_start_time = start_time
        assignment_row.fixed_end_time = end_time
        assignment_row.fixed_recurrence_group_id = group_id

    record = RecurringScheduleAssignment(
        case_id=case_id,
        therapist_user_id=therapist_user_id,
        service_type=case.service_type,
        product_module=case.product_module,
        start_time=start_time,
        end_time=end_time,
        start_date=start_date,
        end_date=end_date,
        recurrence_group_id=group_id,
        created_by_user_id=created_by_user_id,
        booked_slot_count=booked_count,
    )
    record.set_weekdays(weekdays)
    db.add(record)
    db.flush()

    therapist = db.get(User, therapist_user_id)
    appt_notify.notify_recurring_assigned(db, case, therapist, record)
    return record


def preview_conflicts(
    db: Session,
    therapist_user_id: int,
    from_date: date,
    to_date: date,
) -> list[dict[str, Any]]:
    slots = db.scalars(
        select(TherapistSlot)
        .where(
            TherapistSlot.therapist_user_id == therapist_user_id,
            TherapistSlot.slot_date >= from_date,
            TherapistSlot.slot_date <= to_date,
            TherapistSlot.status == SlotStatus.BOOKED,
        )
        .options(selectinload(TherapistSlot.case).selectinload(Case.child))
    ).all()
    return [_slot_to_dict(s) for s in slots]


def mark_holiday_range(
    db: Session,
    therapist_user_id: int,
    from_date: date,
    to_date: date,
    *,
    notes: Optional[str] = None,
) -> int:
    """Mark each day in range with a HOLIDAY slot covering the template day window."""
    config = cal.get_or_create_template(db, therapist_user_id).get_config()
    days_cfg = config.get("days") or {}
    created = 0
    d = from_date
    while d <= to_date:
        day_cfg = days_cfg.get(cal._weekday_key(d), {})
        start = cal._parse_hm(day_cfg.get("start", "09:00"))
        end = cal._parse_hm(day_cfg.get("end", "18:00"))
        existing = db.scalars(
            select(TherapistSlot).where(
                TherapistSlot.therapist_user_id == therapist_user_id,
                TherapistSlot.slot_date == d,
                TherapistSlot.start_time == start,
            )
        ).first()
        if existing:
            if existing.status == SlotStatus.BOOKED:
                raise ValueError(f"Booked session on {d.isoformat()} — cancel or reschedule first")
            existing.status = SlotStatus.HOLIDAY
            existing.notes = notes
        else:
            db.add(
                TherapistSlot(
                    therapist_user_id=therapist_user_id,
                    slot_date=d,
                    start_time=start,
                    end_time=end,
                    status=SlotStatus.HOLIDAY,
                    notes=notes,
                )
            )
            created += 1
        d += timedelta(days=1)
    db.flush()
    return created


def confirm_pending_reschedule(db: Session, new_slot_id: int, therapist_user_id: int) -> TherapistSlot:
    new_slot = db.get(TherapistSlot, new_slot_id)
    if not new_slot or new_slot.therapist_user_id != therapist_user_id:
        raise ValueError("Access denied")
    if getattr(new_slot, "approval_status", "CONFIRMED") != "PENDING_THERAPIST":
        raise ValueError("No pending reschedule to confirm")
    record = db.scalars(
        select(AppointmentReschedule)
        .where(AppointmentReschedule.to_slot_id == new_slot_id)
        .order_by(AppointmentReschedule.id.desc())
    ).first()
    if not record:
        raise ValueError("Reschedule record not found")
    old_slot = db.get(TherapistSlot, record.from_slot_id)
    new_slot.approval_status = "CONFIRMED"
    db.flush()
    if old_slot:
        appt_notify.notify_parents_session_rescheduled(db, old_slot, new_slot)
    return new_slot


def decline_pending_parent_reschedule(db: Session, new_slot_id: int, therapist_user_id: int) -> TherapistSlot:
    new_slot = db.get(TherapistSlot, new_slot_id)
    if not new_slot or new_slot.therapist_user_id != therapist_user_id:
        raise ValueError("Access denied")
    if getattr(new_slot, "approval_status", "CONFIRMED") != "PENDING_THERAPIST":
        raise ValueError("No pending reschedule to decline")
    record = db.scalars(
        select(AppointmentReschedule)
        .where(AppointmentReschedule.to_slot_id == new_slot_id)
        .order_by(AppointmentReschedule.id.desc())
    ).first()
    if not record:
        raise ValueError("Reschedule record not found")
    old_slot = db.get(TherapistSlot, record.from_slot_id)
    case_id = record.case_id

    appt_booking.cancel_session_for_slot(db, new_slot)
    new_slot.status = SlotStatus.AVAILABLE
    new_slot.case_id = None
    new_slot.booked_by_user_id = None
    new_slot.booking_source = None
    new_slot.session_id = None
    new_slot.approval_status = "CONFIRMED"
    new_slot.cancelled_at = None
    new_slot.cancelled_by_user_id = None
    new_slot.cancellation_reason = None

    if old_slot:
        old_slot.status = SlotStatus.BOOKED
        old_slot.case_id = case_id
        old_slot.booked_by_user_id = record.requested_by_user_id
        old_slot.booking_source = BookingSource.PARENT
        old_slot.rescheduled_to_slot_id = None
        if record.from_session_id:
            sess = db.get(TherapySession, record.from_session_id)
            if sess:
                sess.status = SessionStatus.SCHEDULED
                sess.slot_id = old_slot.id
                old_slot.session_id = sess.id
        appt_booking.sync_session_for_slot(db, old_slot)
        parent_ids = appt_notify._parents_for_case(db, case_id)
        appt_notify.notify_parents_reschedule_declined(db, old_slot=old_slot, parent_user_ids=parent_ids)

    db.flush()
    return new_slot
