from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.child import Child
from app.models.leave import TherapistLeave
from app.models.parent import ParentGuardian
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.slot import SlotStatus, TherapistSlot
from app.models.therapist_profile import TherapistProfile
from app.models.user import User
from app.services import appointment_booking_service as appt_booking
from app.services import email_service
from app.services import leave_migration_service as leave_migration
from app.services import leave_service
from app.services import notification_service
from app.services.parent_notification_preferences import parent_wants_log_leave_emails
from app.services.assignment_service import resolve_primary_case_manager_user_id


def _format_date_range(start: date, end: date) -> str:
    if start == end:
        return start.isoformat()
    return f"{start.isoformat()} to {end.isoformat()}"


def _parents_for_case(db: Session, case_id: int) -> list[int]:
    case = db.scalars(select(Case).where(Case.id == case_id)).first()
    if not case:
        return []
    parents = db.scalars(
        select(ParentGuardian)
        .join(ParentGuardian.children)
        .where(Child.id == case.child_id)
    ).all()
    return list({pg.user_id for pg in parents})


def _cases_for_therapist_active(db: Session, therapist_user_id: int) -> list[Case]:
    assignments = db.scalars(
        select(CaseAssignment)
        .where(
            CaseAssignment.therapist_user_id == therapist_user_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
        .options(selectinload(CaseAssignment.case).selectinload(Case.child))
    ).all()
    return [a.case for a in assignments if a.case]


def _cases_for_leave_scope(db: Session, leave: TherapistLeave) -> list[Case]:
    scope = leave_service._leave_scope_ids(leave)
    if scope is None:
        return _cases_for_therapist_active(db, leave.therapist_user_id)
    if not scope:
        return []
    return list(
        db.scalars(
            select(Case).where(Case.id.in_(scope)).options(selectinload(Case.child))
        ).all()
    )


def _parents_for_leave_scope(db: Session, leave: TherapistLeave) -> dict[int, list[Case]]:
    by_parent: dict[int, list[Case]] = defaultdict(list)
    for case in _cases_for_leave_scope(db, leave):
        for parent_user_id in _parents_for_case(db, case.id):
            by_parent[parent_user_id].append(case)
    return by_parent


def _slot_in_leave_scope(slot: TherapistSlot, scope: set[int] | None) -> bool:
    if scope is None:
        return True
    if slot.case_id is None:
        return False
    return int(slot.case_id) in scope


def _leave_staff_recipient_ids(db: Session, leave: TherapistLeave) -> set[int]:
    """Primary CM, therapist mentor, and case managers for affected cases."""
    ids: set[int] = set()
    primary_cm = resolve_primary_case_manager_user_id(db, leave.therapist_user_id)
    if primary_cm:
        ids.add(primary_cm)
    profile = db.scalars(
        select(TherapistProfile).where(TherapistProfile.user_id == leave.therapist_user_id)
    ).first()
    if profile and profile.mentor_user_id:
        ids.add(profile.mentor_user_id)
    for case in _cases_for_leave_scope(db, leave):
        if case.case_manager_user_id:
            ids.add(case.case_manager_user_id)
    ids.discard(leave.therapist_user_id)
    return ids


def _parent_pending_leave_body(therapist: User, date_range: str, cases: list[Case]) -> str:
    case_codes = ", ".join(c.case_code for c in cases[:3])
    if len(cases) > 3:
        case_codes += f" (+{len(cases) - 3} more)"
    child_names = ", ".join({c.child.full_name for c in cases if c.child})
    return (
        f"{therapist.full_name} has applied for leave from {date_range}. "
        "The request is under review — no sessions have been cancelled yet."
        + (f" This affects case(s) {case_codes}" if case_codes else "")
        + (f" for {child_names}." if child_names else ".")
    )


def unblock_slots_for_leave(db: Session, leave_id: int) -> int:
    slots = db.scalars(
        select(TherapistSlot).where(
            TherapistSlot.leave_block_leave_id == leave_id,
            TherapistSlot.status == SlotStatus.BLOCKED,
        )
    ).all()
    n = 0
    for s in slots:
        s.status = SlotStatus.AVAILABLE
        s.leave_block_leave_id = None
        if s.notes and "[blocked: leave" in s.notes:
            s.notes = None
        n += 1
    db.flush()
    return n


def notify_leave_submitted(db: Session, leave: TherapistLeave, therapist: User) -> int:
    date_range = _format_date_range(leave.start_date, leave.end_date)
    count = 0
    retro = leave_migration.is_retroactive_leave(leave.start_date, leave.end_date)
    migration_reentry = leave_migration.is_migration_reentry(leave.start_date, leave.end_date)

    therapist_body = f"Your leave for {date_range} is pending approval."
    if migration_reentry:
        therapist_body += " This records leave you already took — sessions will not be changed."
    notification_service.create_notification(
        db,
        user_id=therapist.id,
        title="Leave request submitted",
        body=therapist_body,
        entity_type="leave",
        entity_id=leave.id,
    )
    count += 1

    for staff_user_id in _leave_staff_recipient_ids(db, leave):
        body = (
            f"{therapist.full_name} requested {leave.leave_type.value} leave for {date_range}. "
            "Review and approve or reject in Leave Management."
        )
        if retro:
            body += (
                " Previous leave — approving records it for balance tracking only; "
                "booked sessions will not be cancelled."
            )
        notification_service.create_notification(
            db,
            user_id=staff_user_id,
            title="Leave request pending approval",
            body=body,
            entity_type="leave",
            entity_id=leave.id,
        )
        count += 1

    if retro:
        return count

    for parent_user_id, cases in _parents_for_leave_scope(db, leave).items():
        body = _parent_pending_leave_body(therapist, date_range, cases)
        notification_service.create_notification(
            db,
            user_id=parent_user_id,
            title="Therapist leave requested",
            body=body,
            entity_type="leave",
            entity_id=leave.id,
        )
        u = db.get(User, parent_user_id)
        if u and parent_wants_log_leave_emails(u):
            email_service.leave_pending_parent_email(
                to=u.email,
                therapist_name=therapist.full_name,
                date_range=date_range,
                body_text=body,
                portal_url=f"{settings.frontend_url}/parent/book",
                parent_name=u.full_name or u.email,
                db=db,
            )
        count += 1
    return count


def notify_leave_approved(db: Session, leave: TherapistLeave, therapist: User) -> int:
    date_range = _format_date_range(leave.start_date, leave.end_date)
    retro = leave_migration.is_retroactive_leave(leave.start_date, leave.end_date)

    if retro:
        notification_service.create_notification(
            db,
            user_id=therapist.id,
            title="Leave approved",
            body=(
                f"Your leave for {date_range} is approved. "
                "This was recorded as previous leave — sessions were not changed."
            ),
            entity_type="leave",
            entity_id=leave.id,
        )
        email_service.leave_approved_therapist_email(
            to=therapist.email,
            therapist_name=therapist.full_name,
            date_range=date_range,
            cancelled_count=0,
            portal_url=f"{settings.frontend_url}/therapist/leave",
            db=db,
        )
        return 1

    scope = leave_service._leave_scope_ids(leave)

    booked_slots = db.scalars(
        select(TherapistSlot)
        .where(
            TherapistSlot.therapist_user_id == leave.therapist_user_id,
            TherapistSlot.slot_date >= leave.start_date,
            TherapistSlot.slot_date <= leave.end_date,
            TherapistSlot.status == SlotStatus.BOOKED,
        )
        .options(selectinload(TherapistSlot.case).selectinload(Case.child))
    ).all()

    cancelled_by_parent: dict[int, list[str]] = defaultdict(list)
    for slot in booked_slots:
        if not slot.case_id or not _slot_in_leave_scope(slot, scope):
            continue
        try:
            appt_booking.cancel_booking_with_session(db, slot.id)
        except ValueError:
            continue
        line = (
            f"{slot.case.case_code}: {slot.slot_date.isoformat()} "
            f"{slot.start_time.strftime('%H:%M')}–{slot.end_time.strftime('%H:%M')}"
        )
        if slot.case.child:
            line = f"{slot.case.child.full_name} — {line}"
        for parent_user_id in _parents_for_case(db, slot.case_id):
            cancelled_by_parent[parent_user_id].append(line)

    avail_slots = db.scalars(
        select(TherapistSlot).where(
            TherapistSlot.therapist_user_id == leave.therapist_user_id,
            TherapistSlot.slot_date >= leave.start_date,
            TherapistSlot.slot_date <= leave.end_date,
            TherapistSlot.status == SlotStatus.AVAILABLE,
        )
    ).all()
    for s in avail_slots:
        if not _slot_in_leave_scope(s, scope):
            continue
        s.status = SlotStatus.BLOCKED
        s.leave_block_leave_id = leave.id
        s.notes = f"[blocked: leave {leave.id}]"
    db.flush()

    notified_parents: set[int] = set()
    count = 0

    for parent_user_id, lines in cancelled_by_parent.items():
        if lines:
            body = (
                f"Leave for {therapist.full_name} on {date_range} is confirmed. "
                f"The following session(s) were cancelled:\n"
                + "\n".join(f"• {ln}" for ln in lines)
            )
        else:
            body = f"Leave for {therapist.full_name} on {date_range} is confirmed."
        notification_service.create_notification(
            db,
            user_id=parent_user_id,
            title="Sessions cancelled — therapist on leave",
            body=body,
            entity_type="leave",
            entity_id=leave.id,
        )
        notified_parents.add(parent_user_id)
        count += 1

    for parent_user_id, cases in _parents_for_leave_scope(db, leave).items():
        if parent_user_id in notified_parents:
            continue
        case_codes = ", ".join(c.case_code for c in cases)
        body = (
            f"Leave for {therapist.full_name} on {date_range} is confirmed. "
            f"No booked sessions were cancelled for your case(s) ({case_codes}), "
            f"but the therapist will be unavailable on those dates."
        )
        notification_service.create_notification(
            db,
            user_id=parent_user_id,
            title="Therapist on leave",
            body=body,
            entity_type="leave",
            entity_id=leave.id,
        )
        count += 1

    cancel_n = sum(len(v) for v in cancelled_by_parent.values())
    notification_service.create_notification(
        db,
        user_id=therapist.id,
        title="Leave approved",
        body=(
            f"Your leave for {date_range} is approved. "
            f"{cancel_n} booked session(s) were cancelled and clients were notified."
        ),
        entity_type="leave",
        entity_id=leave.id,
    )
    count += 1
    email_service.leave_approved_therapist_email(
        to=therapist.email,
        therapist_name=therapist.full_name,
        date_range=date_range,
        cancelled_count=cancel_n,
        portal_url=f"{settings.frontend_url}/therapist/leave",
        db=db,
    )

    return count


def notify_leave_rejected(db: Session, leave: TherapistLeave, therapist: User) -> int:
    unblock_slots_for_leave(db, leave.id)
    date_range = _format_date_range(leave.start_date, leave.end_date)
    count = 0
    therapist_portal = f"{settings.frontend_url}/therapist/leave"

    reject_body = f"Your leave request for {date_range} was not approved."
    if leave.review_note:
        reject_body += f" Note: {leave.review_note}"
    notification_service.create_notification(
        db,
        user_id=therapist.id,
        title="Leave request not approved",
        body=reject_body,
        entity_type="leave",
        entity_id=leave.id,
    )
    email_service.leave_rejected_therapist_email(
        to=therapist.email,
        therapist_name=therapist.full_name,
        date_range=date_range,
        review_note=leave.review_note,
        portal_url=therapist_portal,
        db=db,
    )
    count += 1
    for parent_user_id, cases in _parents_for_leave_scope(db, leave).items():
        case_codes = ", ".join(c.case_code for c in cases)
        body = (
            f"The leave request for {therapist.full_name} ({date_range}) was not approved. "
            f"Your scheduled sessions for case(s) {case_codes} remain as planned."
        )
        notification_service.create_notification(
            db,
            user_id=parent_user_id,
            title="Leave request not approved",
            body=body,
            entity_type="leave",
            entity_id=leave.id,
        )
        count += 1
    return count


def notify_leave_withdrawn(db: Session, leave: TherapistLeave, therapist: User) -> int:
    """Therapist withdrew a pending leave — parents get in-app only."""
    date_range = _format_date_range(leave.start_date, leave.end_date)
    count = 0
    notification_service.create_notification(
        db,
        user_id=therapist.id,
        title="Leave request withdrawn",
        body=f"Your leave request for {date_range} was withdrawn.",
        entity_type="leave",
        entity_id=leave.id,
    )
    count += 1
    for parent_user_id, cases in _parents_for_leave_scope(db, leave).items():
        case_codes = ", ".join(c.case_code for c in cases)
        body = (
            f"{therapist.full_name} withdrew their leave request for {date_range}. "
            f"Your scheduled sessions for case(s) {case_codes} remain as planned."
        )
        notification_service.create_notification(
            db,
            user_id=parent_user_id,
            title="Leave request withdrawn",
            body=body,
            entity_type="leave",
            entity_id=leave.id,
        )
        count += 1
    return count


def notify_leave_cancelled_after_approval(db: Session, leave: TherapistLeave, therapist: User) -> int:
    """Approved leave was cancelled — parents receive email about session reinstatement."""
    date_range = _format_date_range(leave.start_date, leave.end_date)
    count = 0
    portal = f"{settings.frontend_url}/parent/book"
    scope = leave_service._leave_scope_ids(leave)
    scope_case_ids = None if scope is None else scope

    cancelled_sessions = db.scalars(
        select(TherapySession)
        .where(
            TherapySession.therapist_user_id == leave.therapist_user_id,
            TherapySession.scheduled_date >= leave.start_date,
            TherapySession.scheduled_date <= leave.end_date,
            TherapySession.status == SessionStatus.CANCELLED,
        )
        .options(selectinload(TherapySession.case).selectinload(Case.child))
    ).all()

    reinstated_by_parent: dict[int, list[str]] = defaultdict(list)
    for session in cancelled_sessions:
        if scope_case_ids is not None and session.case_id not in scope_case_ids:
            continue
        line = session.scheduled_date.isoformat()
        if session.start_time and session.end_time:
            line += (
                f" {session.start_time.strftime('%H:%M')}–{session.end_time.strftime('%H:%M')}"
            )
        if session.case and session.case.child:
            line = f"{session.case.child.full_name} — {line}"
        for parent_user_id in _parents_for_case(db, session.case_id):
            reinstated_by_parent[parent_user_id].append(line)

    notification_service.create_notification(
        db,
        user_id=therapist.id,
        title="Leave cancelled",
        body=f"Your approved leave for {date_range} was cancelled.",
        entity_type="leave",
        entity_id=leave.id,
    )
    count += 1

    for parent_user_id, cases in _parents_for_leave_scope(db, leave).items():
        lines = reinstated_by_parent.get(parent_user_id, [])
        case_codes = ", ".join(c.case_code for c in cases)
        u = db.get(User, parent_user_id)
        if u and parent_wants_log_leave_emails(u):
            email_service.leave_cancelled_after_approval_email(
                to=u.email,
                therapist_name=therapist.full_name,
                date_range=date_range,
                case_codes=case_codes,
                lines=lines,
                portal_url=portal,
                parent_name=u.full_name or u.email,
                db=db,
            )
        count += 1
    return count
