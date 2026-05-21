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
from app.models.slot import SlotStatus, TherapistSlot
from app.models.user import User
from app.services import appointment_booking_service as appt_booking
from app.services import email_service
from app.services import leave_service
from app.services import notification_service


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


def _parents_for_therapist_cases(db: Session, therapist_user_id: int) -> dict[int, list[Case]]:
    by_parent: dict[int, list[Case]] = defaultdict(list)
    for case in _cases_for_therapist_active(db, therapist_user_id):
        for parent_user_id in _parents_for_case(db, case.id):
            by_parent[parent_user_id].append(case)
    return by_parent


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

    notification_service.create_notification(
        db,
        user_id=therapist.id,
        title="Leave request submitted",
        body=f"Your leave for {date_range} is pending approval.",
        entity_type="leave",
        entity_id=leave.id,
    )
    count += 1

    hr_portal = f"{settings.frontend_url}/hr/leave"
    for manager in leave_service.users_with_leave_manage(db, exclude_user_id=therapist.id):
        body = (
            f"{therapist.full_name} requested {leave.leave_type.value} leave for {date_range}. "
            "Review and approve or reject in Leave Management."
        )
        notification_service.create_notification(
            db,
            user_id=manager.id,
            title="Leave request pending approval",
            body=body,
            entity_type="leave",
            entity_id=leave.id,
        )
        email_service.leave_pending_hr_email(
            to=manager.email,
            therapist_name=therapist.full_name,
            date_range=date_range,
            leave_type=leave.leave_type.value,
            portal_url=hr_portal,
        )
        count += 1

    for parent_user_id, cases in _parents_for_therapist_cases(db, leave.therapist_user_id).items():
        case_codes = ", ".join(c.case_code for c in cases[:3])
        if len(cases) > 3:
            case_codes += f" (+{len(cases) - 3} more)"
        child_names = ", ".join({c.child.full_name for c in cases if c.child})
        body = (
            f"{therapist.full_name} has requested leave from {date_range}. "
            f"This affects case(s) {case_codes}"
            + (f" for {child_names}." if child_names else ".")
            + " Scheduled sessions are not cancelled until the leave is approved."
        )
        notification_service.create_notification(
            db,
            user_id=parent_user_id,
            title="Therapist leave requested",
            body=body,
            entity_type="leave",
            entity_id=leave.id,
        )
        u = db.get(User, parent_user_id)
        if u:
            email_service.send_email(to=u.email, subject="Therapist leave requested", body_text=body)
        count += 1
    return count


def notify_leave_approved(db: Session, leave: TherapistLeave, therapist: User) -> int:
    date_range = _format_date_range(leave.start_date, leave.end_date)
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
        if not slot.case_id:
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
        s.status = SlotStatus.BLOCKED
        s.leave_block_leave_id = leave.id
        s.notes = f"[blocked: leave {leave.id}]"
    db.flush()

    notified_parents: set[int] = set()
    count = 0
    portal = f"{settings.frontend_url}/parent/book"

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
        u = db.get(User, parent_user_id)
        if u:
            email_service.leave_sessions_cancelled_email(
                to=u.email,
                therapist_name=therapist.full_name,
                date_range=date_range,
                lines=lines,
                portal_url=portal,
            )
        notified_parents.add(parent_user_id)
        count += 1

    for parent_user_id, cases in _parents_for_therapist_cases(db, leave.therapist_user_id).items():
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
        u = db.get(User, parent_user_id)
        if u:
            email_service.send_email(to=u.email, subject="Therapist on leave", body_text=body)
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
    )
    for admin_email in settings.admin_notification_email_list:
        email_service.leave_admin_summary_email(
            to=admin_email,
            therapist_name=therapist.full_name,
            date_range=date_range,
            cancelled_count=cancel_n,
        )

    return count


def notify_leave_rejected(db: Session, leave: TherapistLeave, therapist: User) -> int:
    unblock_slots_for_leave(db, leave.id)
    date_range = _format_date_range(leave.start_date, leave.end_date)
    count = 0
    portal = f"{settings.frontend_url}/parent/book"
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
    )
    count += 1
    for parent_user_id, cases in _parents_for_therapist_cases(db, leave.therapist_user_id).items():
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
        u = db.get(User, parent_user_id)
        if u:
            email_service.leave_sessions_reinstated_email(
                to=u.email,
                therapist_name=therapist.full_name,
                date_range=date_range,
                portal_url=portal,
            )
        count += 1
    return count
