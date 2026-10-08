from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.permissions import user_has_permission
from app.core.timezone import today_ist
from app.models.case import Case
from app.models.child import Child
from app.models.parent import ParentGuardian
from app.models.slot import TherapistSlot
from app.models.user import User
from app.services import email_service
from app.services import notification_service
from app.services.email.parent_mail import send_parent_email


def _is_same_day_ist(*dates: date | None) -> bool:
    today = today_ist()
    return any(d == today for d in dates if d is not None)


def _parents_for_case(db: Session, case_id: int) -> list[int]:
    case = db.get(Case, case_id)
    if not case:
        return []
    parents = db.scalars(
        select(ParentGuardian)
        .join(ParentGuardian.children)
        .where(Child.id == case.child_id)
    ).all()
    return list({pg.user_id for pg in parents})


def _parent_users_for_case(db: Session, case_id: int) -> list[User]:
    ids = _parents_for_case(db, case_id)
    return [u for uid in ids if (u := db.get(User, uid))]


def _admin_recipient_user_ids(db: Session) -> list[int]:
    out: list[int] = []
    users = db.scalars(select(User).options(selectinload(User.roles))).all()
    for u in users:
        if user_has_permission(u, "user.manage"):
            out.append(u.id)
    return list(dict.fromkeys(out))


def _slot_when(slot: TherapistSlot) -> str:
    return f"{slot.slot_date.isoformat()} {slot.start_time.strftime('%H:%M')}"


def notify_parents_in_progress_session_cancelled(
    db: Session,
    session,
    *,
    therapist_name: str,
    background_tasks=None,
) -> int:
    """Therapist reverted an accidental in-progress start — notify parents."""
    case_id = session.case_id
    if not case_id:
        return 0
    case = db.scalars(
        select(Case).where(Case.id == case_id).options(selectinload(Case.child))
    ).first()
    child = case.child.full_name if case and case.child else "your child"
    when = session.scheduled_date.isoformat()
    if session.start_time:
        when = f"{when} {session.start_time.strftime('%H:%M')}"
    body = (
        f"{child}'s visit on {when} was cancelled before a session log was started. "
        "The session remains scheduled unless you hear otherwise."
    )
    portal = f"{settings.frontend_url.rstrip('/')}/parent/book"
    same_day = _is_same_day_ist(session.scheduled_date)
    count = 0
    for parent in _parent_users_for_case(db, case_id):
        notification_service.create_notification(
            db,
            user_id=parent.id,
            title="Session visit cancelled",
            body=body,
            entity_type="session",
            entity_id=session.id,
        )
        if same_day:
            send_parent_email(
                db,
                parent,
                category="appointments",
                template_key="session_cancelled_today",
                payload={
                    "parent_name": parent.full_name or parent.email,
                    "child_name": child,
                    "when": when,
                    "reason": "Your therapist cancelled today's visit before logging the session.",
                    "portal_url": portal,
                },
                entity_type="session",
                entity_id=session.id,
                background_tasks=background_tasks,
            )
        count += 1
    return count


def notify_parents_session_cancelled(
    db: Session,
    slot: TherapistSlot,
    *,
    case_id: int,
    cancelled_by_name: str,
    reason: str = "Session cancelled",
    email_allowed: bool = True,
    background_tasks=None,
) -> int:
    if not case_id:
        return 0
    case = db.scalars(
        select(Case).where(Case.id == case_id).options(selectinload(Case.child))
    ).first()
    child = case.child.full_name if case and case.child else "your child"
    when = _slot_when(slot)
    body = (
        f"{reason}. {child}'s session on {when} with {cancelled_by_name} was cancelled. "
        "Open Book appointment to pick a new time."
    )
    count = 0
    portal = f"{settings.frontend_url.rstrip('/')}/parent/book"
    same_day = email_allowed and _is_same_day_ist(slot.slot_date)
    for parent in _parent_users_for_case(db, case_id):
        notification_service.create_notification(
            db,
            user_id=parent.id,
            title="Session cancelled",
            body=body,
            entity_type="appointment",
            entity_id=slot.id,
        )
        if same_day:
            send_parent_email(
                db,
                parent,
                category="appointments",
                template_key="session_cancelled_today",
                payload={
                    "parent_name": parent.full_name or parent.email,
                    "child_name": child,
                    "when": when,
                    "reason": reason,
                    "portal_url": portal,
                },
                entity_type="therapist_slot",
                entity_id=slot.id,
                background_tasks=background_tasks,
            )
        count += 1
    return count


def notify_therapist_parent_meeting_requested(
    db: Session,
    request_row,
    *,
    parent_name: str,
) -> None:
    from app.models.parent_meeting_request import ParentMeetingRequest

    if not isinstance(request_row, ParentMeetingRequest):
        return
    case = db.get(Case, request_row.case_id) if request_row.case_id else None
    child = case.child.full_name if case and case.child else "their child"
    when = request_row.requested_date.strftime("%d %b %Y")
    notification_service.create_notification(
        db,
        user_id=request_row.therapist_user_id,
        title="Meeting requested",
        body=f"{parent_name} asked to meet about {child} on {when}. Open scheduling to add a slot.",
        entity_type="parent_meeting_request",
        entity_id=request_row.id,
        dedupe_key=f"parent_meeting_request:{request_row.id}:PENDING",
    )
    therapist = db.get(User, request_row.therapist_user_id)
    if therapist:
        email_service.send_email(
            to=therapist.email,
            subject=f"Meeting request — {child}",
            body_text=(
                f"{parent_name} requested a session on {when}.\n"
                f"{settings.frontend_url}/therapist/slots?date={request_row.requested_date.isoformat()}\n"
            ),
        )


def notify_therapist_parent_booked(
    db: Session,
    slot: TherapistSlot,
    *,
    parent_name: str,
) -> None:
    case = db.get(Case, slot.case_id) if slot.case_id else None
    child = case.child.full_name if case and case.child else "a client"
    when = _slot_when(slot)
    notification_service.create_notification(
        db,
        user_id=slot.therapist_user_id,
        title="New appointment booked",
        body=f"{parent_name} booked {child} for {when}.",
        entity_type="appointment",
        entity_id=slot.id,
    )
    therapist = db.get(User, slot.therapist_user_id)
    if therapist:
        email_service.send_email(
            to=therapist.email,
            subject=f"New booking — {child}",
            body_text=f"{parent_name} booked {child} for {when}.\n{settings.frontend_url}/therapist/slots\n",
        )


def notify_parents_therapist_booked(
    db: Session,
    slot: TherapistSlot,
    *,
    therapist_name: str,
) -> int:
    if not slot.case_id:
        return 0
    if getattr(slot, "approval_status", "CONFIRMED") == "PENDING_THERAPIST":
        return 0
    case = db.get(Case, slot.case_id)
    child = case.child.full_name if case and case.child else "your child"
    when = _slot_when(slot)
    count = 0
    for parent in _parent_users_for_case(db, slot.case_id):
        notification_service.create_notification(
            db,
            user_id=parent.id,
            title="Session booked",
            body=f"{therapist_name} scheduled {child} for {when}.",
            entity_type="appointment",
            entity_id=slot.id,
        )
        count += 1
    return count


_SKIP_REASON = {
    "leave": "therapist leave",
    "already_booked": "already booked for this case",
    "other_case": "that time is booked for another case",
    "unavailable": "that time is not open",
}


def _recurring_summary_body(case: Case, therapist: User | None, record, skipped: list | None) -> str:
    child = case.child.full_name if case.child else case.case_code
    therapist_name = therapist.full_name if therapist else "your therapist"
    weekdays = ", ".join(record.get_weekdays())
    when = f"{record.start_time.strftime('%H:%M')}–{record.end_time.strftime('%H:%M')}"
    range_str = f"{record.start_date.isoformat()} to {record.end_date.isoformat()}"
    body = (
        f"Recurring sessions for {child} with {therapist_name} were scheduled: "
        f"{weekdays} at {when}, {range_str} ({record.booked_slot_count} sessions)."
    )
    # Dates already booked for this case are not "left off" (e.g. the anchor session booked just before).
    skipped = [row for row in (skipped or []) if row.get("reason") != "already_booked"]
    if skipped:
        bits = []
        for row in skipped[:8]:
            reason = _SKIP_REASON.get(row.get("reason"), row.get("reason") or "not booked")
            bits.append(f"{row.get('date')} ({reason})")
        extra = f" Left off: {'; '.join(bits)}."
        if len(skipped) > 8:
            extra += f" {len(skipped) - 8} more dates were left off."
        body += extra
    return body


def notify_recurring_assigned(
    db: Session,
    case: Case,
    therapist: User | None,
    record,
    *,
    skipped: list | None = None,
) -> int:
    """One summary per recipient for a recurring booking. Not one notice per session.

    Parents, the therapist, and the case manager each get a single in-app notice.
    A repeat of the same recurrence group does not add another copy.
    One-off books, cancellations, and reschedules stay per session.
    """
    body = _recurring_summary_body(case, therapist, record, skipped)
    dedupe_key = f"recurring_schedule:{record.recurrence_group_id}"
    count = 0
    portal = f"{settings.frontend_url}/parent/book"
    parent_ids = {parent.id for parent in _parent_users_for_case(db, case.id)}
    for parent in _parent_users_for_case(db, case.id):
        created = notification_service.create_notification(
            db,
            user_id=parent.id,
            title="Recurring sessions scheduled",
            body=body,
            entity_type="recurring_schedule",
            entity_id=record.id,
            dedupe_key=dedupe_key,
        )
        if created is None:
            continue
        count += 1
    if therapist and therapist.id not in parent_ids:
        created = notification_service.create_notification(
            db,
            user_id=therapist.id,
            title="Recurring schedule assigned",
            body=body,
            entity_type="recurring_schedule",
            entity_id=record.id,
            dedupe_key=dedupe_key,
        )
        if created is not None:
            email_service.send_email(
                to=therapist.email,
                subject="Recurring schedule assigned",
                body_text=body + f"\n{settings.frontend_url}/therapist/slots\n",
            )
            count += 1
    manager_id = getattr(case, "case_manager_user_id", None)
    if manager_id and manager_id not in parent_ids and (not therapist or manager_id != therapist.id):
        created = notification_service.create_notification(
            db,
            user_id=manager_id,
            title="Recurring schedule booked",
            body=body,
            entity_type="recurring_schedule",
            entity_id=record.id,
            dedupe_key=dedupe_key,
        )
        if created is not None:
            count += 1
    return count


def notify_parents_session_rescheduled(
    db: Session,
    old_slot: TherapistSlot,
    new_slot: TherapistSlot,
    *,
    case_id: int,
    email_allowed: bool = True,
    background_tasks=None,
) -> int:
    if not case_id:
        return 0
    case = db.get(Case, case_id)
    child = case.child.full_name if case and case.child else "your child"
    old_when = _slot_when(old_slot)
    new_when = _slot_when(new_slot)
    body = f"{child}'s session was moved from {old_when} to {new_when}."
    count = 0
    portal = f"{settings.frontend_url.rstrip('/')}/parent/book"
    same_day = email_allowed and _is_same_day_ist(old_slot.slot_date, new_slot.slot_date)
    for parent in _parent_users_for_case(db, case_id):
        notification_service.create_notification(
            db,
            user_id=parent.id,
            title="Session rescheduled",
            body=body,
            entity_type="appointment",
            entity_id=new_slot.id,
        )
        if same_day:
            send_parent_email(
                db,
                parent,
                category="appointments",
                template_key="session_rescheduled_today",
                payload={
                    "parent_name": parent.full_name or parent.email,
                    "child_name": child,
                    "old_when": old_when,
                    "new_when": new_when,
                    "portal_url": portal,
                },
                entity_type="therapist_slot",
                entity_id=new_slot.id,
                background_tasks=background_tasks,
            )
        count += 1
    return count


def notify_therapist_admin_booking_pending(
    db: Session,
    slot: TherapistSlot,
    *,
    admin_name: str,
    comment: str | None = None,
) -> None:
    case = db.get(Case, slot.case_id) if slot.case_id else None
    child = case.child.full_name if case and case.child else "a client"
    extra = f"\nNote from admin: {comment}" if comment else ""
    body = (
        f"{admin_name} booked {child} for {_slot_when(slot)} and needs your confirmation."
        f"{extra}"
    )
    notification_service.create_notification(
        db,
        user_id=slot.therapist_user_id,
        title="Session booking needs your confirmation",
        body=body,
        entity_type="appointment",
        entity_id=slot.id,
    )
    therapist = db.get(User, slot.therapist_user_id)
    if therapist:
        email_service.send_email(
            to=therapist.email,
            subject="Admin booked a session — please confirm",
            body_text=body + f"\n{settings.frontend_url}/therapist/slots\n",
        )


def notify_therapist_reschedule_pending(
    db: Session,
    *,
    old_slot: TherapistSlot,
    new_slot: TherapistSlot,
    parent_name: str,
) -> None:
    case = db.get(Case, new_slot.case_id) if new_slot.case_id else None
    child = case.child.full_name if case and case.child else "a client"
    body = (
        f"{parent_name} requested to move {child} from {_slot_when(old_slot)} to {_slot_when(new_slot)}. "
        "Confirm or decline in Scheduling."
    )
    notification_service.create_notification(
        db,
        user_id=new_slot.therapist_user_id,
        title="Reschedule needs your confirmation",
        body=body,
        entity_type="appointment",
        entity_id=new_slot.id,
    )
    therapist = db.get(User, new_slot.therapist_user_id)
    if therapist:
        email_service.send_email(
            to=therapist.email,
            subject="Reschedule pending your confirmation",
            body_text=body + f"\n{settings.frontend_url}/therapist/slots\n",
        )


def notify_parents_reschedule_pending(
    db: Session,
    *,
    old_slot: TherapistSlot,
    new_slot: TherapistSlot,
    case_id: int,
) -> int:
    if not case_id:
        return 0
    case = db.get(Case, case_id)
    child = case.child.full_name if case and case.child else "your child"
    body = (
        f"Your reschedule request for {child} from {_slot_when(old_slot)} to {_slot_when(new_slot)} "
        "is waiting for your therapist to confirm."
    )
    count = 0
    for parent in _parent_users_for_case(db, case_id):
        notification_service.create_notification(
            db,
            user_id=parent.id,
            title="Reschedule pending",
            body=body,
            entity_type="appointment",
            entity_id=new_slot.id,
        )
        count += 1
    return count


def notify_admins_walk_in_invite(
    db: Session,
    *,
    therapist_name: str,
    client_name: str,
    client_email: str,
    slot_when: str,
) -> int:
    title = "Walk-in client invite sent"
    body = (
        f"{therapist_name} invited {client_name} ({client_email}) to the portal for {slot_when}. "
        "Review onboarding and finalize the case when they register."
    )
    count = 0
    for uid in _admin_recipient_user_ids(db):
        notification_service.create_notification(
            db, user_id=uid, title=title, body=body, entity_type="invite", entity_id=None
        )
        count += 1
    for admin_email in settings.admin_notification_email_list:
        email_service.send_email(to=admin_email, subject=title, body_text=body)
    return count


def notify_parent_invite_accepted_admin(
    db: Session,
    *,
    user_email: str,
    full_name: str,
) -> None:
    title = "Client accepted portal invite"
    body = f"{full_name} ({user_email}) completed registration from a therapist invite."
    for uid in _admin_recipient_user_ids(db):
        notification_service.create_notification(
            db, user_id=uid, title=title, body=body, entity_type="user", entity_id=None
        )
    for admin_email in settings.admin_notification_email_list:
        email_service.send_email(to=admin_email, subject=title, body_text=body)


def notify_parents_reschedule_declined(
    db: Session,
    *,
    old_slot: TherapistSlot,
    parent_user_ids: list[int],
) -> None:
    when = _slot_when(old_slot)
    body = f"Your therapist declined the proposed reschedule. Your session remains at {when}."
    for uid in parent_user_ids:
        notification_service.create_notification(
            db, user_id=uid, title="Reschedule declined", body=body, entity_type="appointment", entity_id=old_slot.id
        )
        _ = db.get(User, uid)
