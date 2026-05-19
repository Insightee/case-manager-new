from __future__ import annotations

from datetime import date, time
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.permissions import user_has_permission
from app.models.slot import BookingSource, SlotStatus, TherapistSlot
from app.models.user import User
from app.services import slot_calendar_service as cal

router = APIRouter(prefix="/slots", tags=["slots"])


class SlotCreate(BaseModel):
    slot_date: date
    start_time: time
    end_time: time
    notes: Optional[str] = None


class SlotUpdate(BaseModel):
    status: Optional[SlotStatus] = None
    notes: Optional[str] = None


class TemplateUpdate(BaseModel):
    config: dict[str, Any]


class MaterializeRequest(BaseModel):
    from_date: date
    to_date: date
    therapist_id: Optional[int] = None


class RecurringCreate(BaseModel):
    weekday_keys: list[str] = Field(..., min_length=1)
    start_time: time
    end_time: time
    from_date: date
    weeks: int = Field(4, ge=1, le=52)
    therapist_id: Optional[int] = None


class BookSlotRequest(BaseModel):
    case_id: int


def _resolve_therapist_id(user: User, therapist_id: Optional[int]) -> int:
    if therapist_id is not None:
        if therapist_id != user.id and not user_has_permission(user, "slot.read"):
            raise HTTPException(status_code=403, detail="Access denied")
        return therapist_id
    return user.id


def _serialise(slot: TherapistSlot) -> dict:
    return cal._slot_to_dict(slot)


@router.get("")
def list_slots(
    therapist_id: Optional[int] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tid = _resolve_therapist_id(user, therapist_id)
    stmt = select(TherapistSlot).where(TherapistSlot.therapist_user_id == tid).order_by(
        TherapistSlot.slot_date, TherapistSlot.start_time
    )
    if from_date:
        stmt = stmt.where(TherapistSlot.slot_date >= from_date)
    if to_date:
        stmt = stmt.where(TherapistSlot.slot_date <= to_date)
    slots = db.scalars(stmt).all()
    return [_serialise(s) for s in slots]


@router.get("/calendar")
def get_calendar(
    from_date: date = Query(...),
    to_date: date = Query(...),
    therapist_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tid = _resolve_therapist_id(user, therapist_id)
    return cal.get_calendar_view(db, tid, from_date, to_date)


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
    payload: TemplateUpdate,
    therapist_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tid = _resolve_therapist_id(user, therapist_id)
    row = cal.upsert_template(db, tid, payload.config)
    db.commit()
    return {"therapist_user_id": tid, "config": row.get_config()}


@router.post("/materialize")
def materialize_slots(
    payload: MaterializeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tid = _resolve_therapist_id(user, payload.therapist_id)
    try:
        created = cal.materialize_range(db, tid, payload.from_date, payload.to_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return {"created": created, "therapist_user_id": tid}


@router.post("/recurring", status_code=status.HTTP_201_CREATED)
def create_recurring(
    payload: RecurringCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tid = _resolve_therapist_id(user, payload.therapist_id)
    try:
        group_id, created = cal.create_recurring_slots(
            db,
            tid,
            weekday_keys=payload.weekday_keys,
            start_time=payload.start_time,
            end_time=payload.end_time,
            from_date=payload.from_date,
            weeks=payload.weeks,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return {"recurrence_group_id": group_id, "created": created}


@router.delete("/recurring/{group_id}", status_code=status.HTTP_200_OK)
def delete_recurring(
    group_id: str,
    future_only: bool = True,
    therapist_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tid = _resolve_therapist_id(user, therapist_id)
    try:
        deleted = cal.delete_recurring_group(db, tid, group_id, future_only=future_only)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return {"deleted": deleted}


@router.get("/bookable-cases")
def bookable_cases(
    therapist_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tid = _resolve_therapist_id(user, therapist_id)
    return cal.list_bookable_cases_for_therapist(db, tid)


@router.post("/{slot_id}/book")
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
        slot = cal.book_slot(db, slot_id, payload.case_id, user.id, source)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="book", entity_type="slot", entity_id=slot_id, **meta)
    db.commit()
    db.refresh(slot)
    return _serialise(slot)


@router.post("/{slot_id}/cancel")
def cancel_booking(
    slot_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    slot = db.get(TherapistSlot, slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    if slot.therapist_user_id != user.id and not user_has_permission(user, "slot.book_any"):
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        slot = cal.cancel_booking(db, slot_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="cancel_booking", entity_type="slot", entity_id=slot_id, **meta)
    db.commit()
    return _serialise(slot)


@router.post("/{slot_id}/block")
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


@router.post("", status_code=status.HTTP_201_CREATED)
def create_slot(
    payload: SlotCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.end_time <= payload.start_time:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")
    slot = TherapistSlot(
        therapist_user_id=user.id,
        slot_date=payload.slot_date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        notes=payload.notes,
    )
    db.add(slot)
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="create", entity_type="slot", entity_id=slot.id, **meta)
    db.commit()
    db.refresh(slot)
    return _serialise(slot)


@router.patch("/{slot_id}")
def update_slot(
    slot_id: int,
    payload: SlotUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    slot = db.get(TherapistSlot, slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    if slot.therapist_user_id != user.id and not user_has_permission(user, "slot.read"):
        raise HTTPException(status_code=403, detail="Access denied")
    if payload.status is not None:
        slot.status = payload.status
    if payload.notes is not None:
        slot.notes = payload.notes
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="update", entity_type="slot", entity_id=slot_id, **meta)
    db.commit()
    db.refresh(slot)
    return _serialise(slot)


@router.delete("/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
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
