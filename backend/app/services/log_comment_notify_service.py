from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.session import Session as TherapySession
from app.models.therapist_profile import TherapistProfile
from app.models.user import User
from app.services import case_service, log_service, notification_service
from app.services.session_log_service import parent_user_ids_for_case


def _staff_recipient_ids(
    db: Session,
    case: Case | None,
    session: TherapySession | None,
    *,
    exclude_user_id: int | None = None,
) -> set[int]:
    ids: set[int] = set()
    if session and session.therapist_user_id:
        ids.add(session.therapist_user_id)
    if case and case.case_manager_user_id:
        ids.add(case.case_manager_user_id)
    if session and session.therapist_user_id:
        profile = db.scalars(
            select(TherapistProfile).where(TherapistProfile.user_id == session.therapist_user_id)
        ).first()
        if profile and profile.mentor_user_id:
            ids.add(profile.mentor_user_id)
    if exclude_user_id is not None:
        ids.discard(exclude_user_id)
    return ids


def _resolve_context(
    db: Session,
    *,
    log_id: int,
    case_id: int,
) -> tuple[Case | None, TherapySession | None, date | None, str]:
    session: TherapySession | None
    if log_id > 0:
        log = log_service.get_log(db, log_id)
        if not log:
            case = case_service.get_case(db, case_id)
            return case, None, None, case.child.full_name if case and case.child else "client"
        session = log.session or db.get(TherapySession, log.session_id)
    else:
        session = db.get(TherapySession, -log_id)

    case = None
    if session:
        case = session.case or case_service.get_case(db, session.case_id)
    if not case:
        case = case_service.get_case(db, case_id)

    child_name = case.child.full_name if case and case.child else "client"
    session_date = session.scheduled_date if session else None
    return case, session, session_date, child_name


def _staff_reply_label(author_role: str, author: User) -> str:
    name = (author.full_name or "").strip()
    if name:
        return name
    if author_role == "therapist":
        return "Your therapist"
    if author_role == "case_manager":
        return "Your case manager"
    return "The care team"


def notify_staff_on_parent_log_comment(
    db: Session,
    *,
    comment_id: int,
    log_id: int,
    case_id: int,
    parent_user: User,
) -> int:
    """Bell notification for therapist, case manager, and mentor when a parent comments."""
    case, session, session_date, child_name = _resolve_context(db, log_id=log_id, case_id=case_id)
    if not case:
        return 0

    case_code = case.case_code or "case"
    date_label = session_date.isoformat() if session_date else "recent session"
    parent_name = parent_user.full_name or parent_user.email or "A parent"
    title = f"Family comment on session log — {case_code}"
    body = (
        f"{parent_name} left a comment on {child_name}'s session log ({date_label}). "
        "Open the log to read and reply."
    )
    count = 0
    for uid in _staff_recipient_ids(db, case, session, exclude_user_id=parent_user.id):
        n = notification_service.create_notification(
            db,
            user_id=uid,
            title=title,
            body=body,
            entity_type="daily_log",
            entity_id=log_id,
        )
        if n:
            count += 1
    return count


def notify_parents_on_staff_log_reply(
    db: Session,
    *,
    comment_id: int,
    log_id: int,
    case_id: int,
    staff_user: User,
    author_role: str,
    visibility: str,
) -> int:
    """Bell notification for parents when therapist or case manager replies on the family thread."""
    if visibility != "parent_team":
        return 0
    if author_role not in ("therapist", "case_manager", "admin"):
        return 0

    case, _session, session_date, child_name = _resolve_context(db, log_id=log_id, case_id=case_id)
    if not case:
        return 0

    date_label = session_date.isoformat() if session_date else "recent session"
    staff_label = _staff_reply_label(author_role, staff_user)
    title = f"Reply on {child_name}'s session log"
    body = (
        f"{staff_label} replied on the session log for {date_label}. "
        "Open session updates to read the message."
    )
    count = 0
    for uid in parent_user_ids_for_case(db, case):
        if uid == staff_user.id:
            continue
        n = notification_service.create_notification(
            db,
            user_id=uid,
            title=title,
            body=body,
            entity_type="daily_log",
            entity_id=log_id,
        )
        if n:
            count += 1
    return count
