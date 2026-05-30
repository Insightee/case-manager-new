from __future__ import annotations

from datetime import date, time
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import extract, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.module_access import get_allowed_case_product_modules, is_view_only_user
from app.core.module_write import ensure_feature_write_access, guard_clinical_case
from app.core.permissions import RoleName, case_scope_check, user_has_permission
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case, CaseStatus
from app.models.child import Child
from app.models.case_manager_meeting import CaseManagerMeeting, MeetingStatus, MeetingType
from app.models.user import User
from app.core.rbac_access import build_module_registry
from app.services import parent_service
from app.services.admin_scope_service import apply_case_scope, scoped_case_ids_subquery, user_sees_global_cases

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
    meeting_url: Optional[str] = None
    guest_emails: list[str] = Field(default_factory=list)
    invite_client: bool = True
    invite_therapist: bool = False
    invite_case_manager: bool = True
    admin_user_ids: list[int] = Field(default_factory=list)


class CmMeetingNotesUpdate(BaseModel):
    status: Optional[MeetingStatus] = None
    title: Optional[str] = None
    meeting_url: Optional[str] = None
    guest_emails: Optional[list[str]] = None
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
        RoleName.THERAPIST.value,
    }


def _all_case_product_modules(db: Session) -> set[str]:
    allowed: set[str] = set()
    for mod in build_module_registry(db).values():
        allowed.update(mod.case_product_modules)
    return allowed


def _bookable_cases_stmt(
    db: Session,
    user: User,
    *,
    case_manager_user_id: int | None = None,
):
    stmt = select(Case).options(selectinload(Case.child)).order_by(Case.case_code)
    allowed_modules = get_allowed_case_product_modules(user, db)
    if allowed_modules is not None and not allowed_modules and user_sees_global_cases(user):
        allowed_modules = _all_case_product_modules(db)
    if allowed_modules is not None:
        if not allowed_modules:
            return stmt.where(Case.id < 0)
        stmt = stmt.where(Case.product_module.in_(allowed_modules))

    role = _role_name(user)
    if case_manager_user_id is not None:
        if role == RoleName.CASE_MANAGER.value and not user_has_permission(user, "admin.override"):
            if case_manager_user_id != user.id:
                raise HTTPException(status_code=403, detail="Cannot view another case manager's caseload")
        elif role == RoleName.THERAPIST.value:
            raise HTTPException(status_code=403, detail="Not allowed")
        stmt = stmt.where(Case.case_manager_user_id == case_manager_user_id)
    elif role == RoleName.CASE_MANAGER.value and not user_has_permission(user, "admin.override"):
        stmt = stmt.where(Case.case_manager_user_id == user.id)
    elif role == RoleName.THERAPIST.value:
        stmt = (
            stmt.join(
                CaseAssignment,
                (CaseAssignment.case_id == Case.id)
                & (CaseAssignment.therapist_user_id == user.id)
                & (CaseAssignment.status == CaseAssignmentStatus.ACTIVE),
            )
            .distinct()
        )
    elif user_has_permission(user, "case.read.team") and not user_sees_global_cases(user):
        stmt = stmt.where(Case.case_manager_user_id == user.id)
    elif not user_sees_global_cases(user):
        stmt = apply_case_scope(stmt, user)
    stmt = stmt.where(Case.status != CaseStatus.CLOSED)
    return stmt


def _resolve_meeting_case_manager_id(
    user: User,
    db: Session,
    *,
    case_id: int | None,
) -> int:
    if case_id:
        case = db.get(Case, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        if case.case_manager_user_id:
            return case.case_manager_user_id
        raise HTTPException(status_code=400, detail="Case has no assigned case manager")
    role = _role_name(user)
    if role in {RoleName.CASE_MANAGER.value, RoleName.ADMIN.value, RoleName.SUPER_ADMIN.value}:
        return user.id
    raise HTTPException(status_code=400, detail="Select a case with an assigned case manager")


def _require_cm_meetings_read(user: User) -> None:
    if not _can_read_cm_meetings(user):
        raise HTTPException(status_code=403, detail="Not allowed to view CM meetings")


def _require_cm_meetings_write(user: User) -> None:
    role = _role_name(user)
    allowed = {
        RoleName.CASE_MANAGER.value,
        RoleName.ADMIN.value,
        RoleName.SUPER_ADMIN.value,
        RoleName.THERAPIST.value,
    }
    if role not in allowed and not user_has_permission(user, "admin.override"):
        raise HTTPException(status_code=403, detail="Not allowed to book CM meetings")
    if is_view_only_user(user):
        raise HTTPException(status_code=403, detail="View-only access — changes are not allowed")


def _guard_cm_meeting_write(user: User, case_id: int | None, db: Session) -> None:
    role = _role_name(user)
    if case_id:
        case = db.get(Case, case_id)
        if case:
            if role == RoleName.THERAPIST.value:
                if not case_scope_check(db, user, case):
                    raise HTTPException(status_code=403, detail="Not your case")
                return
            guard_clinical_case(user, case, db, feature="cm_meetings")
            return
    ensure_feature_write_access(user, "cm_meetings", db=db)


def _serialize(meeting: CaseManagerMeeting, db: Session) -> dict:
    from app.services.cm_meeting_service import build_attendee_rows, parse_staff_attendee_ids

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
    attendees = build_attendee_rows(meeting, db)
    from app.core.timezone import today_ist

    display_status = meeting.status.value if meeting.status else None
    if meeting.status == MeetingStatus.SCHEDULED and meeting.scheduled_date and meeting.scheduled_date < today_ist():
        display_status = "OVERDUE"
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
        "display_status": display_status,
        "completed_at": meeting.completed_at.isoformat() if getattr(meeting, "completed_at", None) else None,
        "completed_by_user_id": getattr(meeting, "completed_by_user_id", None),
        "notes_concerns": meeting.notes_concerns,
        "notes_follow_up": meeting.notes_follow_up,
        "notes_action": meeting.notes_action,
        "notes_other": meeting.notes_other,
        "meeting_url": meeting.meeting_url,
        "guest_emails": json.loads(meeting.guest_emails_json) if meeting.guest_emails_json else [],
        "admin_user_ids": parse_staff_attendee_ids(meeting.staff_attendee_user_ids_json),
        "attendees": attendees,
        "created_at": meeting.created_at.isoformat() if meeting.created_at else None,
    }


# ---------------------------------------------------------------------------
# CM / Admin endpoints
# ---------------------------------------------------------------------------

@router.get("/cm-meetings/bookable-cases")
def list_bookable_cases_for_cm_meetings(
    case_manager_user_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_cm_meetings_read(user)
    stmt = _bookable_cases_stmt(db, user, case_manager_user_id=case_manager_user_id)
    rows = db.scalars(stmt.limit(500)).all()
    return [
        {
            "id": c.id,
            "case_code": c.case_code,
            "child_name": c.child.full_name if c.child else None,
            "case_manager_user_id": c.case_manager_user_id,
            "product_module": c.product_module,
        }
        for c in rows
    ]


@router.post("/cm-meetings", status_code=201)
def create_cm_meeting(
    payload: CmMeetingCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.cm_meeting_service import (
        apply_attendee_selection,
        notify_meeting_invites_respecting_flags,
    )

    _require_cm_meetings_write(user)
    _guard_cm_meeting_write(user, payload.case_id, db)
    role = _role_name(user)
    meeting_type = payload.meeting_type
    invite_therapist = payload.invite_therapist
    therapist_user_id = payload.therapist_user_id
    invite_client = payload.invite_client
    if role == RoleName.THERAPIST.value:
        therapist_user_id = user.id
        invite_therapist = True
        invite_client = True
    cm_user_id = _resolve_meeting_case_manager_id(user, db, case_id=payload.case_id)
    guest_json = json.dumps([e.strip() for e in payload.guest_emails if e and e.strip()]) if payload.guest_emails else None
    meeting = CaseManagerMeeting(
        case_manager_user_id=cm_user_id,
        case_id=payload.case_id,
        parent_user_id=None,
        therapist_user_id=None,
        scheduled_date=payload.scheduled_date,
        scheduled_time=payload.scheduled_time,
        duration_minutes=payload.duration_minutes,
        meeting_type=meeting_type,
        title=payload.title,
        meeting_url=(payload.meeting_url or "").strip() or None,
        guest_emails_json=guest_json,
        status=MeetingStatus.SCHEDULED,
    )
    apply_attendee_selection(
        db,
        meeting,
        invite_client=invite_client,
        invite_therapist=invite_therapist,
        therapist_user_id=therapist_user_id,
        admin_user_ids=payload.admin_user_ids,
        case_id=payload.case_id,
    )
    db.add(meeting)
    db.flush()
    notify_meeting_invites_respecting_flags(
        db,
        meeting,
        actor_user_id=user.id,
        invite_case_manager=payload.invite_case_manager,
    )
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
    elif role == RoleName.THERAPIST.value:
        assigned_case_ids = list(
            db.scalars(
                select(CaseAssignment.case_id).where(
                    CaseAssignment.therapist_user_id == user.id,
                    CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
                )
            ).all()
        )
        therapist_clauses = [
            CaseManagerMeeting.therapist_user_id == user.id,
            CaseManagerMeeting.parent_user_id == user.id,
        ]
        if assigned_case_ids:
            therapist_clauses.append(CaseManagerMeeting.case_id.in_(assigned_case_ids))
        stmt = stmt.where(or_(*therapist_clauses))
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
    if role in {
        RoleName.ADMIN.value,
        RoleName.SUPER_ADMIN.value,
        RoleName.MODULE_ADMIN.value,
    } and not user_has_permission(user, "admin.override") and not user_sees_global_cases(user):
        from app.services.cm_meeting_service import user_can_view_meeting

        meetings = [m for m in meetings if user_can_view_meeting(m, user.id)]
    return [_serialize(m, db) for m in meetings]


@router.get("/cm-meetings/pending-completion")
def list_pending_completion_meetings(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.core.timezone import today_ist
    from app.services.cm_meeting_service import user_can_view_meeting

    _require_cm_meetings_read(user)
    today = today_ist()
    stmt = (
        select(CaseManagerMeeting)
        .where(
            CaseManagerMeeting.status == MeetingStatus.SCHEDULED,
            CaseManagerMeeting.scheduled_date < today,
        )
        .order_by(CaseManagerMeeting.scheduled_date.asc())
        .limit(50)
    )
    role = _role_name(user)
    if role == RoleName.CASE_MANAGER.value and not user_has_permission(user, "admin.override"):
        stmt = stmt.where(CaseManagerMeeting.case_manager_user_id == user.id)
    meetings = db.scalars(stmt).all()
    if role == RoleName.THERAPIST.value:
        meetings = [m for m in meetings if user_can_view_meeting(m, user.id)]
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
    _guard_cm_meeting_write(user, meeting.case_id, db)
    role = user.role_name if hasattr(user, "role_name") else (user.roles[0].name if user.roles else "")
    if role == RoleName.CASE_MANAGER.value and meeting.case_manager_user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your meeting")
    old_date = meeting.scheduled_date
    old_time = meeting.scheduled_time
    old_duration = meeting.duration_minutes
    old_url = meeting.meeting_url
    old_guests = meeting.guest_emails_json
    completing = payload.status == MeetingStatus.COMPLETED
    if payload.status is not None:
        if payload.status == MeetingStatus.COMPLETED and meeting.status != MeetingStatus.COMPLETED:
            notes = [
                payload.notes_concerns if payload.notes_concerns is not None else meeting.notes_concerns,
                payload.notes_follow_up if payload.notes_follow_up is not None else meeting.notes_follow_up,
                payload.notes_action if payload.notes_action is not None else meeting.notes_action,
                payload.notes_other if payload.notes_other is not None else meeting.notes_other,
            ]
            if not any(n and str(n).strip() for n in notes):
                raise HTTPException(
                    status_code=400,
                    detail="Add at least one completion note (concerns, follow-up, action, or other) before marking completed.",
                )
        meeting.status = payload.status
        if payload.status == MeetingStatus.COMPLETED:
            from datetime import datetime, timezone

            meeting.completed_at = datetime.now(timezone.utc)
            meeting.completed_by_user_id = user.id
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
    if payload.meeting_url is not None:
        meeting.meeting_url = (payload.meeting_url or "").strip() or None
    if payload.guest_emails is not None:
        meeting.guest_emails_json = json.dumps(
            [e.strip() for e in payload.guest_emails if e and e.strip()]
        ) or None
    schedule_changed = (
        (payload.scheduled_date is not None and payload.scheduled_date != old_date)
        or (payload.scheduled_time is not None and payload.scheduled_time != old_time)
        or (payload.duration_minutes is not None and payload.duration_minutes != old_duration)
    )
    link_changed = payload.meeting_url is not None and (meeting.meeting_url or "") != (old_url or "")
    guests_changed = payload.guest_emails is not None and meeting.guest_emails_json != old_guests
    if (
        meeting.status == MeetingStatus.SCHEDULED
        and (schedule_changed or link_changed or guests_changed)
    ):
        from app.services.cm_meeting_service import notify_meeting_invites_respecting_flags

        notify_meeting_invites_respecting_flags(
            db,
            meeting,
            actor_user_id=user.id,
            invite_case_manager=True,
            is_update=True,
        )
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
    _guard_cm_meeting_write(user, meeting.case_id, db)
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
