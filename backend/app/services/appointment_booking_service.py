from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.case import Case
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.slot import BookingSource, SlotStatus, TherapistSlot
from app.models.user import User
from app.services import appointment_policy as policy
from app.services import appointment_notification_service as notify
from app.services import slot_calendar_service as cal


def sync_session_for_slot(db: Session, slot: TherapistSlot) -> TherapySession | None:
    if slot.status != SlotStatus.BOOKED or not slot.case_id:
        if slot.session_id:
            sess = db.get(TherapySession, slot.session_id)
            if sess and sess.status == SessionStatus.SCHEDULED:
                sess.status = SessionStatus.CANCELLED
            slot.session_id = None
            db.flush()
        return None

    existing = None
    if slot.session_id:
        existing = db.get(TherapySession, slot.session_id)
    if not existing:
        existing = db.scalars(
            select(TherapySession).where(
                TherapySession.slot_id == slot.id,
                TherapySession.status == SessionStatus.SCHEDULED,
            )
        ).first()

    if existing:
        existing.scheduled_date = slot.slot_date
        existing.start_time = slot.start_time
        existing.end_time = slot.end_time
        existing.case_id = slot.case_id
        existing.therapist_user_id = slot.therapist_user_id
        slot.session_id = existing.id
        db.flush()
        return existing

    # Guard: adopt any bare SCHEDULED session for the same case+date+time
    # (created e.g. by seed before the slot was booked) rather than duplicating.
    orphan = db.scalars(
        select(TherapySession).where(
            TherapySession.case_id == slot.case_id,
            TherapySession.scheduled_date == slot.slot_date,
            TherapySession.start_time == slot.start_time,
            TherapySession.status == SessionStatus.SCHEDULED,
            TherapySession.slot_id.is_(None),
        )
    ).first()
    if orphan:
        orphan.end_time = slot.end_time
        orphan.therapist_user_id = slot.therapist_user_id
        orphan.slot_id = slot.id
        slot.session_id = orphan.id
        db.flush()
        return orphan

    sess = TherapySession(
        case_id=slot.case_id,
        therapist_user_id=slot.therapist_user_id,
        scheduled_date=slot.slot_date,
        start_time=slot.start_time,
        end_time=slot.end_time,
        status=SessionStatus.SCHEDULED,
        slot_id=slot.id,
        slot_duration_minutes=slot.slot_duration_minutes,
    )
    db.add(sess)
    db.flush()
    slot.session_id = sess.id
    db.flush()
    return sess


def cancel_session_for_slot(db: Session, slot: TherapistSlot) -> None:
    if slot.session_id:
        sess = db.get(TherapySession, slot.session_id)
        if sess and sess.status in (SessionStatus.SCHEDULED, SessionStatus.IN_PROGRESS):
            sess.status = SessionStatus.CANCELLED
    slot.session_id = None
    db.flush()


def book_with_session(
    db: Session,
    slot_id: int,
    case_id: int,
    booked_by_user_id: int,
    booking_source: BookingSource,
    *,
    require_therapist_approval: bool = False,
    admin_request_comment: str | None = None,
    force_unavailable: bool = False,
) -> TherapistSlot:
    slot = cal.book_slot(
        db,
        slot_id,
        case_id,
        booked_by_user_id,
        booking_source,
        require_therapist_approval=require_therapist_approval,
        admin_request_comment=admin_request_comment,
        force_unavailable=force_unavailable,
    )
    sync_session_for_slot(db, slot)
    return slot


def cancel_booking_with_session(
    db: Session,
    slot_id: int,
    therapist_user_id: int | None = None,
    *,
    cancelled_by_user_id: int | None = None,
    reason: str | None = None,
) -> TherapistSlot:
    from app.services import scheduling_service as sched

    return sched.cancel_booking_with_reason(
        db,
        slot_id,
        cancelled_by_user_id=cancelled_by_user_id,
        reason=reason,
        therapist_user_id=therapist_user_id,
    )


def _slot_visible_to_parent(
    db: Session,
    slot: TherapistSlot,
    case_id: int,
    assignment,
) -> bool:
    if slot.slot_date.isoformat() in cal._leave_dates(db, slot.therapist_user_id, slot.slot_date, slot.slot_date):
        return False
    duration = slot.slot_duration_minutes or 30
    if duration < policy.PARENT_SLOT_DURATION_MINUTES:
        return False
    if slot.status == SlotStatus.BOOKED:
        return slot.case_id == case_id
    if slot.status != SlotStatus.AVAILABLE or not cal.is_slot_bookable(db, slot):
        return False
    if not assignment or assignment.booking_mode != "FIXED":
        return True
    if assignment.fixed_recurrence_group_id:
        return slot.recurrence_group_id == assignment.fixed_recurrence_group_id
    return policy.slot_matches_fixed_window(slot, assignment)


def parent_calendar_view(
    db: Session,
    case_id: int,
    therapist_user_id: int,
    from_date: date,
    to_date: date,
    parent_user_id: int,
) -> dict[str, Any]:
    assignment = policy.get_active_assignment_for_case(db, case_id, therapist_user_id)
    cal.materialize_range(db, therapist_user_id, from_date, to_date)

    slots = db.scalars(
        select(TherapistSlot)
        .where(
            TherapistSlot.therapist_user_id == therapist_user_id,
            TherapistSlot.slot_date >= from_date,
            TherapistSlot.slot_date <= to_date,
        )
        .options(selectinload(TherapistSlot.case).selectinload(Case.child))
        .order_by(TherapistSlot.slot_date, TherapistSlot.start_time)
    ).all()

    leave_days = cal._leave_dates(db, therapist_user_id, from_date, to_date)
    visible: list[dict[str, Any]] = []

    for s in slots:
        if s.slot_date.isoformat() in leave_days:
            continue
        if not _slot_visible_to_parent(db, s, case_id, assignment):
            continue

        entry = cal._slot_to_dict(s)
        is_mine = s.status == SlotStatus.BOOKED and s.case_id == case_id
        entry["is_mine"] = is_mine
        entry["display_status"] = "mine" if is_mine else "available"
        if is_mine:
            cancel_r = policy.can_parent_cancel(s, case_id, db)
            reschedule_r = policy.can_parent_reschedule(s, case_id, db)
            entry["can_cancel"] = cancel_r.allowed
            entry["can_reschedule"] = reschedule_r.allowed
            entry["cancel_reason"] = cancel_r.reason if not cancel_r.allowed else ""
            entry["reschedule_reason"] = reschedule_r.reason if not reschedule_r.allowed else ""
            entry["reschedules_left"] = policy.reschedules_remaining(db, case_id, s.slot_date)
            entry["hours_until_start"] = round(policy.hours_until_start(s), 1)
            entry["session_id"] = s.session_id
        visible.append(entry)

    return {
        "case_id": case_id,
        "therapist_user_id": therapist_user_id,
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "booking": policy.assignment_booking_summary(assignment),
        "day_overlays": leave_days,
        "slots": visible,
        "reschedules_left": policy.reschedules_remaining(db, case_id, from_date),
    }


def parent_reschedule(
    db: Session,
    old_slot_id: int,
    new_slot_id: int,
    case_id: int,
    parent_user_id: int,
) -> TherapistSlot:
    old_slot = db.get(TherapistSlot, old_slot_id)
    if not old_slot or old_slot.case_id != case_id:
        raise ValueError("Appointment not found")
    check = policy.can_parent_reschedule(old_slot, case_id, db)
    if not check.allowed:
        raise ValueError(check.reason)

    new_slot = db.get(TherapistSlot, new_slot_id)
    if not new_slot or not cal.is_slot_bookable(db, new_slot):
        raise ValueError("Selected time is not available")
    if new_slot.therapist_user_id != old_slot.therapist_user_id:
        raise ValueError("Must reschedule with the same therapist")

    assignment = policy.get_active_assignment_for_case(db, case_id, new_slot.therapist_user_id)
    if assignment and assignment.booking_mode == "FIXED":
        if assignment.fixed_recurrence_group_id:
            if new_slot.recurrence_group_id != assignment.fixed_recurrence_group_id:
                raise ValueError("Outside your assigned time window")
        elif not policy.slot_matches_fixed_window(new_slot, assignment):
            raise ValueError("Outside your assigned time window")

    from app.services import scheduling_service as sched

    booked = sched.reschedule_appointment(
        db,
        from_slot_id=old_slot_id,
        to_slot_id=new_slot_id,
        case_id=case_id,
        requested_by_user_id=parent_user_id,
        requested_by_role="PARENT",
        policy_check=check,
    )

    usage = policy.get_usage(db, case_id, old_slot.slot_date)
    usage.reschedules_used += 1
    db.flush()

    return booked


def serialize_parent_appointment(db: Session, slot: TherapistSlot, case_id: int) -> dict[str, Any]:
    case = db.get(Case, slot.case_id) if slot.case_id else None
    therapist = db.get(User, slot.therapist_user_id)
    cancel_r = policy.can_parent_cancel(slot, case_id, db)
    reschedule_r = policy.can_parent_reschedule(slot, case_id, db)
    return {
        "id": slot.id,
        "caseId": case.case_code if case else None,
        "caseDbId": slot.case_id,
        "childName": case.child.full_name if case and case.child else None,
        "therapistName": therapist.full_name if therapist else None,
        "therapistUserId": slot.therapist_user_id,
        "slotDate": slot.slot_date.isoformat(),
        "startTime": slot.start_time.strftime("%H:%M"),
        "endTime": slot.end_time.strftime("%H:%M"),
        "bookingSource": slot.booking_source.value if slot.booking_source else None,
        "can_cancel": cancel_r.allowed,
        "can_reschedule": reschedule_r.allowed,
        "cancel_reason": cancel_r.reason if not cancel_r.allowed else "",
        "reschedule_reason": reschedule_r.reason if not reschedule_r.allowed else "",
        "reschedules_left": policy.reschedules_remaining(db, case_id, slot.slot_date),
        "hours_until_start": round(policy.hours_until_start(slot), 1),
        "session_id": slot.session_id,
        "approval_status": getattr(slot, "approval_status", None) or "CONFIRMED",
    }
