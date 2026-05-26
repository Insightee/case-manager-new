from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.permissions import get_active_assignment
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.leave import LeaveStatus, TherapistLeave
from app.models.schedule_template import TherapistScheduleTemplate, default_template_config
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.slot import BookingSource, SlotStatus, TherapistSlot
from app.services.therapist_portal_queries import fetch_calendar_sessions

WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _weekday_key(d: date) -> str:
    return WEEKDAY_KEYS[d.weekday()]


def _parse_hm(value: str) -> time:
    parts = value.strip().split(":")
    return time(int(parts[0]), int(parts[1]))


def normalize_day_config(day_cfg: dict[str, Any] | None) -> dict[str, Any]:
    """Support legacy single start/end per day and multi-window days (breaks)."""
    day_cfg = day_cfg or {}
    if day_cfg.get("windows"):
        windows = [
            {"start": w.get("start", "09:00"), "end": w.get("end", "18:00")}
            for w in day_cfg["windows"]
            if w.get("start") and w.get("end")
        ]
        if windows:
            return {"enabled": bool(day_cfg.get("enabled")), "windows": windows}
    return {
        "enabled": bool(day_cfg.get("enabled")),
        "windows": [
            {
                "start": day_cfg.get("start", "09:00"),
                "end": day_cfg.get("end", "18:00"),
            }
        ],
    }


def _materialize_day_windows(
    db: Session,
    therapist_user_id: int,
    d: date,
    windows: list[dict[str, Any]],
    duration: int,
    existing: set[tuple[date, time]],
) -> int:
    created = 0
    for window in windows:
        start = _parse_hm(window.get("start", "09:00"))
        end = _parse_hm(window.get("end", "18:00"))
        cursor = start
        while _add_minutes(cursor, duration) <= end:
            slot_end = _add_minutes(cursor, duration)
            key = (d, cursor)
            if key not in existing:
                db.add(
                    TherapistSlot(
                        therapist_user_id=therapist_user_id,
                        slot_date=d,
                        start_time=cursor,
                        end_time=slot_end,
                        status=SlotStatus.AVAILABLE,
                        slot_duration_minutes=duration,
                    )
                )
                existing.add(key)
                created += 1
            cursor = slot_end
    return created


def _add_minutes(t: time, minutes: int) -> time:
    dt = datetime.combine(date.today(), t) + timedelta(minutes=minutes)
    return dt.time()


def get_or_create_template(db: Session, therapist_user_id: int) -> TherapistScheduleTemplate:
    row = db.scalars(
        select(TherapistScheduleTemplate).where(TherapistScheduleTemplate.therapist_user_id == therapist_user_id)
    ).first()
    if row:
        return row
    row = TherapistScheduleTemplate(therapist_user_id=therapist_user_id)
    row.set_config(default_template_config())
    db.add(row)
    db.flush()
    return row


def upsert_template(db: Session, therapist_user_id: int, config: dict[str, Any]) -> TherapistScheduleTemplate:
    row = get_or_create_template(db, therapist_user_id)
    row.set_config(config)
    db.flush()
    return row


def _existing_slot_keys(db: Session, therapist_user_id: int, from_date: date, to_date: date) -> set[tuple[date, time]]:
    slots = db.scalars(
        select(TherapistSlot).where(
            TherapistSlot.therapist_user_id == therapist_user_id,
            TherapistSlot.slot_date >= from_date,
            TherapistSlot.slot_date <= to_date,
        )
    ).all()
    return {(s.slot_date, s.start_time) for s in slots}


def _leave_dates(
    db: Session, therapist_user_id: int, from_date: date, to_date: date
) -> dict[str, dict[str, Any]]:
    """Pending and approved leave block booking."""
    leaves = db.scalars(
        select(TherapistLeave).where(
            TherapistLeave.therapist_user_id == therapist_user_id,
            TherapistLeave.start_date <= to_date,
            TherapistLeave.end_date >= from_date,
            TherapistLeave.status.in_([LeaveStatus.PENDING, LeaveStatus.APPROVED]),
        )
    ).all()
    overlays: dict[str, dict[str, Any]] = {}
    for leave in leaves:
        d = max(leave.start_date, from_date)
        end = min(leave.end_date, to_date)
        while d <= end:
            overlays[d.isoformat()] = {
                "overlay": "leave",
                "leave_id": leave.id,
                "leave_type": leave.leave_type.value,
                "status": leave.status.value,
            }
            d += timedelta(days=1)
    return overlays


def is_day_on_leave(db: Session, therapist_user_id: int, day: date) -> bool:
    return day.isoformat() in _leave_dates(db, therapist_user_id, day, day)


def is_slot_bookable(db: Session, slot: TherapistSlot) -> bool:
    if slot.status not in (SlotStatus.AVAILABLE,):
        return False
    if is_day_on_leave(db, slot.therapist_user_id, slot.slot_date):
        return False
    return True


def materialize_range(
    db: Session,
    therapist_user_id: int,
    from_date: date,
    to_date: date,
    *,
    use_template: bool = True,
) -> int:
    if to_date < from_date:
        raise ValueError("to_date must be on or after from_date")
    config = get_or_create_template(db, therapist_user_id).get_config() if use_template else default_template_config()
    duration = int(config.get("slot_duration_minutes") or 30)
    days_cfg = config.get("days") or default_template_config()["days"]
    existing = _existing_slot_keys(db, therapist_user_id, from_date, to_date)
    created = 0
    d = from_date
    while d <= to_date:
        if is_day_on_leave(db, therapist_user_id, d):
            d += timedelta(days=1)
            continue
        day_cfg = normalize_day_config(days_cfg.get(_weekday_key(d), {}))
        if not day_cfg.get("enabled"):
            d += timedelta(days=1)
            continue
        created += _materialize_day_windows(
            db, therapist_user_id, d, day_cfg["windows"], duration, existing
        )
        d += timedelta(days=1)
    db.flush()
    return created


def create_recurring_slots(
    db: Session,
    therapist_user_id: int,
    *,
    weekday_keys: list[str],
    start_time: time,
    end_time: time,
    from_date: date,
    weeks: int = 4,
    status: SlotStatus = SlotStatus.AVAILABLE,
) -> tuple[str, int]:
    if end_time <= start_time:
        raise ValueError("end_time must be after start_time")
    group_id = str(uuid.uuid4())
    duration = int((datetime.combine(date.today(), end_time) - datetime.combine(date.today(), start_time)).total_seconds() // 60)
    existing = _existing_slot_keys(db, therapist_user_id, from_date, from_date + timedelta(days=weeks * 7))
    created = 0
    for week in range(weeks):
        for day_offset in range(7):
            d = from_date + timedelta(days=week * 7 + day_offset)
            if _weekday_key(d) not in weekday_keys:
                continue
            if is_day_on_leave(db, therapist_user_id, d):
                continue
            key = (d, start_time)
            if key in existing:
                continue
            db.add(
                TherapistSlot(
                    therapist_user_id=therapist_user_id,
                    slot_date=d,
                    start_time=start_time,
                    end_time=end_time,
                    status=status,
                    recurrence_group_id=group_id,
                    slot_duration_minutes=duration,
                )
            )
            existing.add(key)
            created += 1
    db.flush()
    return group_id, created


def delete_recurring_group(db: Session, therapist_user_id: int, group_id: str, *, future_only: bool = True) -> int:
    stmt = select(TherapistSlot).where(
        TherapistSlot.therapist_user_id == therapist_user_id,
        TherapistSlot.recurrence_group_id == group_id,
    )
    if future_only:
        stmt = stmt.where(TherapistSlot.slot_date >= date.today())
    slots = list(db.scalars(stmt).all())
    for slot in slots:
        if slot.status == SlotStatus.BOOKED:
            raise ValueError("Cannot delete recurring group with booked slots in range")
        db.delete(slot)
    db.flush()
    return len(slots)


def _slot_to_dict(slot: TherapistSlot, case: Case | None = None) -> dict[str, Any]:
    child_name = None
    case_code = None
    product_module = None
    service_type = None
    resolved_case = case or slot.case
    if resolved_case:
        case_code = resolved_case.case_code
        child_name = resolved_case.child.full_name if resolved_case.child else None
        product_module = getattr(resolved_case, "product_module", None)
        service_type = getattr(resolved_case, "service_type", None)
    return {
        "id": slot.id,
        "therapist_user_id": slot.therapist_user_id,
        "slot_date": slot.slot_date.isoformat(),
        "start_time": slot.start_time.strftime("%H:%M"),
        "end_time": slot.end_time.strftime("%H:%M"),
        "status": slot.status.value,
        "notes": slot.notes,
        "case_id": slot.case_id,
        "case_code": case_code,
        "child_name": child_name,
        "product_module": product_module,
        "service_type": service_type,
        "booked_by_user_id": slot.booked_by_user_id,
        "booking_source": slot.booking_source.value if slot.booking_source else None,
        "recurrence_group_id": slot.recurrence_group_id,
        "slot_duration_minutes": slot.slot_duration_minutes,
        "session_id": slot.session_id,
        "rescheduled_to_slot_id": slot.rescheduled_to_slot_id,
        "approval_status": getattr(slot, "approval_status", None) or "CONFIRMED",
        "leave_block_leave_id": getattr(slot, "leave_block_leave_id", None),
        "created_at": slot.created_at.isoformat() if slot.created_at else None,
        "updated_at": slot.updated_at.isoformat() if slot.updated_at else None,
    }


def _session_to_calendar_dict(session: TherapySession) -> dict[str, Any]:
    case = session.case
    child_name = case.child.full_name if case and case.child else None
    case_code = case.case_code if case else None
    start = session.start_time.strftime("%H:%M") if session.start_time else "09:00"
    end = session.end_time.strftime("%H:%M") if session.end_time else start
    status = (
        "IN_PROGRESS"
        if session.status == SessionStatus.IN_PROGRESS
        else "SESSION"
    )
    return {
        "event_type": "session",
        "id": f"session-{session.id}",
        "session_id": session.id,
        "slot_id": session.slot_id,
        "slot_date": session.scheduled_date.isoformat(),
        "start_time": start,
        "end_time": end,
        "status": status,
        "case_id": session.case_id,
        "case_code": case_code,
        "child_name": child_name,
        "mode": session.mode.value if session.mode else None,
    }


def get_calendar_view(
    db: Session,
    therapist_user_id: int,
    from_date: date,
    to_date: date,
    *,
    case_id: int | None = None,
) -> dict[str, Any]:
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
    linked_slot_ids = {s.id for s in slots if s.session_id}
    session_rows = fetch_calendar_sessions(
        db, therapist_user_id, from_date, to_date, case_id=case_id
    )
    sessions = [
        _session_to_calendar_dict(sess)
        for sess in session_rows
        if not (sess.slot_id and sess.slot_id in linked_slot_ids)
    ]
    template = get_or_create_template(db, therapist_user_id)
    return {
        "therapist_user_id": therapist_user_id,
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "template": template.get_config(),
        "day_overlays": _leave_dates(db, therapist_user_id, from_date, to_date),
        "slots": [_slot_to_dict(s) for s in slots],
        "sessions": sessions,
    }


def book_slot(
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
    slot = db.scalars(
        select(TherapistSlot)
        .where(TherapistSlot.id == slot_id)
        .options(selectinload(TherapistSlot.case).selectinload(Case.child))
    ).first()
    if not slot:
        raise ValueError("Slot not found")
    if not force_unavailable and not is_slot_bookable(db, slot):
        raise ValueError("Slot is not available for booking")
    if slot.status == SlotStatus.BOOKED and slot.case_id != case_id and not force_unavailable:
        raise ValueError("Slot is already booked for another case")
    if not get_active_assignment(db, case_id, slot.therapist_user_id):
        raise ValueError("Therapist is not actively assigned to this case")
    case = db.get(Case, case_id)
    if not case:
        raise ValueError("Case not found")
    slot.status = SlotStatus.BOOKED
    slot.case_id = case_id
    slot.booked_by_user_id = booked_by_user_id
    slot.booking_source = booking_source
    if require_therapist_approval or force_unavailable:
        slot.approval_status = "PENDING_THERAPIST"
        if admin_request_comment:
            slot.notes = admin_request_comment
    else:
        slot.approval_status = "CONFIRMED"
    db.flush()
    return slot


def cancel_booking(db: Session, slot_id: int, therapist_user_id: int | None = None) -> TherapistSlot:
    slot = db.get(TherapistSlot, slot_id)
    if not slot:
        raise ValueError("Slot not found")
    if therapist_user_id and slot.therapist_user_id != therapist_user_id:
        raise ValueError("Access denied")
    if slot.status != SlotStatus.BOOKED:
        raise ValueError("Slot is not booked")
    slot.status = SlotStatus.CANCELLED
    slot.case_id = None
    slot.booked_by_user_id = None
    slot.booking_source = None
    slot.cancelled_at = datetime.now(timezone.utc)
    db.flush()
    return slot


def block_slot(db: Session, slot_id: int) -> TherapistSlot:
    slot = db.get(TherapistSlot, slot_id)
    if not slot:
        raise ValueError("Slot not found")
    if slot.status == SlotStatus.BOOKED:
        raise ValueError("Cannot block a booked slot; cancel booking first")
    slot.status = SlotStatus.BLOCKED
    db.flush()
    return slot


def list_bookable_cases_for_therapist(db: Session, therapist_user_id: int) -> list[dict[str, Any]]:
    assignments = db.scalars(
        select(CaseAssignment)
        .where(
            CaseAssignment.therapist_user_id == therapist_user_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
        .options(selectinload(CaseAssignment.case).selectinload(Case.child))
    ).all()
    from app.services.address_service import case_service_address_read, is_homecare_case

    result = []
    for a in assignments:
        if a.case:
            svc = case_service_address_read(a.case)
            entry = {
                "case_id": a.case_id,
                "case_code": a.case.case_code,
                "child_name": a.case.child.full_name if a.case.child else None,
                "product_module": a.case.product_module,
                "is_homecare": is_homecare_case(a.case),
            }
            if svc:
                entry["service_address"] = svc.model_dump()
                entry["maps_url"] = svc.maps_url
            result.append(entry)
    return result


def list_available_slots_public(
    db: Session,
    therapist_user_id: int,
    from_date: date,
    to_date: date,
) -> list[dict[str, Any]]:
    """Parent-facing: only AVAILABLE slots on non-leave days."""
    slots = db.scalars(
        select(TherapistSlot).where(
            TherapistSlot.therapist_user_id == therapist_user_id,
            TherapistSlot.slot_date >= from_date,
            TherapistSlot.slot_date <= to_date,
            TherapistSlot.status == SlotStatus.AVAILABLE,
        )
    ).all()
    leave_days = _leave_dates(db, therapist_user_id, from_date, to_date)
    return [
        {
            "id": s.id,
            "slot_date": s.slot_date.isoformat(),
            "start_time": s.start_time.strftime("%H:%M"),
            "end_time": s.end_time.strftime("%H:%M"),
        }
        for s in slots
        if s.slot_date.isoformat() not in leave_days
    ]


def list_therapists_for_case(db: Session, case_id: int) -> list[dict[str, Any]]:
    assignments = db.scalars(
        select(CaseAssignment).where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
    ).all()
    from app.models.user import User

    result = []
    for a in assignments:
        user = db.get(User, a.therapist_user_id)
        if user:
            result.append(
                {
                    "therapist_user_id": user.id,
                    "full_name": user.full_name,
                    "email": user.email,
                }
            )
    return result
