"""Case manager meeting invites, attendees, and calendar helpers."""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from typing import Any, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.case_manager_meeting import CaseManagerMeeting, MeetingStatus, MeetingType
from app.core.config import settings
from app.core.permissions import RoleName
from app.models.user import User
from app.services import notification_service, parent_service
from app.services.email.google_calendar import build_google_calendar_add_url
from app.services.email.service import cm_meeting_invite_email


def parse_staff_attendee_ids(raw: str | None) -> list[int]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [int(x) for x in data if x is not None]
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    return []


def dump_staff_attendee_ids(ids: list[int]) -> str | None:
    clean = sorted({int(i) for i in ids if i})
    return json.dumps(clean) if clean else None


def meeting_participant_user_ids(meeting: CaseManagerMeeting) -> set[int]:
    ids: set[int] = set()
    if meeting.case_manager_user_id:
        ids.add(meeting.case_manager_user_id)
    if meeting.parent_user_id:
        ids.add(meeting.parent_user_id)
    if meeting.therapist_user_id:
        ids.add(meeting.therapist_user_id)
    ids.update(parse_staff_attendee_ids(meeting.staff_attendee_user_ids_json))
    return ids


def user_can_view_meeting(meeting: CaseManagerMeeting, user_id: int) -> bool:
    return user_id in meeting_participant_user_ids(meeting)


def parse_guest_emails(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(e).strip().lower() for e in data if e and str(e).strip()]
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    return []


def _format_meeting_when(meeting: CaseManagerMeeting) -> str:
    when = meeting.scheduled_date.isoformat() if meeting.scheduled_date else ""
    if meeting.scheduled_time:
        when = f"{when} {meeting.scheduled_time.strftime('%H:%M')}"
    return when.strip()


def _meeting_type_label(meeting_type: MeetingType | None) -> str:
    labels = {
        MeetingType.CLIENT_ONLY: "Progress review",
        MeetingType.CLIENT_AND_THERAPIST: "Care coordination",
        MeetingType.IEP_MEETING: "IEP discussion",
        MeetingType.SUPERVISION: "Internal meeting",
    }
    if meeting_type:
        return labels.get(meeting_type, meeting_type.value.replace("_", " ").title())
    return "Case manager meeting"


def build_attendee_rows(meeting: CaseManagerMeeting, db: Session) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(role: str, user: User | None) -> None:
        if not user:
            return
        rows.append({"role": role, "user_id": user.id, "name": user.full_name or user.email})

    cm = db.get(User, meeting.case_manager_user_id)
    add("case_manager", cm)
    if meeting.parent_user_id:
        add("client", db.get(User, meeting.parent_user_id))
    if meeting.therapist_user_id:
        add("therapist", db.get(User, meeting.therapist_user_id))
    for uid in parse_staff_attendee_ids(meeting.staff_attendee_user_ids_json):
        if uid == meeting.case_manager_user_id:
            continue
        u = db.get(User, uid)
        add("admin", u)
    return rows


def _end_time_from_start(start: time | None, duration_minutes: int) -> str | None:
    if not start:
        return None
    base = datetime.combine(date.today(), start)
    end = base + timedelta(minutes=max(duration_minutes, 15))
    return end.time().strftime("%H:%M")


def meeting_to_calendar_dict(meeting: CaseManagerMeeting, db: Session) -> dict[str, Any]:
    case = db.get(Case, meeting.case_id) if meeting.case_id else None
    child_name = case.child.full_name if case and case.child else None
    return {
        "id": meeting.id,
        "kind": "cm_meeting",
        "case_id": meeting.case_id,
        "case_code": case.case_code if case else None,
        "child_name": child_name,
        "date": meeting.scheduled_date.isoformat() if meeting.scheduled_date else None,
        "start_time": meeting.scheduled_time.strftime("%H:%M") if meeting.scheduled_time else None,
        "end_time": _end_time_from_start(meeting.scheduled_time, meeting.duration_minutes),
        "duration_minutes": meeting.duration_minutes,
        "title": meeting.title or _meeting_type_label(meeting.meeting_type),
        "meeting_type": meeting.meeting_type.value if meeting.meeting_type else None,
        "status": meeting.status.value if meeting.status else None,
        "meeting_url": meeting.meeting_url,
    }


def fetch_cm_meetings_for_user(
    db: Session,
    user_id: int,
    *,
    from_date: date,
    to_date: date,
) -> list[CaseManagerMeeting]:
    """Scheduled CM meetings in range where the user is a participant."""
    stmt = (
        select(CaseManagerMeeting)
        .where(
            CaseManagerMeeting.scheduled_date >= from_date,
            CaseManagerMeeting.scheduled_date <= to_date,
            CaseManagerMeeting.status == MeetingStatus.SCHEDULED,
        )
        .order_by(CaseManagerMeeting.scheduled_date, CaseManagerMeeting.scheduled_time)
    )
    rows = db.scalars(stmt).all()
    return [m for m in rows if user_can_view_meeting(m, user_id)]


def fetch_cm_meetings_for_therapist_calendar(
    db: Session,
    therapist_user_id: int,
    *,
    from_date: date,
    to_date: date,
    case_id: int | None = None,
) -> list[CaseManagerMeeting]:
    assigned_case_ids = list(
        db.scalars(
            select(CaseAssignment.case_id).where(
                CaseAssignment.therapist_user_id == therapist_user_id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
        ).all()
    )
    stmt = select(CaseManagerMeeting).where(
        CaseManagerMeeting.scheduled_date >= from_date,
        CaseManagerMeeting.scheduled_date <= to_date,
        CaseManagerMeeting.status == MeetingStatus.SCHEDULED,
    )
    if case_id is not None:
        stmt = stmt.where(CaseManagerMeeting.case_id == case_id)
    rows = list(db.scalars(stmt.order_by(CaseManagerMeeting.scheduled_date)).all())
    return [m for m in rows if user_can_view_meeting(m, therapist_user_id)]


def resolve_active_therapist_for_case(db: Session, case_id: int) -> int | None:
    row = db.scalars(
        select(CaseAssignment.therapist_user_id).where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
    ).first()
    return row


def apply_attendee_selection(
    db: Session,
    meeting: CaseManagerMeeting,
    *,
    invite_client: bool,
    invite_therapist: bool,
    therapist_user_id: int | None,
    admin_user_ids: list[int],
    case_id: int | None,
) -> None:
    if invite_client and case_id:
        case = db.get(Case, case_id)
        if case and case.child_id:
            meeting.parent_user_id = parent_service.primary_parent_user_id_for_child(db, case.child_id)
    else:
        meeting.parent_user_id = None

    if invite_therapist:
        tid = therapist_user_id
        if not tid and case_id:
            tid = resolve_active_therapist_for_case(db, case_id)
        meeting.therapist_user_id = tid
    else:
        meeting.therapist_user_id = None

    meeting.staff_attendee_user_ids_json = dump_staff_attendee_ids(admin_user_ids)


def _portal_url_for_user(user: User) -> str:
    base = (settings.frontend_url or "http://localhost:5173").rstrip("/")
    role = getattr(user, "role_name", None) or (
        user.roles[0].name if getattr(user, "roles", None) and user.roles else ""
    )
    if role == RoleName.PARENT.value:
        return f"{base}/parent"
    if role == RoleName.THERAPIST.value:
        return f"{base}/therapist/cm-meetings"
    return f"{base}/admin/cm-meetings"


def _meeting_calendar_details(
    *,
    organizer_name: str,
    child_name: str | None,
    case_code: str | None,
    meeting_url: str | None,
    portal_url: str | None,
) -> str:
    lines = [f"Organizer: {organizer_name}"]
    if child_name or case_code:
        case_bits = [p for p in [child_name, f"({case_code})" if case_code else None] if p]
        lines.append(f"Case: {' '.join(case_bits)}")
    if meeting_url:
        lines.append(f"Join: {meeting_url}")
    if portal_url:
        lines.append(f"Insighte: {portal_url}")
    return "\n".join(lines)


def send_meeting_invite_emails(
    db: Session,
    meeting: CaseManagerMeeting,
    *,
    actor_user_id: int,
    invite_case_manager: bool,
    is_update: bool = False,
) -> None:
    """Email invited stakeholders (portal users + guests). The booker does not receive email."""
    case = db.get(Case, meeting.case_id) if meeting.case_id else None
    child_name = case.child.full_name if case and case.child else None
    case_code = case.case_code if case else None
    label = _meeting_type_label(meeting.meeting_type)
    title_text = meeting.title or label
    when = _format_meeting_when(meeting)
    actor = db.get(User, actor_user_id)
    organizer_name = (actor.full_name if actor else None) or "Insighte"
    actor_email = (actor.email or "").strip().lower() if actor and actor.email else ""

    sent_to: set[str] = set()
    if actor_email:
        sent_to.add(actor_email)

    def _send_one(*, to: str, full_name: str, portal_url: str | None) -> None:
        addr = to.strip().lower()
        if not addr or addr in sent_to:
            return
        sent_to.add(addr)
        details = _meeting_calendar_details(
            organizer_name=organizer_name,
            child_name=child_name,
            case_code=case_code,
            meeting_url=meeting.meeting_url,
            portal_url=portal_url,
        )
        google_calendar_url = build_google_calendar_add_url(
            title=title_text,
            scheduled_date=meeting.scheduled_date,
            scheduled_time=meeting.scheduled_time,
            duration_minutes=meeting.duration_minutes or 30,
            details=details,
            location=meeting.meeting_url or "",
            timezone=settings.meeting_invite_calendar_timezone,
        )
        cm_meeting_invite_email(
            to=addr,
            full_name=full_name,
            meeting_title=title_text,
            when=when,
            duration_minutes=meeting.duration_minutes or 30,
            organizer_name=organizer_name,
            meeting_url=meeting.meeting_url,
            portal_url=portal_url,
            google_calendar_url=google_calendar_url,
            calendar_details=details,
            child_name=child_name,
            case_code=case_code,
            is_update=is_update,
        )

    for uid in meeting_participant_user_ids(meeting):
        if uid == actor_user_id:
            continue
        if not invite_case_manager and uid == meeting.case_manager_user_id:
            continue
        user = db.get(User, uid)
        if not user or not (user.email or "").strip():
            continue
        _send_one(
            to=user.email,
            full_name=user.full_name or user.email,
            portal_url=_portal_url_for_user(user),
        )

    for guest in parse_guest_emails(meeting.guest_emails_json):
        _send_one(to=guest, full_name="there", portal_url=None)


def notify_meeting_invites_respecting_flags(
    db: Session,
    meeting: CaseManagerMeeting,
    *,
    actor_user_id: int,
    invite_case_manager: bool,
    is_update: bool = False,
) -> None:
    """In-app notifications and email invites for all stakeholders."""
    case = db.get(Case, meeting.case_id) if meeting.case_id else None
    child_name = case.child.full_name if case and case.child else None
    label = _meeting_type_label(meeting.meeting_type)
    title_text = meeting.title or label
    when = _format_meeting_when(meeting)
    body_parts = [f"{title_text}"]
    if child_name:
        body_parts.append(f"Case: {child_name}")
    if when:
        body_parts.append(f"When: {when}")
    if meeting.meeting_url:
        body_parts.append(f"Join: {meeting.meeting_url}")
    body = " · ".join(body_parts)

    for uid in meeting_participant_user_ids(meeting):
        if uid == actor_user_id:
            continue
        if not invite_case_manager and uid == meeting.case_manager_user_id:
            continue
        notification_service.create_notification(
            db,
            user_id=uid,
            title="CM meeting updated" if is_update else "CM meeting invitation",
            body=body,
            entity_type="cm_meeting",
            entity_id=meeting.id,
        )

    send_meeting_invite_emails(
        db,
        meeting,
        actor_user_id=actor_user_id,
        invite_case_manager=invite_case_manager,
        is_update=is_update,
    )
