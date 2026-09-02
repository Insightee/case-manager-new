from __future__ import annotations

import csv
import json
import uuid
from datetime import date, datetime, time, timedelta
from io import BytesIO, StringIO
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import extract, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.db_errors import commit_or_http
from app.core.module_access import get_allowed_case_product_modules, is_view_only_user
from app.core.module_write import ensure_feature_write_access, guard_clinical_case
from app.core.timezone import IST, now_ist, today_ist
from app.core.permissions import (
    RoleName,
    case_scope_check,
    effective_role,
    has_any_role,
    has_role,
    user_has_permission,
)
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case, CaseStatus
from app.models.child import Child
from app.models.case_manager_meeting import CaseManagerMeeting, MeetingStatus, MeetingType
from app.models.meeting_action import MeetingAction
from app.models.session import Session as TherapySession, SessionStatus
from app.models.user import User
from app.services import parent_service
from app.services import availability_service
from app.services.cm_meeting_service import meeting_participant_user_ids, parse_staff_attendee_ids
from app.services.cm_meeting_service import user_can_view_meeting, notify_meeting_cancellation
from app.services.cm_meeting_service import send_meeting_reminder_if_within_hour
from app.services.admin_scope_service import scoped_case_ids_subquery, user_sees_global_cases
from app.services.mentor_scope_service import mentor_case_ids_subquery
from app.services.reports_export_helpers import parse_int_list
from app.services import case_document_service as doc_svc

router = APIRouter(tags=["meetings"])
compat_router = APIRouter(tags=["cm-meetings"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class MeetingActionSchema(BaseModel):
    title: str
    owner_role: str  # parent, therapist, case_manager, admin
    due_date: Optional[date] = None
    status: Optional[str] = None  # open, completed
    id: Optional[int] = None


class MeetingCreate(BaseModel):
    case_id: Optional[int] = None
    parent_user_id: Optional[int] = None
    therapist_user_id: Optional[int] = None
    mentor_user_id: Optional[int] = None
    scheduled_date: date
    scheduled_time: Optional[time] = None
    duration_minutes: int = 30  # 30, 45, 60, 90 validated in endpoint
    meeting_type: MeetingType
    other_reason: Optional[str] = None
    title: Optional[str] = None
    meeting_url: Optional[str] = None
    platform: Optional[str] = None  # GOOGLE_MEET, ZOOM, TEAMS, EXTERNAL
    guest_emails: list[str] = Field(default_factory=list)
    invite_client: bool = True
    invite_therapist: bool = False
    invite_case_manager: bool = True
    admin_user_ids: list[int] = Field(default_factory=list)

    # Linked clinical records
    linked_observation_report_id: Optional[int] = None
    linked_observation_checklist_id: Optional[int] = None
    linked_iep_id: Optional[int] = None
    linked_monthly_report_id: Optional[int] = None
    linked_incident_id: Optional[int] = None
    linked_ticket_id: Optional[int] = None


class MeetingNotesUpdate(BaseModel):
    status: Optional[MeetingStatus] = None
    title: Optional[str] = None
    meeting_url: Optional[str] = None
    platform: Optional[str] = None
    guest_emails: Optional[list[str]] = None
    other_reason: Optional[str] = None

    notes_outcome: Optional[str] = None
    notes_summary: Optional[str] = None
    notes_next_meeting_required: Optional[bool] = None
    notes_additional: Optional[str] = None
    therapist_notes: Optional[str] = None

    therapist_user_id: Optional[int] = None
    mentor_user_id: Optional[int] = None
    scheduled_date: Optional[date] = None
    scheduled_time: Optional[time] = None
    duration_minutes: Optional[int] = None

    # Actions list sync
    actions: Optional[list[MeetingActionSchema]] = None

    linked_observation_report_id: Optional[int] = None
    linked_observation_checklist_id: Optional[int] = None
    linked_iep_id: Optional[int] = None
    linked_monthly_report_id: Optional[int] = None
    linked_incident_id: Optional[int] = None
    linked_ticket_id: Optional[int] = None


class MeetingReschedulePayload(BaseModel):
    scheduled_date: date
    scheduled_time: time
    duration_minutes: int
    reschedule_reason: str


class MeetingCancelPayload(BaseModel):
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers & Validations
# scheduled_time is naive local time in Asia/Kolkata (IST).
# ---------------------------------------------------------------------------

def _can_read_meetings(user: User) -> bool:
    if user_has_permission(user, "admin.override"):
        return True
    return has_any_role(
        user,
        RoleName.CASE_MANAGER,
        RoleName.ADMIN,
        RoleName.MODULE_ADMIN,
        RoleName.SUPER_ADMIN,
        RoleName.SUPERVISOR,
        RoleName.HR,
        RoleName.THERAPIST,
        RoleName.PARENT,
    )


def _require_meetings_read(user: User) -> None:
    if not _can_read_meetings(user):
        raise HTTPException(status_code=403, detail="Not allowed to view meetings")


def _require_meetings_write(user: User) -> None:
    allowed = has_any_role(
        user,
        RoleName.CASE_MANAGER,
        RoleName.ADMIN,
        RoleName.MODULE_ADMIN,
        RoleName.SUPER_ADMIN,
        RoleName.THERAPIST,
    )
    if not allowed and not user_has_permission(user, "admin.override"):
        raise HTTPException(status_code=403, detail="Not allowed to schedule meetings")
    if is_view_only_user(user):
        raise HTTPException(status_code=403, detail="View-only access — changes are not allowed")


def _guard_meeting_write(
    user: User,
    case_id: int | None,
    db: Session,
    *,
    meeting: CaseManagerMeeting | None = None,
) -> None:
    if effective_role(user) == RoleName.THERAPIST.value:
        from app.services.cm_meeting_service import user_can_view_meeting
        if meeting is not None and user_can_view_meeting(meeting, user.id):
            return
        if case_id:
            case = db.get(Case, case_id)
            if not case:
                raise HTTPException(status_code=404, detail="Case not found")
            if not case_scope_check(db, user, case):
                raise HTTPException(status_code=403, detail="Not your case")
            return
        raise HTTPException(status_code=400, detail="Select a case with an assigned case manager")

    if case_id:
        case = db.get(Case, case_id)
        if case:
            guard_clinical_case(user, case, db, feature="cm_meetings")
            return
    ensure_feature_write_access(user, "cm_meetings", db=db)


def _validate_meeting_duration(duration: int) -> None:
    if duration not in {30, 45, 60, 90}:
        raise HTTPException(status_code=400, detail="Meeting duration must be 30, 45, 60, or 90 minutes")


def _all_case_product_modules(db: Session) -> set[str]:
    from app.core.rbac_access import build_module_registry
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
    from app.services.admin_scope_service import user_sees_global_cases, apply_case_scope
    stmt = select(Case).options(selectinload(Case.child)).order_by(Case.case_code)
    allowed_modules = get_allowed_case_product_modules(user, db)
    if allowed_modules is not None and not allowed_modules and user_sees_global_cases(user):
        allowed_modules = _all_case_product_modules(db)
    if allowed_modules is not None:
        if not allowed_modules:
            return stmt.where(Case.id < 0)
        stmt = stmt.where(Case.product_module.in_(allowed_modules))

    role = effective_role(user)
    if case_manager_user_id is not None:
        if _is_case_manager_scoped(user):
            if case_manager_user_id != user.id:
                raise HTTPException(status_code=403, detail="Cannot view another case manager's caseload")
        elif role == RoleName.THERAPIST.value:
            raise HTTPException(status_code=403, detail="Not allowed")
        stmt = stmt.where(Case.case_manager_user_id == case_manager_user_id)
    elif _is_case_manager_scoped(user):
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


def _validate_meeting_link(platform: Optional[str], url: Optional[str]) -> None:
    if not platform:
        return
    trimmed = (url or "").strip()
    if not trimmed:
        return  # blank links are allowed if platform supports it (filled by oauth later or left empty)
    if not trimmed.startswith("https://"):
        raise HTTPException(status_code=400, detail="Meeting link must start with https://")
    
    if platform == "GOOGLE_MEET" and "meet.google.com" not in trimmed:
        raise HTTPException(status_code=400, detail="Invalid Google Meet URL")
    elif platform == "ZOOM" and "zoom.us" not in trimmed:
        raise HTTPException(status_code=400, detail="Invalid Zoom URL")
    elif platform == "TEAMS" and "teams.microsoft.com" not in trimmed and "teams.live.com" not in trimmed:
        raise HTTPException(status_code=400, detail="Invalid Microsoft Teams URL")


def _normalize_guest_emails(guest_emails: Optional[list[str]]) -> str | None:
    cleaned = [e.strip() for e in guest_emails or [] if e and e.strip()]
    return json.dumps(cleaned) if cleaned else None


def _meeting_start_dt(meeting_date: date | None, meeting_time: time | None) -> datetime | None:
    if meeting_date is None:
        return None
    start_time = meeting_time or time(0, 0)
    return datetime.combine(meeting_date, start_time, tzinfo=IST)


def _can_complete_meeting(user: User, meeting: CaseManagerMeeting) -> bool:
    if user_has_permission(user, "admin.override"):
        return True
    return has_role(user, RoleName.CASE_MANAGER) and meeting.case_manager_user_id == user.id


def _viewer_is_therapist(user: User | None) -> bool:
    return user is not None and effective_role(user) == RoleName.THERAPIST.value


def _viewer_is_parent(user: User | None) -> bool:
    return user is not None and effective_role(user) == RoleName.PARENT.value


def _is_case_manager_scoped(user: User) -> bool:
    """True when the user should be limited to their own CM caseload for meetings."""
    if user_has_permission(user, "admin.override"):
        return False
    return effective_role(user) == RoleName.CASE_MANAGER.value


def _case_manager_meeting_scope(user: User, db: Session):
    clauses = [CaseManagerMeeting.case_manager_user_id == user.id]
    mentor_case_ids = list(db.scalars(mentor_case_ids_subquery(user.id)).all())
    if mentor_case_ids:
        clauses.append(CaseManagerMeeting.case_id.in_(mentor_case_ids))
    return or_(*clauses)


def _meetings_scope_stmt(user: User, db: Session, *, include_rescheduled: bool = False):
    stmt = select(CaseManagerMeeting).options(selectinload(CaseManagerMeeting.actions)).order_by(
        CaseManagerMeeting.scheduled_date.desc(),
        CaseManagerMeeting.scheduled_time.desc(),
    )

    role = effective_role(user)
    if _is_case_manager_scoped(user):
        stmt = stmt.where(_case_manager_meeting_scope(user, db))
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
    elif role == RoleName.PARENT.value:
        child_ids = parent_service.child_ids_for_parent(db, user.id)
        if not child_ids:
            return stmt.where(CaseManagerMeeting.id < 0)
        case_ids = list(db.scalars(select(Case.id).where(Case.child_id.in_(child_ids))).all())
        if not case_ids:
            return stmt.where(CaseManagerMeeting.id < 0)
        stmt = stmt.where(
            CaseManagerMeeting.case_id.in_(case_ids),
            CaseManagerMeeting.status != MeetingStatus.CANCELLED,
        )

    if not include_rescheduled:
        stmt = stmt.where(CaseManagerMeeting.status != MeetingStatus.RESCHEDULED)
    return stmt


def _apply_role_scoped_notes(data: dict, viewer: User | None) -> dict:
    """Hide CM notes from therapists and therapist notes from everyone else."""
    if _viewer_is_therapist(viewer):
        for key in (
            "notes_outcome",
            "notes_summary",
            "notes_next_meeting_required",
            "notes_additional",
            "notes_concerns",
            "notes_follow_up",
            "notes_action",
            "notes_other",
        ):
            data[key] = None
        data["actions"] = []
        if data.get("display_status") in {"OVERDUE_NOTES", "PENDING_NOTES"}:
            data["display_status"] = data.get("status")
    else:
        data["therapist_notes"] = None

    if _viewer_is_parent(viewer):
        for key in (
            "notes_outcome",
            "notes_summary",
            "notes_next_meeting_required",
            "notes_additional",
            "notes_concerns",
            "notes_follow_up",
            "notes_action",
            "notes_other",
            "therapist_notes",
        ):
            data[key] = None
        data["actions"] = []

    return data


def _serialize_many(meetings: list[CaseManagerMeeting], db: Session, viewer: User | None = None) -> list[dict]:
    if not meetings:
        return []

    meeting_ids = [meeting.id for meeting in meetings]
    case_ids = sorted({meeting.case_id for meeting in meetings if meeting.case_id})
    user_ids: set[int] = set()
    for meeting in meetings:
        user_ids.update(
            uid
            for uid in (
                meeting.case_manager_user_id,
                meeting.parent_user_id,
                meeting.therapist_user_id,
                meeting.mentor_user_id,
                meeting.completed_by_user_id,
                meeting.cancelled_by_user_id,
            )
            if uid
        )
        user_ids.update(parse_staff_attendee_ids(meeting.staff_attendee_user_ids_json))

    users_by_id = {
        user.id: user
        for user in db.scalars(select(User).where(User.id.in_(sorted(user_ids)))).all()
    } if user_ids else {}
    cases_by_id = {
        case.id: case
        for case in db.scalars(
            select(Case).options(selectinload(Case.child)).where(Case.id.in_(case_ids))
        ).all()
    } if case_ids else {}
    actions_by_meeting: dict[int, list[MeetingAction]] = {}
    for action in db.scalars(select(MeetingAction).where(MeetingAction.meeting_id.in_(meeting_ids))).all():
        actions_by_meeting.setdefault(action.meeting_id, []).append(action)

    serialized: list[dict] = []
    today = today_ist()
    for meeting in meetings:
        cm = users_by_id.get(meeting.case_manager_user_id)
        parent = users_by_id.get(meeting.parent_user_id) if meeting.parent_user_id else None
        therapist = users_by_id.get(meeting.therapist_user_id) if meeting.therapist_user_id else None
        mentor = users_by_id.get(meeting.mentor_user_id) if meeting.mentor_user_id else None
        completed_by = users_by_id.get(meeting.completed_by_user_id) if meeting.completed_by_user_id else None
        cancelled_by = users_by_id.get(meeting.cancelled_by_user_id) if meeting.cancelled_by_user_id else None

        case = cases_by_id.get(meeting.case_id) if meeting.case_id else None
        case_code = case.case_code if case else None
        child_name = case.child.full_name if case and case.child else None

        attendees: list[dict] = []
        seen_attendees: set[tuple[str, int]] = set()

        def add_attendee(role: str, user: User | None) -> None:
            if not user:
                return
            key = (role, user.id)
            if key in seen_attendees:
                return
            seen_attendees.add(key)
            attendees.append({"role": role, "user_id": user.id, "name": user.full_name or user.email})

        add_attendee("case_manager", cm)
        add_attendee("client", parent)
        add_attendee("therapist", therapist)
        add_attendee("mentor", mentor)
        for uid in parse_staff_attendee_ids(meeting.staff_attendee_user_ids_json):
            add_attendee("admin", users_by_id.get(uid))

        notes_missing = not meeting.notes_outcome or not meeting.notes_summary
        display_status = meeting.status.value if meeting.status else None
        if meeting.status == MeetingStatus.SCHEDULED:
            if meeting.scheduled_date and meeting.scheduled_date < today:
                display_status = "OVERDUE_NOTES" if notes_missing else "COMPLETED"
            elif meeting.scheduled_date == today and notes_missing:
                display_status = "PENDING_NOTES"
        elif meeting.status == MeetingStatus.COMPLETED and notes_missing:
            if meeting.scheduled_date and meeting.scheduled_date < today:
                display_status = "OVERDUE_NOTES"
            else:
                display_status = "PENDING_NOTES"

        action_items = [
            {
                "id": action.id,
                "title": action.title,
                "owner_role": action.owner_role,
                "due_date": action.due_date.isoformat() if action.due_date else None,
                "status": action.status,
            }
            for action in actions_by_meeting.get(meeting.id, [])
        ]

        data = {
            "id": meeting.id,
            "series_id": meeting.series_id,
            "case_manager_user_id": meeting.case_manager_user_id,
            "case_manager_name": cm.full_name if cm else None,
            "case_id": meeting.case_id,
            "case_code": case_code,
            "child_name": child_name,
            "parent_user_id": meeting.parent_user_id,
            "parent_name": parent.full_name if parent else None,
            "therapist_user_id": meeting.therapist_user_id,
            "therapist_name": therapist.full_name if therapist else None,
            "mentor_user_id": meeting.mentor_user_id,
            "mentor_name": mentor.full_name if mentor else None,
            "scheduled_date": meeting.scheduled_date.isoformat() if meeting.scheduled_date else None,
            "scheduled_time": meeting.scheduled_time.strftime("%H:%M") if meeting.scheduled_time else None,
            "duration_minutes": meeting.duration_minutes,
            "meeting_type": meeting.meeting_type.value if meeting.meeting_type else None,
            "other_reason": meeting.other_reason,
            "title": meeting.title,
            "status": meeting.status.value if meeting.status else None,
            "display_status": display_status,
            "platform": meeting.platform,
            "meeting_url": meeting.meeting_url,
            "guest_emails": json.loads(meeting.guest_emails_json) if meeting.guest_emails_json else [],
            "admin_user_ids": parse_staff_attendee_ids(meeting.staff_attendee_user_ids_json),
            "attendees": attendees,
            "rescheduled_from_id": meeting.rescheduled_from_id,
            "reschedule_reason": meeting.reschedule_reason,
            "cancel_reason": meeting.cancel_reason,
            "cancelled_by_user_id": meeting.cancelled_by_user_id,
            "cancelled_by_name": cancelled_by.full_name if cancelled_by else None,
            "cancelled_at": meeting.cancelled_at.isoformat() if meeting.cancelled_at else None,
            "reminder_sent_at": meeting.reminder_sent_at.isoformat() if meeting.reminder_sent_at else None,
            "notes_outcome": meeting.notes_outcome,
            "notes_summary": meeting.notes_summary,
            "notes_next_meeting_required": meeting.notes_next_meeting_required,
            "notes_additional": meeting.notes_additional,
            "therapist_notes": meeting.therapist_notes,
            "actions": action_items,
            "linked_observation_report_id": meeting.linked_observation_report_id,
            "linked_observation_checklist_id": meeting.linked_observation_checklist_id,
            "linked_iep_id": meeting.linked_iep_id,
            "linked_monthly_report_id": meeting.linked_monthly_report_id,
            "linked_incident_id": meeting.linked_incident_id,
            "linked_ticket_id": meeting.linked_ticket_id,
            "completed_at": meeting.completed_at.isoformat() if meeting.completed_at else None,
            "completed_by_user_id": meeting.completed_by_user_id,
            "completed_by_name": completed_by.full_name if completed_by else None,
            "created_at": meeting.created_at.isoformat() if meeting.created_at else None,
        }
        serialized.append(_apply_role_scoped_notes(data, viewer))
    return serialized


def _serialize(meeting: CaseManagerMeeting, db: Session, viewer: User | None = None) -> dict:
    rows = _serialize_many([meeting], db, viewer=viewer)
    return rows[0] if rows else {}


# ---------------------------------------------------------------------------
# Availability Conflict Engine
# ---------------------------------------------------------------------------

def _check_time_overlap(s1: time, duration1_mins: int, s2: time, duration2_mins: int) -> bool:
    anchor = today_ist()
    d1 = datetime.combine(anchor, s1)
    d2 = datetime.combine(anchor, s2)
    e1 = d1 + timedelta(minutes=duration1_mins)
    e2 = d2 + timedelta(minutes=duration2_mins)
    return max(d1, d2) < min(e1, e2)


def check_conflicts(
    db: Session,
    target_date: date,
    target_time: time,
    duration_minutes: int,
    attendee_ids: list[int],
    ignore_meeting_id: Optional[int] = None,
) -> tuple[bool, Optional[str]]:
    """Checks if any attendee is already booked in meetings or sessions during target slot."""
    if not attendee_ids:
        return False, None
    slot_start = datetime.combine(target_date, target_time).replace(tzinfo=availability_service.IST)
    slot_end = slot_start + timedelta(minutes=duration_minutes)
    busy = availability_service.busy_intervals(
        db,
        attendee_ids,
        target_date,
        target_date,
        ignore_meeting_id=ignore_meeting_id,
    )
    for uid in attendee_ids:
        for busy_start, busy_end in busy.get(uid, []):
            if max(slot_start, busy_start) < min(slot_end, busy_end):
                conflicted_name = db.scalar(select(User.full_name).where(User.id == uid)) or f"User {uid}"
                return True, f"Conflict: {conflicted_name} is busy"
    return False, None


def _validate_slot_in_availability(
    db: Session,
    *,
    target_date: date,
    target_time: time,
    duration_minutes: int,
    attendee_ids: list[int],
    user: User,
) -> None:
    """Ensure the requested start time falls in shared attendee availability."""
    if not attendee_ids or not target_time:
        return
    slots_payload = availability_service.free_slots(
        db,
        attendee_ids,
        target_date,
        target_date,
        duration_minutes,
        user,
    )
    requested = target_time.strftime("%H:%M")
    allowed = {
        slot["time"]
        for slot in slots_payload.get("slots", [])
        if slot.get("date") == target_date.isoformat()
    }
    if requested not in allowed:
        raise HTTPException(
            status_code=400,
            detail="That time isn't open on the case manager's calendar — pick one of the available slots.",
        )


@router.get("/meetings/bookable-cases")
@compat_router.get("/cm-meetings/bookable-cases")
def list_bookable_cases_for_meetings(
    case_manager_user_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_meetings_read(user)
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


@router.get("/meetings/availability")
def get_meetings_availability(
    target_date: date,
    case_manager_id: Optional[int] = None,
    therapist_id: Optional[int] = None,
    parent_id: Optional[int] = None,
    mentor_id: Optional[int] = None,
    admin_ids: list[int] = Query(default_factory=list),
    duration_minutes: int = 30,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_meetings_read(user)
    _validate_meeting_duration(duration_minutes)

    attendees = []
    if case_manager_id:
        attendees.append(case_manager_id)
    if therapist_id:
        attendees.append(therapist_id)
    if parent_id:
        attendees.append(parent_id)
    if mentor_id:
        attendees.append(mentor_id)
    attendees.extend(admin_ids)
    return availability_service.free_slots(
        db,
        attendees,
        target_date,
        target_date,
        duration_minutes,
        user,
    )


@router.get("/meetings/calendar")
@compat_router.get("/cm-meetings/calendar")
def get_meetings_calendar(
    from_date: date = Query(..., alias="from_date"),
    to_date: date = Query(..., alias="to_date"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.cm_meeting_service import fetch_my_meetings_for_calendar, meeting_to_calendar_dict

    _require_meetings_read(user)
    if to_date < from_date:
        raise HTTPException(status_code=400, detail="to_date must be on or after from_date")

    rows = fetch_my_meetings_for_calendar(db, user, from_date=from_date, to_date=to_date)
    return {
        "cm_meetings": [meeting_to_calendar_dict(m, db) for m in rows],
    }


# ---------------------------------------------------------------------------
# Booking & Rescheduling endpoints
# ---------------------------------------------------------------------------

@router.post("/meetings", status_code=201)
@compat_router.post("/cm-meetings", status_code=201)
def create_meeting(
    payload: MeetingCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.cm_meeting_service import (
        apply_attendee_selection,
        notify_meeting_invites_respecting_flags,
    )

    _require_meetings_write(user)
    _guard_meeting_write(user, payload.case_id, db)
    _validate_meeting_duration(payload.duration_minutes)
    _validate_meeting_link(payload.platform, payload.meeting_url)
    if payload.scheduled_date < today_ist():
        raise HTTPException(status_code=400, detail="Scheduled date cannot be in the past")

    if payload.meeting_type == MeetingType.OTHER:
        other_reason = (payload.other_reason or "").strip() or (payload.title or "").strip()
        if not other_reason:
            raise HTTPException(status_code=400, detail="Mandatory reason must be provided when Meeting Type is 'Other'")
    else:
        other_reason = (payload.other_reason or "").strip() or None

    role = effective_role(user)
    invite_therapist = payload.invite_therapist
    therapist_user_id = payload.therapist_user_id
    invite_client = payload.invite_client

    if role == RoleName.THERAPIST.value:
        therapist_user_id = user.id
        invite_therapist = True

    # Auto-resolve CM
    cm_id = None
    if payload.case_id:
        case = db.get(Case, payload.case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        cm_id = case.case_manager_user_id
    
    if not cm_id:
        if has_any_role(
            user,
            RoleName.CASE_MANAGER,
            RoleName.ADMIN,
            RoleName.SUPER_ADMIN,
            RoleName.MODULE_ADMIN,
        ):
            cm_id = user.id
        else:
            raise HTTPException(status_code=400, detail="Select a case with an assigned case manager")

    # Double Booking Prevention
    if payload.scheduled_time:
        attendees = [cm_id]
        if invite_therapist and therapist_user_id:
            attendees.append(therapist_user_id)
        if invite_client and payload.case_id:
            from app.services import parent_service
            parent_uid = parent_service.primary_parent_user_id_for_child(db, case.child_id) if case.child_id else None
            if parent_uid:
                attendees.append(parent_uid)
        if payload.mentor_user_id:
            attendees.append(payload.mentor_user_id)
        attendees.extend(payload.admin_user_ids)

        _validate_slot_in_availability(
            db,
            target_date=payload.scheduled_date,
            target_time=payload.scheduled_time,
            duration_minutes=payload.duration_minutes,
            attendee_ids=attendees,
            user=user,
        )
        conflicted, reason = check_conflicts(db, payload.scheduled_date, payload.scheduled_time, payload.duration_minutes, attendees)
        if conflicted:
            raise HTTPException(status_code=400, detail=f"Double booking error: {reason}")

    guest_json = _normalize_guest_emails(payload.guest_emails)

    meeting = CaseManagerMeeting(
        series_id=str(uuid.uuid4()),
        case_manager_user_id=cm_id,
        case_id=payload.case_id,
        parent_user_id=None,
        therapist_user_id=None,
        mentor_user_id=payload.mentor_user_id,
        scheduled_date=payload.scheduled_date,
        scheduled_time=payload.scheduled_time,
        duration_minutes=payload.duration_minutes,
        meeting_type=payload.meeting_type,
        other_reason=other_reason,
        title=payload.title or (other_reason if payload.meeting_type == MeetingType.OTHER else None),
        platform=payload.platform,
        meeting_url=(payload.meeting_url or "").strip() or None,
        guest_emails_json=guest_json,
        status=MeetingStatus.SCHEDULED,

        # Linked records
        linked_observation_report_id=payload.linked_observation_report_id,
        linked_observation_checklist_id=payload.linked_observation_checklist_id,
        linked_iep_id=payload.linked_iep_id,
        linked_monthly_report_id=payload.linked_monthly_report_id,
        linked_incident_id=payload.linked_incident_id,
        linked_ticket_id=payload.linked_ticket_id,
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
    send_meeting_reminder_if_within_hour(db, meeting, now_ist_dt=now_ist())

    commit_or_http(db)
    db.refresh(meeting)
    return _serialize(meeting, db, viewer=user)


@router.post("/meetings/{meeting_id}/reschedule")
def reschedule_meeting(
    meeting_id: int,
    payload: MeetingReschedulePayload,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.cm_meeting_service import (
        apply_attendee_selection,
        notify_meeting_invites_respecting_flags,
    )

    _require_meetings_write(user)
    meeting = db.get(CaseManagerMeeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    _guard_meeting_write(user, meeting.case_id, db, meeting=meeting)
    _validate_meeting_duration(payload.duration_minutes)

    # Prevent double booking on new slot
    attendees = list(meeting_participant_user_ids(meeting))

    _validate_slot_in_availability(
        db,
        target_date=payload.scheduled_date,
        target_time=payload.scheduled_time,
        duration_minutes=payload.duration_minutes,
        attendee_ids=attendees,
        user=user,
    )
    conflicted, reason = check_conflicts(
        db,
        payload.scheduled_date,
        payload.scheduled_time,
        payload.duration_minutes,
        attendees,
        ignore_meeting_id=meeting.id,
    )
    if conflicted:
        raise HTTPException(status_code=400, detail=f"Double booking error on new slot: {reason}")

    # Mark current as RESCHEDULED
    meeting.status = MeetingStatus.RESCHEDULED
    meeting.reschedule_reason = payload.reschedule_reason

    # Create replacement meeting
    replacement = CaseManagerMeeting(
        series_id=meeting.series_id or str(uuid.uuid4()),
        case_manager_user_id=meeting.case_manager_user_id,
        case_id=meeting.case_id,
        parent_user_id=meeting.parent_user_id,
        therapist_user_id=meeting.therapist_user_id,
        mentor_user_id=meeting.mentor_user_id,
        scheduled_date=payload.scheduled_date,
        scheduled_time=payload.scheduled_time,
        duration_minutes=payload.duration_minutes,
        meeting_type=meeting.meeting_type,
        other_reason=meeting.other_reason,
        title=meeting.title,
        platform=meeting.platform,
        meeting_url=meeting.meeting_url,
        guest_emails_json=meeting.guest_emails_json,
        staff_attendee_user_ids_json=meeting.staff_attendee_user_ids_json,
        status=MeetingStatus.SCHEDULED,
        rescheduled_from_id=meeting.id,

        # Link clinical items
        linked_observation_report_id=meeting.linked_observation_report_id,
        linked_observation_checklist_id=meeting.linked_observation_checklist_id,
        linked_iep_id=meeting.linked_iep_id,
        linked_monthly_report_id=meeting.linked_monthly_report_id,
        linked_incident_id=meeting.linked_incident_id,
        linked_ticket_id=meeting.linked_ticket_id,
    )

    db.add(replacement)
    db.flush()

    notify_meeting_invites_respecting_flags(
        db,
        replacement,
        actor_user_id=user.id,
        invite_case_manager=True,
    )
    send_meeting_reminder_if_within_hour(db, replacement, now_ist_dt=now_ist())

    db.commit()
    db.refresh(replacement)
    db.refresh(meeting)
    return {
        "old_meeting": _serialize(meeting, db, viewer=user),
        "new_meeting": _serialize(replacement, db, viewer=user)
    }


# ---------------------------------------------------------------------------
# Listing & Filtering endpoints
# ---------------------------------------------------------------------------

@router.get("/meetings")
@compat_router.get("/cm-meetings")
def list_meetings(
    case_id: Optional[int] = None,
    status: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    meeting_type: Optional[str] = None,
    case_manager_user_id: Optional[int] = None,
    participant_role: Optional[str] = Query(
        None,
        description="Filter by participant role: case_manager | therapist | admin",
    ),
    participant_user_ids: Optional[str] = Query(
        None,
        description="Comma-separated participant user ids (used with participant_role)",
    ),
    search: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_meetings_read(user)
    role = effective_role(user)

    try:
        participant_ids = parse_int_list(participant_user_ids)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Looks like we still need valid participant_user_ids (comma-separated integers).",
        ) from exc

    participant_role_norm = (participant_role or "").strip().lower() or None
    if participant_role_norm and participant_role_norm not in {
        "case_manager",
        "therapist",
        "admin",
    }:
        raise HTTPException(
            status_code=400,
            detail="participant_role must be case_manager, therapist, or admin.",
        )
    
    stmt = select(CaseManagerMeeting).options(
        selectinload(CaseManagerMeeting.actions)
    ).order_by(
        CaseManagerMeeting.scheduled_date.desc(),
        CaseManagerMeeting.scheduled_time.desc()
    )

    if _is_case_manager_scoped(user):
        stmt = stmt.where(_case_manager_meeting_scope(user, db))
    elif role == RoleName.SUPERVISOR.value and not user_has_permission(user, "admin.override"):
        from app.services.admin_scope_service import scoped_case_ids_subquery
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
    elif role == RoleName.PARENT.value:
        from app.services import parent_service
        child_ids = parent_service.child_ids_for_parent(db, user.id)
        if not child_ids:
            return []
        case_ids = list(db.scalars(select(Case.id).where(Case.child_id.in_(child_ids))).all())
        if not case_ids:
            return []
        stmt = stmt.where(
            CaseManagerMeeting.case_id.in_(case_ids),
            CaseManagerMeeting.status != MeetingStatus.CANCELLED,
        )

    if case_id is not None:
        stmt = stmt.where(CaseManagerMeeting.case_id == case_id)
    if status:
        try:
            stmt = stmt.where(CaseManagerMeeting.status == MeetingStatus(status.upper()))
        except ValueError:
            pass
    else:
        stmt = stmt.where(CaseManagerMeeting.status != MeetingStatus.RESCHEDULED)
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

    # Participant role filter (SQL for CM/therapist; admin JSON post-filtered below).
    if participant_role_norm and participant_ids:
        if participant_role_norm == "case_manager":
            stmt = stmt.where(CaseManagerMeeting.case_manager_user_id.in_(participant_ids))
        elif participant_role_norm == "therapist":
            stmt = stmt.where(CaseManagerMeeting.therapist_user_id.in_(participant_ids))

    meetings = list(db.scalars(stmt).all())
    from app.services.admin_scope_service import user_sees_global_cases
    if role in {
        RoleName.ADMIN.value,
        RoleName.SUPER_ADMIN.value,
        RoleName.MODULE_ADMIN.value,
    } and not user_has_permission(user, "admin.override") and not user_sees_global_cases(user):
        from app.services.cm_meeting_service import user_can_view_meeting
        meetings = [m for m in meetings if user_can_view_meeting(m, user.id)]

    if participant_role_norm == "admin" and participant_ids:
        id_set = set(participant_ids)
        meetings = [
            m
            for m in meetings
            if id_set.intersection(parse_staff_attendee_ids(m.staff_attendee_user_ids_json))
        ]

    return _serialize_many(meetings, db, viewer=user)


@router.get("/meetings/pending-completion")
@compat_router.get("/cm-meetings/pending-completion")
def list_pending_completion_meetings(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_meetings_read(user)
    today = today_ist()
    
    # Scheduled meetings in the past (notes missing), or completed in the past with missing notes
    # We query all meetings that are SCHEDULED in the past, or COMPLETED but have missing notes.
    stmt = (
        select(CaseManagerMeeting).options(selectinload(CaseManagerMeeting.actions))
        .where(
            or_(
                # Scheduled in the past
                (CaseManagerMeeting.status == MeetingStatus.SCHEDULED) & (CaseManagerMeeting.scheduled_date < today),
                # Completed, but missing notes
                (CaseManagerMeeting.status == MeetingStatus.COMPLETED) & 
                (or_(CaseManagerMeeting.notes_outcome.is_(None), CaseManagerMeeting.notes_summary.is_(None) | (CaseManagerMeeting.notes_summary == '')))
            )
        )
        .order_by(CaseManagerMeeting.scheduled_date.asc())
        .limit(50)
    )

    role = effective_role(user)
    if _is_case_manager_scoped(user):
        stmt = stmt.where(_case_manager_meeting_scope(user, db))

    meetings = db.scalars(stmt).all()
    if role == RoleName.THERAPIST.value:
        meetings = [m for m in meetings if user_can_view_meeting(m, user.id)]

    return _serialize_many(meetings, db, viewer=user)


# ---------------------------------------------------------------------------
# Notes & Actions updates
# ---------------------------------------------------------------------------

async def _sync_meeting_docs(
    db: Session,
    user: User,
    meeting: CaseManagerMeeting,
    *,
    notes_summary: str | None = None,
    file: UploadFile | None = None,
) -> list[dict]:
    created_docs: list[dict] = []
    if file is not None:
        attachment = await doc_svc.create_meeting_attachment_document(db, user, meeting, file=file)
        created_docs.append(attachment.model_dump())
    if meeting.case_id and meeting.status == MeetingStatus.COMPLETED and (notes_summary or "").strip():
        notes_doc = await doc_svc.upsert_meeting_notes_document(
            db,
            user,
            meeting,
            notes_summary=notes_summary or "",
        )
        if notes_doc is not None:
            created_docs.append(notes_doc.model_dump())
    return created_docs


def _apply_meeting_notes_updates(
    meeting: CaseManagerMeeting,
    *,
    notes_outcome: str | None = None,
    notes_summary: str | None = None,
    notes_next_meeting_required: bool | None = None,
    notes_additional: str | None = None,
    therapist_notes: str | None = None,
) -> None:
    if notes_outcome is not None:
        meeting.notes_outcome = notes_outcome.strip() or None
    if notes_summary is not None:
        meeting.notes_summary = notes_summary.strip() or None
    if notes_next_meeting_required is not None:
        meeting.notes_next_meeting_required = notes_next_meeting_required
    if notes_additional is not None:
        meeting.notes_additional = notes_additional.strip() or None
    if therapist_notes is not None:
        meeting.therapist_notes = therapist_notes.strip() or None


@router.patch("/meetings/{meeting_id}")
@compat_router.patch("/cm-meetings/{meeting_id}")
def update_meeting(
    meeting_id: int,
    payload: MeetingNotesUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_meetings_write(user)
    meeting = db.get(CaseManagerMeeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    _guard_meeting_write(user, meeting.case_id, db, meeting=meeting)
    role = effective_role(user)
    is_therapist = role == RoleName.THERAPIST.value
    if _is_case_manager_scoped(user) and meeting.case_manager_user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your meeting")

    if any(
        value is not None
        for value in (payload.scheduled_date, payload.scheduled_time, payload.duration_minutes)
    ):
        raise HTTPException(status_code=400, detail="Use reschedule to change meeting date, time, or duration.")

    if is_therapist:
        if payload.status is not None and payload.status != meeting.status:
            raise HTTPException(status_code=403, detail="Only the case manager can update meeting status")
        cm_only_fields = (
            payload.notes_outcome,
            payload.notes_summary,
            payload.notes_next_meeting_required,
            payload.notes_additional,
            payload.actions,
            payload.title,
            payload.other_reason,
            payload.platform,
            payload.meeting_url,
            payload.guest_emails,
            payload.therapist_user_id,
            payload.mentor_user_id,
            payload.linked_observation_report_id,
            payload.linked_observation_checklist_id,
            payload.linked_iep_id,
            payload.linked_monthly_report_id,
            payload.linked_incident_id,
            payload.linked_ticket_id,
        )
        if any(v is not None for v in cm_only_fields):
            raise HTTPException(status_code=403, detail="Therapists can only save their own meeting discussion notes")
        if payload.therapist_notes is not None:
            meeting.therapist_notes = payload.therapist_notes.strip() or None
        db.commit()
        db.refresh(meeting)
        return _serialize(meeting, db, viewer=user)

    if payload.therapist_notes is not None:
        raise HTTPException(status_code=403, detail="Therapist notes can only be edited by the therapist")

    if payload.duration_minutes is not None:
        _validate_meeting_duration(payload.duration_minutes)
    if payload.meeting_url is not None:
        _validate_meeting_link(payload.platform or meeting.platform, payload.meeting_url)

    completing = payload.status == MeetingStatus.COMPLETED
    if completing and not _can_complete_meeting(user, meeting):
        raise HTTPException(status_code=403, detail="Only the assigned case manager can complete this meeting")
    if completing:
        meeting_start = _meeting_start_dt(meeting.scheduled_date, meeting.scheduled_time)
        if meeting_start and meeting_start > now_ist():
            raise HTTPException(status_code=400, detail="You can only mark a meeting complete after its scheduled start time.")
        outcome = payload.notes_outcome if payload.notes_outcome is not None else meeting.notes_outcome
        summary = payload.notes_summary if payload.notes_summary is not None else meeting.notes_summary
        if not outcome or not outcome.strip() or not summary or not summary.strip():
            raise HTTPException(
                status_code=400,
                detail="Meeting Outcome and Discussion Summary are required before completing the meeting. Silent closures are blocked."
            )

    if payload.status is not None:
        meeting.status = payload.status
        if payload.status == MeetingStatus.COMPLETED:
            meeting.completed_at = now_ist()
            meeting.completed_by_user_id = user.id

    if payload.title is not None:
        meeting.title = payload.title
    if payload.other_reason is not None:
        meeting.other_reason = payload.other_reason
    if payload.platform is not None:
        meeting.platform = payload.platform
    if payload.meeting_url is not None:
        meeting.meeting_url = (payload.meeting_url or "").strip() or None
    if payload.guest_emails is not None:
        meeting.guest_emails_json = _normalize_guest_emails(payload.guest_emails)

    if payload.notes_outcome is not None:
        meeting.notes_outcome = payload.notes_outcome
    if payload.notes_summary is not None:
        meeting.notes_summary = payload.notes_summary
    if payload.notes_next_meeting_required is not None:
        meeting.notes_next_meeting_required = payload.notes_next_meeting_required
    if payload.notes_additional is not None:
        meeting.notes_additional = payload.notes_additional

    if payload.therapist_user_id is not None:
        meeting.therapist_user_id = payload.therapist_user_id
    if payload.mentor_user_id is not None:
        meeting.mentor_user_id = payload.mentor_user_id
    if payload.scheduled_date is not None:
        meeting.scheduled_date = payload.scheduled_date
    if payload.scheduled_time is not None:
        meeting.scheduled_time = payload.scheduled_time
    if payload.duration_minutes is not None:
        meeting.duration_minutes = payload.duration_minutes

    if payload.linked_observation_report_id is not None:
        meeting.linked_observation_report_id = payload.linked_observation_report_id
    if payload.linked_observation_checklist_id is not None:
        meeting.linked_observation_checklist_id = payload.linked_observation_checklist_id
    if payload.linked_iep_id is not None:
        meeting.linked_iep_id = payload.linked_iep_id
    if payload.linked_monthly_report_id is not None:
        meeting.linked_monthly_report_id = payload.linked_monthly_report_id
    if payload.linked_incident_id is not None:
        meeting.linked_incident_id = payload.linked_incident_id
    if payload.linked_ticket_id is not None:
        meeting.linked_ticket_id = payload.linked_ticket_id

    if payload.actions is not None:
        existing_actions = {act.id: act for act in list(meeting.actions)}
        kept_ids: set[int] = set()
        for act_schema in payload.actions:
            if act_schema.id is not None and act_schema.id in existing_actions:
                action = existing_actions[act_schema.id]
                action.title = act_schema.title
                action.owner_role = act_schema.owner_role
                action.due_date = act_schema.due_date
                if act_schema.status is not None:
                    action.status = act_schema.status
                kept_ids.add(action.id)
                continue

            new_action = MeetingAction(
                meeting_id=meeting.id,
                title=act_schema.title,
                owner_role=act_schema.owner_role,
                due_date=act_schema.due_date,
                status=act_schema.status or "open",
            )
            db.add(new_action)

        for action_id, action in existing_actions.items():
            if action_id not in kept_ids and all((item.id is None or item.id != action_id) for item in payload.actions):
                db.delete(action)

    db.flush()
    if meeting.case_id and meeting.status == MeetingStatus.COMPLETED and (meeting.notes_summary or "").strip():
        doc_svc.upsert_meeting_notes_document(
            db,
            user,
            meeting,
            notes_summary=meeting.notes_summary or "",
        )

    db.commit()
    db.refresh(meeting)
    return _serialize(meeting, db, viewer=user)


@router.post("/meetings/{meeting_id}/notes")
@compat_router.post("/cm-meetings/{meeting_id}/notes")
async def save_meeting_notes(
    meeting_id: int,
    notes_outcome: Optional[str] = Form(None),
    notes_summary: Optional[str] = Form(None),
    notes_next_meeting_required: Optional[bool] = Form(None),
    notes_additional: Optional[str] = Form(None),
    therapist_notes: Optional[str] = Form(None),
    status: Optional[MeetingStatus] = Form(None),
    file: Optional[UploadFile] = File(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_meetings_write(user)
    meeting = db.get(CaseManagerMeeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    _guard_meeting_write(user, meeting.case_id, db, meeting=meeting)
    role = effective_role(user)
    is_therapist = role == RoleName.THERAPIST.value

    if is_therapist:
        if file is not None:
            raise HTTPException(status_code=400, detail="File uploads are available for case-linked shared minutes only")
        if any(
            value is not None
            for value in (notes_outcome, notes_summary, notes_next_meeting_required, notes_additional, status)
        ):
            raise HTTPException(status_code=403, detail="Therapists can only save their own meeting notes")
        if therapist_notes is not None:
            meeting.therapist_notes = therapist_notes.strip() or None
        db.commit()
        db.refresh(meeting)
        return _serialize(meeting, db, viewer=user)

    if therapist_notes is not None:
        raise HTTPException(status_code=403, detail="Therapist notes can only be edited by the therapist")

    _apply_meeting_notes_updates(
        meeting,
        notes_outcome=notes_outcome,
        notes_summary=notes_summary,
        notes_next_meeting_required=notes_next_meeting_required,
        notes_additional=notes_additional,
    )
    if status is not None:
        meeting.status = status
        if status == MeetingStatus.COMPLETED:
            meeting.completed_at = now_ist()
            meeting.completed_by_user_id = user.id

    if file is not None and not meeting.case_id:
        raise HTTPException(status_code=400, detail="File uploads require a case-linked meeting")

    final_summary = (meeting.notes_summary or "").strip()
    final_outcome = (meeting.notes_outcome or "").strip()
    if meeting.status == MeetingStatus.COMPLETED and (not final_summary or not final_outcome):
        raise HTTPException(
            status_code=400,
            detail="Shared minutes outcome and summary are required before completing the meeting.",
        )

    db.flush()
    if file is not None:
        await doc_svc.create_meeting_attachment_document(db, user, meeting, file=file)
    if meeting.case_id and meeting.status == MeetingStatus.COMPLETED and final_summary:
        doc_svc.upsert_meeting_notes_document(
            db,
            user,
            meeting,
            notes_summary=final_summary,
        )

    db.commit()
    db.refresh(meeting)
    return _serialize(meeting, db, viewer=user)


@router.post("/meetings/{meeting_id}/cancel")
def cancel_meeting_post(
    meeting_id: int,
    payload: MeetingCancelPayload,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_meetings_write(user)
    meeting = db.get(CaseManagerMeeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    _guard_meeting_write(user, meeting.case_id, db, meeting=meeting)
    if _is_case_manager_scoped(user) and meeting.case_manager_user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your meeting")

    reason = (payload.reason or "").strip()
    if len(reason) < 3:
        raise HTTPException(status_code=400, detail="Use the cancel endpoint with a reason of at least 3 characters.")

    meeting.status = MeetingStatus.CANCELLED
    meeting.cancel_reason = reason
    meeting.cancelled_by_user_id = user.id
    meeting.cancelled_at = now_ist()
    notify_meeting_cancellation(db, meeting, actor_user_id=user.id)
    db.commit()
    db.refresh(meeting)
    return _serialize(meeting, db, viewer=user)


@router.delete("/meetings/{meeting_id}", status_code=204)
@compat_router.delete("/cm-meetings/{meeting_id}", status_code=204)
def cancel_meeting(
    meeting_id: int,
    reason: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not reason or len(reason.strip()) < 3:
        raise HTTPException(status_code=400, detail="Use POST /api/v1/meetings/{meeting_id}/cancel with a reason.")

    cancel_meeting_post(
        meeting_id=meeting_id,
        payload=MeetingCancelPayload(reason=reason),
        user=user,
        db=db,
    )


# ---------------------------------------------------------------------------
# Dashboard Action Tracking
# ---------------------------------------------------------------------------

@router.get("/meetings/actions")
def list_open_actions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_meetings_read(user)
    role = effective_role(user)

    stmt = select(MeetingAction).join(CaseManagerMeeting).where(MeetingAction.status == "open")

    if role == RoleName.PARENT.value:
        from app.services import parent_service
        child_ids = parent_service.child_ids_for_parent(db, user.id)
        case_ids = list(db.scalars(select(Case.id).where(Case.child_id.in_(child_ids))).all())
        stmt = stmt.where(
            MeetingAction.owner_role == "parent",
            CaseManagerMeeting.case_id.in_(case_ids)
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
        stmt = stmt.where(
            MeetingAction.owner_role == "therapist",
            CaseManagerMeeting.case_id.in_(assigned_case_ids)
        )
    elif _is_case_manager_scoped(user):
        stmt = stmt.where(CaseManagerMeeting.case_manager_user_id == user.id)

    actions = db.scalars(stmt.order_by(MeetingAction.due_date.asc())).all()

    return [
        {
            "id": a.id,
            "meeting_id": a.meeting_id,
            "meeting_title": a.meeting.title or a.meeting.meeting_type.value,
            "case_code": db.scalar(select(Case.case_code).where(Case.id == a.meeting.case_id)) if a.meeting.case_id else None,
            "title": a.title,
            "owner_role": a.owner_role,
            "due_date": a.due_date.isoformat() if a.due_date else None,
            "status": a.status,
        }
        for a in actions
    ]


@router.patch("/meetings/actions/{action_id}")
def toggle_action_status(
    action_id: int,
    status: str = Query(..., description="open or completed"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_meetings_write(user)
    action = db.get(MeetingAction, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action item not found")

    meeting = db.get(CaseManagerMeeting, action.meeting_id)
    _guard_meeting_write(user, meeting.case_id, db, meeting=meeting)

    if status not in {"open", "completed"}:
        raise HTTPException(status_code=400, detail="Invalid status")

    action.status = status
    db.commit()
    db.refresh(action)
    return {
        "id": action.id,
        "title": action.title,
        "status": action.status,
    }


# ---------------------------------------------------------------------------
# Admin Productivity Dashboard & Analytics
# ---------------------------------------------------------------------------

@router.get("/meetings/productivity")
def case_manager_productivity_analytics(
    year: Optional[int] = None,
    month: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Admin/SuperAdmin/ModuleAdmin/Supervisor only
    if not has_any_role(
        user,
        RoleName.SUPER_ADMIN,
        RoleName.ADMIN,
        RoleName.MODULE_ADMIN,
        RoleName.SUPERVISOR,
    ) and not user_has_permission(user, "admin.override"):
        raise HTTPException(status_code=403, detail="Analytics restricted to administrators.")

    from app.core.timezone import today_ist
    today = today_ist()

    # Query Case Managers
    cms = db.scalars(select(User).where(User.roles.any(name=RoleName.CASE_MANAGER.value))).all()

    analytics = []
    for cm in cms:
        # Base filter
        stmt = select(CaseManagerMeeting).where(CaseManagerMeeting.case_manager_user_id == cm.id)
        if year:
            stmt = stmt.where(extract("year", CaseManagerMeeting.scheduled_date) == year)
        if month:
            stmt = stmt.where(extract("month", CaseManagerMeeting.scheduled_date) == month)

        meetings = db.scalars(stmt).all()

        completed = [m for m in meetings if m.status == MeetingStatus.COMPLETED]
        cancelled = [m for m in meetings if m.status == MeetingStatus.CANCELLED]
        
        # Pending notes calculation
        pending_notes = 0
        for m in meetings:
            notes_missing = not m.notes_outcome or not m.notes_summary
            if notes_missing:
                if m.status == MeetingStatus.SCHEDULED and m.scheduled_date <= today:
                    pending_notes += 1
                elif m.status == MeetingStatus.COMPLETED:
                    pending_notes += 1

        # Calculate completed hours
        completed_hours = sum(m.duration_minutes for m in completed) / 60.0

        # Group by type
        type_distribution = {}
        for m in completed:
            t = m.meeting_type.value
            type_distribution[t] = type_distribution.get(t, 0) + 1

        analytics.append({
            "case_manager_id": cm.id,
            "case_manager_name": cm.full_name,
            "meetings_completed": len(completed),
            "meeting_hours": round(completed_hours, 2),
            "pending_notes": pending_notes,
            "cancelled_meetings": len(cancelled),
            "types": type_distribution,
        })

    return analytics


# ---------------------------------------------------------------------------
# Monthly Exports
# ---------------------------------------------------------------------------

@router.get("/meetings/export")
def export_meetings(
    format: str = Query(..., description="excel, csv, or pdf"),
    year: Optional[int] = None,
    month: Optional[int] = None,
    case_id: Optional[int] = None,
    status: Optional[str] = None,
    meeting_type: Optional[str] = None,
    case_manager_user_id: Optional[int] = None,
    participant_role: Optional[str] = Query(
        None,
        description="Filter by participant role: case_manager | therapist | admin",
    ),
    participant_user_ids: Optional[str] = Query(
        None,
        description="Comma-separated participant user ids (used with participant_role)",
    ),
    search: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_meetings_read(user)

    # 1. Fetch meetings using general list logic
    meetings = list_meetings(
        case_id=case_id,
        status=status,
        year=year,
        month=month,
        meeting_type=meeting_type,
        case_manager_user_id=case_manager_user_id,
        participant_role=participant_role,
        participant_user_ids=participant_user_ids,
        search=search,
        user=user,
        db=db,
    )

    if len(meetings) > 10000:
        raise HTTPException(status_code=400, detail="Export is limited to 10,000 meetings at a time.")

    headers = [
        "Meeting ID", "Case Code", "Client Name", "Meeting Type", "Date",
        "Duration (Mins)", "Attendees", "Scheduled By", "Outcome", "Summary",
        "Action Items", "Status"
    ]

    rows = []
    for m in meetings:
        attendee_names = ", ".join([a["name"] for a in m["attendees"]])
        actions_list = "; ".join([f"{a['title']} ({a['owner_role']}: {a['status']})" for a in m["actions"]])
        rows.append([
            m["id"],
            m["case_code"] or "—",
            m["child_name"] or "—",
            m["meeting_type"],
            m["scheduled_date"],
            m["duration_minutes"],
            attendee_names,
            m["case_manager_name"] or "—",
            m["notes_outcome"] or "—",
            m["notes_summary"] or "—",
            actions_list,
            m["display_status"] or m["status"]
        ])

    if format.lower() == "csv":
        csv_buffer = StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(headers)
        writer.writerows(rows)
        csv_buffer.seek(0)
        return StreamingResponse(
            BytesIO(csv_buffer.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=meetings_export_{year or 'all'}_{month or 'all'}.csv"}
        )

    elif format.lower() == "excel":
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Meetings"

        # Headers styling
        ws.append(headers)
        for row in rows:
            ws.append(row)

        stream = BytesIO()
        wb.save(stream)
        stream.seek(0)
        return StreamingResponse(
            stream,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=meetings_export_{year or 'all'}_{month or 'all'}.xlsx"}
        )

    elif format.lower() == "pdf":
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

        stream = BytesIO()
        doc = SimpleDocTemplate(stream, pagesize=landscape(letter), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        story = []

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#1e293b'),
            spaceAfter=15
        )
        body_style = ParagraphStyle(
            'BodyStyle',
            parent=styles['Normal'],
            fontSize=8,
            leading=10
        )
        header_style = ParagraphStyle(
            'HeaderStyle',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.white,
            fontName='Helvetica-Bold'
        )

        title = f"Meetings Export - {year or 'All Years'} / {month or 'All Months'}"
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 10))

        # Format table data
        table_data = [[Paragraph(h, header_style) for h in headers]]
        for row in rows:
            table_data.append([
                Paragraph(str(cell), body_style) for cell in row
            ])

        # Column widths: page width is 792 - 60 = 732
        # Widths: ID=35, Case=45, Client=70, Type=80, Date=60, Dur=30, Attendees=100, By=70, Out=60, Sum=90, Act=60, Stat=32
        col_widths = [35, 45, 70, 80, 60, 30, 100, 70, 60, 90, 60, 32]
        t = Table(table_data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4f46e5')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 0), (-1, 0), 6),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
        ]))

        story.append(t)
        doc.build(story)
        stream.seek(0)
        return StreamingResponse(
            stream,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=meetings_export_{year or 'all'}_{month or 'all'}.pdf"}
        )

    raise HTTPException(status_code=400, detail="Invalid format. Use excel, csv, or pdf.")


# ---------------------------------------------------------------------------
# Backward Compatibility Endpoint Redirect (optional wrapper)
# ---------------------------------------------------------------------------


@router.get("/meetings/{meeting_id}")
def get_meeting(
    meeting_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_meetings_read(user)
    stmt = _meetings_scope_stmt(user, db)
    meeting = db.scalars(stmt.where(CaseManagerMeeting.id == meeting_id)).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    role = effective_role(user)
    if role in {
        RoleName.ADMIN.value,
        RoleName.SUPER_ADMIN.value,
        RoleName.MODULE_ADMIN.value,
    } and not user_has_permission(user, "admin.override") and not user_sees_global_cases(user):
        if not user_can_view_meeting(meeting, user.id):
            raise HTTPException(status_code=404, detail="Meeting not found")

    return _serialize(meeting, db, viewer=user)


@router.get("/meetings/{meeting_id}/documents")
def list_meeting_documents(
    meeting_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_meetings_read(user)
    meeting = db.scalars(_meetings_scope_stmt(user, db, include_rescheduled=True).where(CaseManagerMeeting.id == meeting_id)).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return doc_svc.list_for_meeting_series(db, user, meeting.id)


@router.get("/parent/cm-meetings")
def parent_cm_meetings_compat(
    year: Optional[int] = None,
    month: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Point directly to list_meetings
    return list_meetings(year=year, month=month, user=user, db=db)
