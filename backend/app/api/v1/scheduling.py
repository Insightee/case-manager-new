from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta, time, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import user_has_permission
from app.models.case import Case
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.slot import BookingSource, SlotStatus, TherapistSlot
from app.models.user import InviteToken, User
from app.services import appointment_booking_service as appt_booking
from app.services import appointment_notification_service as appt_notify
from app.services import appointment_policy as policy
from app.services import scheduling_service as sched
from app.services import slot_calendar_service as cal

router = APIRouter(prefix="/scheduling", tags=["scheduling"])


class SlotCreate(BaseModel):
    slot_date: date
    start_time: time
    end_time: time
    notes: Optional[str] = None
    therapist_id: Optional[int] = None


class SlotPatch(BaseModel):
    slot_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    status: Optional[SlotStatus] = None
    notes: Optional[str] = None


class AssignRecurringRequest(BaseModel):
    case_id: int
    therapist_user_id: int
    weekdays: list[str] = Field(..., min_length=1)
    start_time: time
    end_time: time
    start_date: date
    end_date: date


class RescheduleRequest(BaseModel):
    from_slot_id: int
    to_slot_id: int
    case_id: int
    reason: Optional[str] = None


class HolidayRequest(BaseModel):
    from_date: date
    to_date: date
    notes: Optional[str] = None
    therapist_id: Optional[int] = None


class BookSlotRequest(BaseModel):
    case_id: int
    require_therapist_approval: bool = False
    admin_request_comment: Optional[str] = None
    force_unavailable: bool = False


class InviteClientRequest(BaseModel):
    client_name: str = Field(..., min_length=1, max_length=255)
    client_email: EmailStr
    child_name: Optional[str] = None
    client_phone: Optional[str] = None


class CancelSlotRequest(BaseModel):
    reason: Optional[str] = None


def _resolve_therapist_id(user: User, therapist_id: Optional[int]) -> int:
    if therapist_id is not None:
        if therapist_id != user.id and not user_has_permission(user, "slot.read"):
            raise HTTPException(status_code=403, detail="Access denied")
        return therapist_id
    return user.id


def _serialise(slot: TherapistSlot) -> dict[str, Any]:
    return cal._slot_to_dict(slot)


@router.get("/calendar")
def get_calendar(
    from_date: date = Query(...),
    to_date: date = Query(...),
    therapist_id: Optional[int] = None,
    case_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tid = _resolve_therapist_id(user, therapist_id)
    from app.services.cm_meeting_service import fetch_cm_meetings_for_therapist_calendar, meeting_to_calendar_dict

    cal = sched.get_unified_calendar(db, tid, from_date, to_date, case_id=case_id)
    cm_rows = fetch_cm_meetings_for_therapist_calendar(
        db, tid, from_date=from_date, to_date=to_date, case_id=case_id
    )
    cal["cm_meetings"] = [meeting_to_calendar_dict(m, db) for m in cm_rows]
    return cal


@router.post("/slots", status_code=status.HTTP_201_CREATED)
def create_slot(
    payload: SlotCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tid = _resolve_therapist_id(user, payload.therapist_id)
    if tid != user.id and not user_has_permission(user, "slot.book_any"):
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        slot = sched.create_slot(
            db,
            tid,
            slot_date=payload.slot_date,
            start_time=payload.start_time,
            end_time=payload.end_time,
            notes=payload.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="create", entity_type="slot", entity_id=slot.id, **meta)
    db.commit()
    db.refresh(slot)
    return _serialise(slot)


@router.patch("/slots/{slot_id}")
def patch_slot(
    slot_id: int,
    payload: SlotPatch,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    slot = db.get(TherapistSlot, slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    if slot.therapist_user_id != user.id and not user_has_permission(user, "slot.read"):
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        slot = sched.update_slot(
            db,
            slot_id,
            slot_date=payload.slot_date,
            start_time=payload.start_time,
            end_time=payload.end_time,
            status=payload.status,
            notes=payload.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="update", entity_type="slot", entity_id=slot_id, **meta)
    db.commit()
    db.refresh(slot)
    return _serialise(slot)


@router.delete("/slots/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_slot(
    slot_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    slot = db.get(TherapistSlot, slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    if slot.therapist_user_id != user.id and not user_has_permission(user, "slot.read"):
        raise HTTPException(status_code=403, detail="Access denied")
    if slot.status == SlotStatus.BOOKED:
        raise HTTPException(status_code=400, detail="Cancel booking before deleting")
    db.delete(slot)
    db.commit()


@router.post("/slots/{slot_id}/book")
def book_slot(
    slot_id: int,
    payload: BookSlotRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    slot = db.get(TherapistSlot, slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    if slot.therapist_user_id == user.id and user_has_permission(user, "slot.book"):
        source = BookingSource.THERAPIST
    elif user_has_permission(user, "slot.book_any"):
        source = BookingSource.ADMIN
    else:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    try:
        slot = appt_booking.book_with_session(
            db,
            slot_id,
            payload.case_id,
            user.id,
            source,
            require_therapist_approval=payload.require_therapist_approval,
            admin_request_comment=payload.admin_request_comment,
            force_unavailable=payload.force_unavailable and source == BookingSource.ADMIN,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if slot.approval_status == "PENDING_THERAPIST" and source == BookingSource.ADMIN:
        appt_notify.notify_therapist_admin_booking_pending(
            db,
            slot,
            admin_name=user.full_name,
            comment=payload.admin_request_comment,
        )
    if source == BookingSource.THERAPIST:
        appt_notify.notify_parents_therapist_booked(db, slot, therapist_name=user.full_name)
    elif source == BookingSource.ADMIN:
        th = db.get(User, slot.therapist_user_id)
        appt_notify.notify_parents_therapist_booked(
            db, slot, therapist_name=th.full_name if th else user.full_name
        )
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="book", entity_type="slot", entity_id=slot_id, **meta)
    db.commit()
    db.refresh(slot)
    return _serialise(slot)


@router.post("/slots/{slot_id}/cancel")
def cancel_slot_booking(
    slot_id: int,
    request: Request,
    payload: CancelSlotRequest = CancelSlotRequest(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    slot = db.get(TherapistSlot, slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    if slot.therapist_user_id != user.id and not user_has_permission(user, "slot.book_any"):
        raise HTTPException(status_code=403, detail="Access denied")
    slot_snapshot = db.get(TherapistSlot, slot_id)
    case_id_before = slot_snapshot.case_id if slot_snapshot else None
    try:
        slot = sched.cancel_booking_with_reason(
            db,
            slot_id,
            cancelled_by_user_id=user.id,
            reason=payload.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if case_id_before and slot_snapshot and slot_snapshot.therapist_user_id == user.id:
        appt_notify.notify_parents_session_cancelled(
            db,
            slot_snapshot,
            cancelled_by_name=user.full_name,
            reason=payload.reason or "Your therapist cancelled the session",
        )
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="cancel_booking", entity_type="slot", entity_id=slot_id, **meta)
    db.commit()
    return _serialise(slot)


@router.post("/slots/{slot_id}/block")
def block_slot(
    slot_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    slot = db.get(TherapistSlot, slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    if slot.therapist_user_id != user.id and not user_has_permission(user, "slot.read"):
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        slot = cal.block_slot(db, slot_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return _serialise(slot)


@router.post("/assign-recurring/preview")
def assign_recurring_preview(
    payload: AssignRecurringRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    can_admin = user_has_permission(user, "slot.book_any")
    can_self = user_has_permission(user, "slot.book") and payload.therapist_user_id == user.id
    if not can_admin and not can_self:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    try:
        return sched.preview_recurring_schedule(
            db,
            case_id=payload.case_id,
            therapist_user_id=payload.therapist_user_id,
            weekdays=payload.weekdays,
            start_time=payload.start_time,
            end_time=payload.end_time,
            start_date=payload.start_date,
            end_date=payload.end_date,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/assign-recurring", status_code=status.HTTP_201_CREATED)
def assign_recurring(
    payload: AssignRecurringRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    can_admin = user_has_permission(user, "slot.book_any")
    can_self = user_has_permission(user, "slot.book") and payload.therapist_user_id == user.id
    if not can_admin and not can_self:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    try:
        record = sched.assign_recurring_schedule(
            db,
            case_id=payload.case_id,
            therapist_user_id=payload.therapist_user_id,
            weekdays=payload.weekdays,
            start_time=payload.start_time,
            end_time=payload.end_time,
            start_date=payload.start_date,
            end_date=payload.end_date,
            created_by_user_id=user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="assign_recurring",
        entity_type="recurring_schedule",
        entity_id=record.id,
        **meta,
    )
    db.commit()
    return {
        "id": record.id,
        "recurrence_group_id": record.recurrence_group_id,
        "booked_slot_count": record.booked_slot_count,
        "case_id": record.case_id,
        "therapist_user_id": record.therapist_user_id,
        "weekdays": record.get_weekdays(),
        "start_date": record.start_date.isoformat(),
        "end_date": record.end_date.isoformat(),
    }


@router.post("/reschedule")
def reschedule(
    payload: RescheduleRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    role_names = user.role_names
    role = role_names[0] if role_names else "USER"
    policy_check = None
    if user_has_permission(user, "slot.book_parent") and not user_has_permission(user, "slot.book_any"):
        old_slot = db.get(TherapistSlot, payload.from_slot_id)
        if not old_slot:
            raise HTTPException(status_code=404, detail="Appointment not found")
        policy_check = policy.can_parent_reschedule(old_slot, payload.case_id, db)
    try:
        new_slot = sched.reschedule_appointment(
            db,
            from_slot_id=payload.from_slot_id,
            to_slot_id=payload.to_slot_id,
            case_id=payload.case_id,
            requested_by_user_id=user.id,
            requested_by_role=role,
            reason=payload.reason,
            policy_check=policy_check,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return _serialise(new_slot)


@router.get("/conflicts")
def list_conflicts(
    from_date: date = Query(...),
    to_date: date = Query(...),
    therapist_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tid = _resolve_therapist_id(user, therapist_id)
    return {"booked_slots": sched.preview_conflicts(db, tid, from_date, to_date)}


@router.post("/holiday")
def mark_holiday(
    payload: HolidayRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tid = _resolve_therapist_id(user, payload.therapist_id)
    try:
        created = sched.mark_holiday_range(
            db, tid, payload.from_date, payload.to_date, notes=payload.notes
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return {"created": created, "therapist_user_id": tid}


@router.get("/template")
def get_template(
    therapist_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tid = _resolve_therapist_id(user, therapist_id)
    row = cal.get_or_create_template(db, tid)
    db.commit()
    return {"therapist_user_id": tid, "config": row.get_config()}


@router.patch("/template")
def update_template(
    payload: dict[str, Any],
    therapist_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tid = _resolve_therapist_id(user, therapist_id)
    config = payload.get("config") if "config" in payload else payload
    row = cal.upsert_template(db, tid, config)
    db.commit()
    return {"therapist_user_id": tid, "config": row.get_config()}


@router.post("/template/materialize")
def materialize(
    from_date: date = Query(...),
    to_date: date = Query(...),
    therapist_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tid = _resolve_therapist_id(user, therapist_id)
    try:
        created = cal.materialize_range(db, tid, from_date, to_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return {"created": created, "therapist_user_id": tid}


@router.post("/slots/{slot_id}/invite-client")
def invite_client_to_slot(
    slot_id: int,
    payload: InviteClientRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    slot = db.get(TherapistSlot, slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    if slot.therapist_user_id != user.id:
        raise HTTPException(status_code=403, detail="Only the slot owner can invite a client")
    if slot.status != SlotStatus.AVAILABLE:
        raise HTTPException(status_code=400, detail="Slot must be available")
    token = secrets.token_urlsafe(32)
    invite = InviteToken(
        email=str(payload.client_email).lower(),
        role_name="PARENT",
        module_assignments=[],
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        created_by_user_id=user.id,
        invite_metadata={
            "pending_slot_id": slot_id,
            "client_name": payload.client_name.strip(),
            "child_name": payload.child_name.strip() if payload.child_name else None,
            "client_phone": payload.client_phone.strip() if payload.client_phone else None,
            "therapist_user_id": user.id,
        },
    )
    db.add(invite)
    slot.status = SlotStatus.BLOCKED
    slot.notes = f"Pending client invite: {payload.client_name.strip()}"
    db.flush()
    url = f"{settings.frontend_url}/invite/{token}"
    appt_notify.notify_admins_walk_in_invite(
        db,
        therapist_name=user.full_name,
        client_name=payload.client_name.strip(),
        client_email=str(payload.client_email).lower(),
        slot_when=f"{slot.slot_date.isoformat()} {slot.start_time.strftime('%H:%M')}",
    )
    from app.services import email_service

    email_service.invite_portal_email(
        to=str(payload.client_email).lower(),
        invite_url=url,
        therapist_name=user.full_name,
        client_name=payload.client_name.strip(),
        slot_when=f"{slot.slot_date.isoformat()} {slot.start_time.strftime('%H:%M')}",
    )
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="invite_client_slot", entity_type="slot", entity_id=slot_id, **meta)
    db.commit()
    db.refresh(slot)
    return {"invite_sent": True, "invite_url": url, "slot": _serialise(slot), "expires_at": invite.expires_at.isoformat()}


@router.post("/slots/{slot_id}/confirm-reschedule")
def confirm_reschedule(
    slot_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        slot = sched.confirm_pending_reschedule(db, slot_id, user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="confirm_reschedule", entity_type="slot", entity_id=slot_id, **meta)
    db.commit()
    db.refresh(slot)
    return _serialise(slot)


@router.post("/slots/{slot_id}/decline-reschedule")
def decline_reschedule(
    slot_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        slot = sched.decline_pending_parent_reschedule(db, slot_id, user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="decline_reschedule", entity_type="slot", entity_id=slot_id, **meta)
    db.commit()
    db.refresh(slot)
    return _serialise(slot)


# ---------------------------------------------------------------------------
# Shadow-care bulk block scheduling
# ---------------------------------------------------------------------------

class ShadowBlockRequest(BaseModel):
    case_id: int
    therapist_user_id: int
    dates: list[date] = Field(..., min_length=1)
    start_time: time
    duration_hours: float = Field(..., gt=0, le=24)


def _shadow_conflict_check(
    db: Session,
    therapist_user_id: int,
    check_date: date,
    start: time,
    end: time,
) -> list[dict]:
    """Return any BOOKED/BLOCKED slots for the therapist that overlap the window."""
    from sqlalchemy import select as sa_select
    from datetime import datetime, timezone

    slots = db.scalars(
        sa_select(TherapistSlot).where(
            TherapistSlot.therapist_user_id == therapist_user_id,
            TherapistSlot.slot_date == check_date,
            TherapistSlot.status.in_([SlotStatus.BOOKED, SlotStatus.BLOCKED]),
        )
    ).all()
    conflicts = []
    for s in slots:
        # overlap when proposed_start < slot_end AND proposed_end > slot_start
        if start < s.end_time and end > s.start_time:
            conflicts.append({
                "slot_id": s.id,
                "date": check_date.isoformat(),
                "start": s.start_time.strftime("%H:%M"),
                "end": s.end_time.strftime("%H:%M"),
                "status": s.status.value,
            })
    return conflicts


@router.get("/shadow-block/preview")
def shadow_block_preview(
    therapist_user_id: int = Query(...),
    dates: list[date] = Query(...),
    start_time: time = Query(...),
    duration_hours: float = Query(..., gt=0, le=24),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return any conflicting slots without committing changes."""
    if not user_has_permission(user, "case.read.all"):
        raise HTTPException(status_code=403, detail="Admin access required")
    from datetime import datetime, timedelta

    end_time = (datetime.combine(date.today(), start_time) + timedelta(hours=duration_hours)).time()
    all_conflicts: list[dict] = []
    for d in dates:
        all_conflicts.extend(_shadow_conflict_check(db, therapist_user_id, d, start_time, end_time))
    return {"conflicts": all_conflicts}


@router.post("/shadow-block", status_code=status.HTTP_201_CREATED)
def create_shadow_block(
    payload: ShadowBlockRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bulk-create BOOKED shadow-care slots (and linked sessions) for a therapist."""
    if not user_has_permission(user, "case.read.all"):
        raise HTTPException(status_code=403, detail="Admin access required")

    case = db.get(Case, payload.case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.product_module != "shadow_support":
        raise HTTPException(status_code=400, detail="Shadow block is only for shadow_support cases")

    from datetime import datetime, timedelta
    from sqlalchemy import select as sa_select

    duration_mins = int(payload.duration_hours * 60)
    end_time = (datetime.combine(date.today(), payload.start_time) + timedelta(hours=payload.duration_hours)).time()

    # Conflict check across all requested dates
    all_conflicts: list[dict] = []
    for d in payload.dates:
        all_conflicts.extend(_shadow_conflict_check(db, payload.therapist_user_id, d, payload.start_time, end_time))
    if all_conflicts:
        raise HTTPException(status_code=400, detail={"message": "Scheduling conflicts detected", "conflicts": all_conflicts})

    created = []
    for d in payload.dates:
        slot = TherapistSlot(
            therapist_user_id=payload.therapist_user_id,
            slot_date=d,
            start_time=payload.start_time,
            end_time=end_time,
            slot_duration_minutes=duration_mins,
            status=SlotStatus.BOOKED,
            case_id=payload.case_id,
            booking_source=BookingSource.ADMIN,
        )
        db.add(slot)
        db.flush()
        session = appt_booking.sync_session_for_slot(db, slot)
        if session:
            session.slot_duration_minutes = duration_mins
        created.append(_serialise(slot))

    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="shadow_block",
        entity_type="slot",
        entity_id=None,
        new_value={"case_id": payload.case_id, "dates": [str(d) for d in payload.dates]},
        **meta,
    )
    db.commit()
    return {"created": created}
