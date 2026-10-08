from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.module_write import ensure_case_transition_allows_booking
from app.models.case import Case
from app.models.slot import TherapistSlot
from app.core.permissions import RoleName, user_has_permission, case_scope_check
from app.models.slot import BookingSource
from app.models.user import User
from app.services import availability_service
from app.services import appointment_booking_service as appt_booking
from app.services import appointment_notification_service as appt_notify
from app.services import case_service, slot_calendar_service as cal

router = APIRouter(prefix="/booking", tags=["booking"])


class AppointmentCreate(BaseModel):
    slot_id: int
    case_id: int


def _parent_case_ids(db: Session, user: User) -> list[int]:
    from app.services import parent_service

    return [row["id"] for row in parent_service.list_parent_cases(db, user)]


def _require_parent_booking(user: User) -> None:
    if RoleName.PARENT.value not in user.role_names:
        raise HTTPException(status_code=403, detail="Parent access only")
    if not user_has_permission(user, "slot.book_parent"):
        raise HTTPException(status_code=403, detail="Booking not permitted")


@router.get("/therapists")
def list_therapists_for_booking(
    case_id: int = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if user_has_permission(user, "slot.book_any") or case_scope_check(db, user, case):
        return cal.list_therapists_for_case(db, case_id)
    _require_parent_booking(user)
    allowed = _parent_case_ids(db, user)
    if case_id not in allowed:
        raise HTTPException(status_code=404, detail="Case not found")
    return cal.list_therapists_for_case(db, case_id)


@router.get("/slots")
def get_booking_slots(
    case_id: int = Query(...),
    date: date = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if not (user_has_permission(user, "slot.book_any") or case_scope_check(db, user, case)):
        raise HTTPException(status_code=403, detail="Access denied")

    from app.services import parent_service

    parent_uid = parent_service.primary_parent_user_id_for_child(db, case.child_id) if case.child_id else None
    
    therapists = cal.list_therapists_for_case(db, case_id)
    therapist_ids = [t["therapist_user_id"] for t in therapists]

    attendees = []
    if case.case_manager_user_id:
        attendees.append(case.case_manager_user_id)
    if "THERAPIST" in user.role_names:
        attendees.append(user.id)
    else:
        for t_id in therapist_ids:
            attendees.append(t_id)
    if parent_uid:
        attendees.append(parent_uid)

    return availability_service.free_slots(
        db,
        attendees,
        date,
        date,
        30,
        user,
    )



@router.get("/availability")
def booking_availability(
    therapist_id: int = Query(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    case_id: Optional[int] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if RoleName.PARENT.value in user.role_names:
        _require_parent_booking(user)
        if case_id is not None and case_id not in _parent_case_ids(db, user):
            # Handover filtering is case-specific; don't let a parent probe other families' cases.
            raise HTTPException(status_code=404, detail="Case not found")
    elif case_id is not None:
        case = case_service.get_case(db, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        if not (user_has_permission(user, "slot.book_any") or case_scope_check(db, user, case)):
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        _require_parent_booking(user)
    return cal.list_available_slots_public(
        db, therapist_id, from_date, to_date, case_id=case_id
    )


@router.post("/appointments", status_code=status.HTTP_201_CREATED)
def create_appointment(
    payload: AppointmentCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent_booking(user)
    allowed = _parent_case_ids(db, user)
    if payload.case_id not in allowed:
        raise HTTPException(status_code=404, detail="Case not found")
    slot_row = db.get(TherapistSlot, payload.slot_id)
    if not slot_row:
        raise HTTPException(status_code=404, detail="Slot not found")
    case = db.get(Case, payload.case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    ensure_case_transition_allows_booking(
        case,
        db,
        slot_date=slot_row.slot_date,
        therapist_user_id=slot_row.therapist_user_id,
    )
    try:
        slot = appt_booking.book_with_session(
            db, payload.slot_id, payload.case_id, user.id, BookingSource.PARENT
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    appt_notify.notify_therapist_parent_booked(db, slot, parent_name=user.full_name)
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="book", entity_type="slot", entity_id=payload.slot_id, **meta)
    db.commit()
    return appt_booking.serialize_parent_appointment(db, slot, payload.case_id)
