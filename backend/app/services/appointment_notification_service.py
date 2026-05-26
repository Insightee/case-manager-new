from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.permissions import user_has_permission
from app.models.case import Case
from app.models.child import Child
from app.models.parent import ParentGuardian
from app.models.slot import TherapistSlot
from app.models.user import User
from app.services import email_service
from app.services import notification_service


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


def notify_parents_session_cancelled(
    db: Session,
    slot: TherapistSlot,
    *,
    cancelled_by_name: str,
    reason: str = "Session cancelled",
) -> int:
    if not slot.case_id:
        return 0
    case = db.scalars(
        select(Case).where(Case.id == slot.case_id).options(selectinload(Case.child))
    ).first()
    child = case.child.full_name if case and case.child else "your child"
    when = _slot_when(slot)
    body = (
        f"{reason}. {child}'s session on {when} with {cancelled_by_name} was cancelled. "
        "Open Book appointment to pick a new time."
    )
    count = 0
    portal = f"{settings.frontend_url}/parent/book"
    for parent in _parent_users_for_case(db, slot.case_id):
        notification_service.create_notification(
            db,
            user_id=parent.id,
            title="Session cancelled",
            body=body,
            entity_type="appointment",
            entity_id=slot.id,
        )
        email_service.booking_cancelled_email(
            to=parent.email,
            child_name=child,
            when=when,
            reason=reason,
            portal_url=portal,
        )
        count += 1
    return count


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
    case = db.get(Case, slot.case_id)
    child = case.child.full_name if case and case.child else "your child"
    when = _slot_when(slot)
    portal = f"{settings.frontend_url}/parent/book"
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
        email_service.booking_confirmed_email(
            to=parent.email,
            child_name=child,
            therapist_name=therapist_name,
            when=when,
            portal_url=portal,
        )
        count += 1
    return count


def notify_recurring_assigned(
    db: Session,
    case: Case,
    therapist: User | None,
    record,
) -> int:
    child = case.child.full_name if case.child else case.case_code
    therapist_name = therapist.full_name if therapist else "your therapist"
    weekdays = ", ".join(record.get_weekdays())
    when = f"{record.start_time.strftime('%H:%M')}–{record.end_time.strftime('%H:%M')}"
    range_str = f"{record.start_date.isoformat()} to {record.end_date.isoformat()}"
    body = (
        f"Recurring sessions for {child} with {therapist_name} were scheduled: "
        f"{weekdays} at {when}, {range_str} ({record.booked_slot_count} sessions)."
    )
    count = 0
    portal = f"{settings.frontend_url}/parent/book"
    for parent in _parent_users_for_case(db, case.id):
        notification_service.create_notification(
            db,
            user_id=parent.id,
            title="Recurring sessions scheduled",
            body=body,
            entity_type="recurring_schedule",
            entity_id=record.id,
        )
        email_service.send_email(
            to=parent.email,
            subject=f"Recurring sessions — {child}",
            body_text=body + f"\n{portal}\n",
        )
        count += 1
    if therapist:
        notification_service.create_notification(
            db,
            user_id=therapist.id,
            title="Recurring schedule assigned",
            body=body,
            entity_type="recurring_schedule",
            entity_id=record.id,
        )
        email_service.send_email(
            to=therapist.email,
            subject="Recurring schedule assigned",
            body_text=body + f"\n{settings.frontend_url}/therapist/slots\n",
        )
        count += 1
    return count


def notify_parents_session_rescheduled(
    db: Session,
    old_slot: TherapistSlot,
    new_slot: TherapistSlot,
) -> int:
    if not old_slot.case_id:
        return 0
    case = db.get(Case, old_slot.case_id)
    child = case.child.full_name if case and case.child else "your child"
    old_when = _slot_when(old_slot)
    new_when = _slot_when(new_slot)
    body = f"{child}'s session was moved from {old_when} to {new_when}."
    count = 0
    portal = f"{settings.frontend_url}/parent/book"
    for parent in _parent_users_for_case(db, old_slot.case_id):
        notification_service.create_notification(
            db,
            user_id=parent.id,
            title="Session rescheduled",
            body=body,
            entity_type="appointment",
            entity_id=new_slot.id,
        )
        email_service.booking_rescheduled_email(
            to=parent.email,
            child_name=child,
            old_when=old_when,
            new_when=new_when,
            portal_url=portal,
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
        "Confirm or decline in Open Slots."
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
) -> int:
    if not old_slot.case_id:
        return 0
    case = db.get(Case, old_slot.case_id)
    child = case.child.full_name if case and case.child else "your child"
    body = (
        f"Your reschedule request for {child} from {_slot_when(old_slot)} to {_slot_when(new_slot)} "
        "is waiting for your therapist to confirm."
    )
    count = 0
    for parent in _parent_users_for_case(db, old_slot.case_id):
        notification_service.create_notification(
            db,
            user_id=parent.id,
            title="Reschedule pending",
            body=body,
            entity_type="appointment",
            entity_id=new_slot.id,
        )
        email_service.send_email(to=parent.email, subject="Reschedule pending", body_text=body)
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
        u = db.get(User, uid)
        if u:
            email_service.send_email(to=u.email, subject="Reschedule declined", body_text=body)
