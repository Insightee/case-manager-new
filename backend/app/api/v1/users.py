from __future__ import annotations

from datetime import date, time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.db_errors import commit_or_http
from app.core.permissions import RoleName, has_any_role, user_has_permission
from app.models.calendar_availability import AvailabilityExceptionType
from app.models.user import User
from app.services import availability_service

router = APIRouter(prefix="/users", tags=["users"])


class AvailabilityRuleIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    effective_from: date | None = None
    effective_to: date | None = None
    slot_granularity_minutes: int = Field(default=30, ge=1)


class AvailabilityExceptionIn(BaseModel):
    date: date
    type: AvailabilityExceptionType = AvailabilityExceptionType.CLOSED
    start_time: time | None = None
    end_time: time | None = None
    reason: str | None = None


class BookingPolicyIn(BaseModel):
    min_notice_minutes: int = Field(default=120, ge=0)
    max_days_ahead: int = Field(default=60, ge=0)
    buffer_minutes: int = Field(default=0, ge=0)
    allowed_durations: list[int] = Field(default_factory=lambda: [30, 45, 60, 90])


class AvailabilityUpdatePayload(BaseModel):
    rules: list[AvailabilityRuleIn] = Field(default_factory=list)
    exceptions: list[AvailabilityExceptionIn] = Field(default_factory=list)
    booking_policy: BookingPolicyIn = Field(default_factory=BookingPolicyIn)


def _can_manage_user_availability(current_user: User, target_user_id: int) -> bool:
    if current_user.id == target_user_id:
        return True
    if user_has_permission(current_user, "admin.override"):
        return True
    return has_any_role(
        current_user,
        RoleName.SUPER_ADMIN,
        RoleName.ADMIN,
        RoleName.MODULE_ADMIN,
    )


@router.get("/{user_id}/availability")
def get_user_availability(
    user_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _can_manage_user_availability(user, user_id):
        raise HTTPException(status_code=403, detail="Not allowed to view this availability")
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    return availability_service.load_user_availability(db, user_id)


@router.put("/{user_id}/availability")
def update_user_availability(
    user_id: int,
    payload: AvailabilityUpdatePayload,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _can_manage_user_availability(user, user_id):
        raise HTTPException(status_code=403, detail="Not allowed to update this availability")
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    updated = availability_service.save_user_availability(db, user_id, payload.model_dump())
    commit_or_http(db)
    return updated

