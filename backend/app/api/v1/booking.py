from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.permissions import RoleName, user_has_permission
from app.models.parent import ParentGuardian
from app.models.slot import BookingSource
from app.models.user import User
from app.core.permissions import case_scope_check
from app.services import appointment_booking_service as appt_booking
from app.services import appointment_notification_service as appt_notify
from app.services import case_service, slot_calendar_service as cal
from sqlalchemy import select

router = APIRouter(prefix="/booking", tags=["booking"])


class AppointmentCreate(BaseModel):
    slot_id: int
    case_id: int


def _parent_case_ids(db: Session, user: User) -> list[int]:
    from app.models.case import Case

    pg = db.scalars(select(ParentGuardian).where(ParentGuardian.user_id == user.id)).first()
    if not pg:
        return []
    child_ids = [c.id for c in pg.children]
    if not child_ids:
        return []
    cases = db.scalars(select(Case).where(Case.child_id.in_(child_ids))).all()
    return [c.id for c in cases]


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
    if user_has_permission(user, "slot.book_any"):
        if not case_scope_check(db, user, case):
            raise HTTPException(status_code=404, detail="Case not found")
        return cal.list_therapists_for_case(db, case_id)
    _require_parent_booking(user)
    allowed = _parent_case_ids(db, user)
    if case_id not in allowed:
        raise HTTPException(status_code=404, detail="Case not found")
    return cal.list_therapists_for_case(db, case_id)


@router.get("/availability")
def booking_availability(
    therapist_id: int = Query(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent_booking(user)
    return cal.list_available_slots_public(db, therapist_id, from_date, to_date)


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
