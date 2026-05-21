from __future__ import annotations

from datetime import date, time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import extract, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.permissions import RoleName, user_has_permission
from app.models.case import Case
from app.models.child import Child
from app.models.case_manager_meeting import CaseManagerMeeting, MeetingStatus, MeetingType
from app.models.user import User
from app.services import parent_service
from app.services.admin_scope_service import apply_case_scope, scoped_case_ids_subquery

router = APIRouter(tags=["cm-meetings"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class CmMeetingCreate(BaseModel):
    case_id: Optional[int] = None
    parent_user_id: Optional[int] = None
    therapist_user_id: Optional[int] = None
    scheduled_date: date
    scheduled_time: Optional[time] = None
    duration_minutes: int = 30
    meeting_type: MeetingType = MeetingType.CLIENT_ONLY
    title: Optional[str] = None


class CmMeetingNotesUpdate(BaseModel):
    status: Optional[MeetingStatus] = None
    title: Optional[str] = None
    notes_concerns: Optional[str] = None
    notes_follow_up: Optional[str] = None
    notes_action: Optional[str] = None
    notes_other: Optional[str] = None
    therapist_user_id: Optional[int] = None
    scheduled_date: Optional[date] = None
    scheduled_time: Optional[time] = None
    duration_minutes: Optional[int] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _role_name(user: User) -> str:
    return user.role_name if hasattr(user, "role_name") else (user.roles[0].name if user.roles else "")


def _can_read_cm_meetings(user: User) -> bool:
    if user_has_permission(user, "admin.override"):
        return True
    role = _role_name(user)
    return role in {
        RoleName.CASE_MANAGER.value,
        RoleName.ADMIN.value,
        RoleName.SUPER_ADMIN.value,
        RoleName.SUPERVISOR.value,
    }


def _require_cm_meetings_read(user: User) -> None:
    if not _can_read_cm_meetings(user):
        raise HTTPException(status_code=403, detail="Not allowed to view CM meetings")


def _require_cm_meetings_write(user: User) -> None:
    role = _role_name(user)
    allowed = {RoleName.CASE_MANAGER.value, RoleName.ADMIN.value, RoleName.SUPER_ADMIN.value}
    if role not in allowed and not user_has_permission(user, "admin.override"):
        raise HTTPException(status_code=403, detail="Case manager or admin role required")


def _serialize(meeting: CaseManagerMeeting, db: Session) -> dict:
    cm = db.get(User, meeting.case_manager_user_id)
    parent = db.get(User, meeting.parent_user_id) if meeting.parent_user_id else None
    therapist = db.get(User, meeting.therapist_user_id) if meeting.therapist_user_id else None
    child_name: Optional[str] = None
    case_code: Optional[str] = None
    if meeting.case_id:
        case = db.get(Case, meeting.case_id)
        if case:
            case_code = case.case_code
            if case.child:
                child_name = case.child.full_name
    return {
        "id": meeting.id,
        "case_manager_user_id": meeting.case_manager_user_id,
        "case_manager_name": cm.full_name if cm else None,
        "case_id": meeting.case_id,
        "case_code": case_code,
        "child_name": child_name,
        "parent_user_id": meeting.parent_user_id,
        "parent_name": parent.full_name if parent else None,
        "therapist_user_id": meeting.therapist_user_id,
        "therapist_name": therapist.full_name if therapist else None,
        "scheduled_date": meeting.scheduled_date.isoformat() if meeting.scheduled_date else None,
        "scheduled_time": meeting.scheduled_time.strftime("%H:%M") if meeting.scheduled_time else None,
        "duration_minutes": meeting.duration_minutes,
        "meeting_type": meeting.meeting_type.value if meeting.meeting_type else None,
        "title": meeting.title,
        "status": meeting.status.value if meeting.status else None,
        "notes_concerns": meeting.notes_concerns,
        "notes_follow_up": meeting.notes_follow_up,
        "notes_action": meeting.notes_action,
        "notes_other": meeting.notes_other,
        "created_at": meeting.created_at.isoformat() if meeting.created_at else None,
    }


# ---------------------------------------------------------------------------
# CM / Admin endpoints
# ---------------------------------------------------------------------------

@router.post("/cm-meetings", status_code=201)
def create_cm_meeting(
    payload: CmMeetingCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_cm_meetings_write(user)
    meeting_type = payload.meeting_type
    if payload.therapist_user_id:
        meeting_type = MeetingType.CLIENT_AND_THERAPIST
    parent_user_id = payload.parent_user_id
    if payload.case_id and not parent_user_id:
        case = db.get(Case, payload.case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        if case.child_id:
            parent_user_id = parent_service.primary_parent_user_id_for_child(db, case.child_id)
    meeting = CaseManagerMeeting(
        case_manager_user_id=user.id,
        case_id=payload.case_id,
        parent_user_id=parent_user_id,
        therapist_user_id=payload.therapist_user_id,
        scheduled_date=payload.scheduled_date,
        scheduled_time=payload.scheduled_time,
        duration_minutes=payload.duration_minutes,
        meeting_type=meeting_type,
        title=payload.title,
        status=MeetingStatus.SCHEDULED,
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return _serialize(meeting, db)


@router.get("/cm-meetings")
def list_cm_meetings(
    case_id: Optional[int] = None,
    status: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    meeting_type: Optional[str] = None,
    case_manager_user_id: Optional[int] = None,
    search: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_cm_meetings_read(user)
    role = _role_name(user)
    stmt = select(CaseManagerMeeting).order_by(
        CaseManagerMeeting.scheduled_date.desc()
    )
    if role == RoleName.CASE_MANAGER.value and not user_has_permission(user, "admin.override"):
        stmt = stmt.where(CaseManagerMeeting.case_manager_user_id == user.id)
    elif role == RoleName.SUPERVISOR.value and not user_has_permission(user, "admin.override"):
        case_ids = db.scalars(scoped_case_ids_subquery(user)).all()
        if not case_ids:
            stmt = stmt.where(CaseManagerMeeting.id < 0)
        else:
            stmt = stmt.where(
                or_(
                    CaseManagerMeeting.case_id.in_(case_ids),
                    CaseManagerMeeting.case_manager_user_id == user.id,
                )
            )
    if case_id is not None:
        stmt = stmt.where(CaseManagerMeeting.case_id == case_id)
    if status:
        try:
            stmt = stmt.where(CaseManagerMeeting.status == MeetingStatus(status.upper()))
        except ValueError:
            pass
    if meeting_type:
        try:
            stmt = stmt.where(CaseManagerMeeting.meeting_type == MeetingType(meeting_type.upper()))
        except ValueError:
            pass
    if case_manager_user_id is not None:
        stmt = stmt.where(CaseManagerMeeting.case_manager_user_id == case_manager_user_id)
    if year is not None:
        stmt = stmt.where(extract("year", CaseManagerMeeting.scheduled_date) == year)
    if month is not None:
        stmt = stmt.where(extract("month", CaseManagerMeeting.scheduled_date) == month)
    if search:
        q = f"%{search.strip()}%"
        stmt = (
            stmt.outerjoin(Case, CaseManagerMeeting.case_id == Case.id)
            .outerjoin(Child, Case.child_id == Child.id)
            .where(
                or_(
                    CaseManagerMeeting.title.ilike(q),
                    Case.case_code.ilike(q),
                    Child.first_name.ilike(q),
                    Child.last_name.ilike(q),
                )
            )
        )
    meetings = db.scalars(stmt).all()
    return [_serialize(m, db) for m in meetings]


@router.patch("/cm-meetings/{meeting_id}")
def update_cm_meeting(
    meeting_id: int,
    payload: CmMeetingNotesUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_cm_meetings_write(user)
    meeting = db.get(CaseManagerMeeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    role = user.role_name if hasattr(user, "role_name") else (user.roles[0].name if user.roles else "")
    if role == RoleName.CASE_MANAGER.value and meeting.case_manager_user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your meeting")
    if payload.status is not None:
        meeting.status = payload.status
    if payload.title is not None:
        meeting.title = payload.title
    if payload.notes_concerns is not None:
        meeting.notes_concerns = payload.notes_concerns
    if payload.notes_follow_up is not None:
        meeting.notes_follow_up = payload.notes_follow_up
    if payload.notes_action is not None:
        meeting.notes_action = payload.notes_action
    if payload.notes_other is not None:
        meeting.notes_other = payload.notes_other
    if payload.therapist_user_id is not None:
        meeting.therapist_user_id = payload.therapist_user_id
        meeting.meeting_type = MeetingType.CLIENT_AND_THERAPIST
    if payload.scheduled_date is not None:
        meeting.scheduled_date = payload.scheduled_date
    if payload.scheduled_time is not None:
        meeting.scheduled_time = payload.scheduled_time
    if payload.duration_minutes is not None:
        meeting.duration_minutes = payload.duration_minutes
    db.commit()
    db.refresh(meeting)
    return _serialize(meeting, db)


@router.delete("/cm-meetings/{meeting_id}", status_code=204)
def cancel_cm_meeting(
    meeting_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_cm_meetings_write(user)
    meeting = db.get(CaseManagerMeeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    role = user.role_name if hasattr(user, "role_name") else (user.roles[0].name if user.roles else "")
    if role == RoleName.CASE_MANAGER.value and meeting.case_manager_user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your meeting")
    meeting.status = MeetingStatus.CANCELLED
    db.commit()


# ---------------------------------------------------------------------------
# Parent endpoint  (read-only, scoped to their cases)
# ---------------------------------------------------------------------------

@router.get("/parent/cm-meetings")
def parent_cm_meetings(
    year: Optional[int] = None,
    month: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    role = user.role_name if hasattr(user, "role_name") else (user.roles[0].name if user.roles else "")
    if role != RoleName.PARENT.value:
        raise HTTPException(status_code=403, detail="Parent access only")
    child_ids = parent_service.child_ids_for_parent(db, user.id)
    if not child_ids:
        return []
    case_ids = list(
        db.scalars(select(Case.id).where(Case.child_id.in_(child_ids))).all()
    )
    if not case_ids:
        return []
    stmt = (
        select(CaseManagerMeeting)
        .where(
            CaseManagerMeeting.case_id.in_(case_ids),
            CaseManagerMeeting.status != MeetingStatus.CANCELLED,
        )
        .order_by(CaseManagerMeeting.scheduled_date.asc())
    )
    if year is not None:
        stmt = stmt.where(extract("year", CaseManagerMeeting.scheduled_date) == year)
    if month is not None:
        stmt = stmt.where(extract("month", CaseManagerMeeting.scheduled_date) == month)
    meetings = db.scalars(stmt).all()
    return [_serialize(m, db) for m in meetings]
