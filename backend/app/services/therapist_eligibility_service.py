"""Therapist assignment / login eligibility (Core OS Stabilisation PR2 / DEC-03)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import RoleName
from app.core.timezone import today_ist
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case, CaseStatus
from app.models.support_ticket import SupportTicket, TicketCategory, TicketMessage, TicketStatus, TicketTopic
from app.models.therapist_profile import TherapistProfile, TherapistProfileStatus
from app.models.user import EmploymentStatus, User

_INELIGIBLE_EMPLOYMENT = frozenset(
    {
        EmploymentStatus.SUSPENDED.value,
        EmploymentStatus.ARCHIVED.value,
    }
)
_INELIGIBLE_PROFILE = frozenset(
    {
        TherapistProfileStatus.PAUSED.value,
        TherapistProfileStatus.DELETED.value,
    }
)

RESTORE_TICKET_SUBJECT = "Therapist status restore request"


class TherapistIneligibleError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)

    def as_dict(self) -> dict:
        return {"code": self.code, "message": self.message}


def _emp_value(user: User) -> str:
    if user.employment_status is None:
        return EmploymentStatus.ACTIVE.value
    return (
        user.employment_status.value
        if hasattr(user.employment_status, "value")
        else str(user.employment_status)
    )


def _profile_status_value(profile: TherapistProfile | None) -> str | None:
    if profile is None or profile.status is None:
        return None
    return profile.status.value if hasattr(profile.status, "value") else str(profile.status)


def therapist_ineligibility_code(db: Session, therapist_user_id: int) -> str | None:
    """
    Return a block code if the therapist may not hold / start cases, else None.

    DEC-03: is_active=false, employment SUSPENDED/ARCHIVED, profile PAUSED/DELETED.
    """
    user = db.get(User, therapist_user_id)
    if user is None:
        return "THERAPIST_NOT_FOUND"
    if not user.is_active:
        return "THERAPIST_INACTIVE"
    emp = _emp_value(user)
    if emp in _INELIGIBLE_EMPLOYMENT:
        return f"THERAPIST_EMPLOYMENT_{emp}"
    profile = db.scalars(
        select(TherapistProfile).where(TherapistProfile.user_id == therapist_user_id)
    ).first()
    status = _profile_status_value(profile)
    if status in _INELIGIBLE_PROFILE:
        return f"THERAPIST_PROFILE_{status}"
    return None


def therapist_may_hold_case(db: Session, therapist_user_id: int, *, case_id: int | None = None) -> bool:
    del case_id  # reserved for future case-specific rules
    return therapist_ineligibility_code(db, therapist_user_id) is None


def assert_therapist_may_hold_case(
    db: Session,
    *,
    therapist_user_id: int,
    case_id: int | None = None,
) -> None:
    code = therapist_ineligibility_code(db, therapist_user_id)
    if code is None:
        return
    messages = {
        "THERAPIST_NOT_FOUND": "Therapist account was not found.",
        "THERAPIST_INACTIVE": (
            "This therapist account is not active — they cannot be assigned or start sessions."
        ),
        "THERAPIST_EMPLOYMENT_SUSPENDED": (
            "This therapist's employment is suspended — they cannot hold cases until restored."
        ),
        "THERAPIST_EMPLOYMENT_ARCHIVED": (
            "This therapist's employment is archived — they cannot hold cases until restored."
        ),
        "THERAPIST_PROFILE_PAUSED": (
            "This therapist's profile is paused — they cannot hold cases until HR restores it."
        ),
        "THERAPIST_PROFILE_DELETED": (
            "This therapist's profile is deleted — they cannot hold cases until restored."
        ),
    }
    raise TherapistIneligibleError(code, messages.get(code, "Therapist is not eligible to hold this case."))


def user_may_login(db: Session, user: User) -> tuple[bool, str | None]:
    """Staff login gate. Non-therapists use is_active only; therapists use DEC-03 eligibility."""
    if not user.is_active:
        return False, "ACCOUNT_INACTIVE"
    if RoleName.THERAPIST.value not in (user.role_names or []):
        return True, None
    code = therapist_ineligibility_code(db, user.id)
    if code is None:
        return True, None
    return False, code


def apply_therapist_exit(
    db: Session,
    therapist_user_id: int,
    *,
    reason: str,
    end_date: date | None = None,
) -> dict:
    """
    End ACTIVE assignments and surface cases for PENDING_REPLACEMENT attention.
    Does not rewrite historical sessions/payouts.
    """
    today = end_date or today_ist()
    reason_clean = (reason or "Therapist exit").strip()[:255]
    active = list(
        db.scalars(
            select(CaseAssignment).where(
                CaseAssignment.therapist_user_id == therapist_user_id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
        ).all()
    )
    case_ids: list[int] = []
    for assignment in active:
        case_ids.append(assignment.case_id)
        if assignment.case_service_id is not None:
            existing_ended = db.scalars(
                select(CaseAssignment).where(
                    CaseAssignment.case_service_id == assignment.case_service_id,
                    CaseAssignment.therapist_user_id == therapist_user_id,
                    CaseAssignment.status == CaseAssignmentStatus.ENDED,
                    CaseAssignment.id != assignment.id,
                )
            ).first()
            if existing_ended is not None:
                existing_ended.end_date = today
                existing_ended.reason_for_change = reason_clean
                db.delete(assignment)
                continue
        assignment.status = CaseAssignmentStatus.ENDED
        assignment.end_date = today
        assignment.reason_for_change = reason_clean

    replacement_case_ids: list[int] = []
    for case_id in sorted(set(case_ids)):
        case = db.get(Case, case_id)
        if case is None:
            continue
        status = case.status.value if hasattr(case.status, "value") else str(case.status)
        if status in (
            CaseStatus.ACTIVE.value,
            CaseStatus.PENDING_ALLOTMENT.value,
        ):
            case.status = CaseStatus.PENDING_REPLACEMENT
            case.status_effective_date = today
            case.status_reason = reason_clean[:512] if hasattr(case, "status_reason") else None
            replacement_case_ids.append(case_id)

    db.flush()
    return {
        "ended_assignments": len(active),
        "case_ids": sorted(set(case_ids)),
        "pending_replacement_case_ids": replacement_case_ids,
    }


def maybe_apply_exit_after_status_change(
    db: Session,
    therapist_user_id: int,
    *,
    reason: str,
) -> dict | None:
    """If therapist is now ineligible, run exit side-effects once."""
    if therapist_may_hold_case(db, therapist_user_id):
        return None
    return apply_therapist_exit(db, therapist_user_id, reason=reason)


def find_open_restore_ticket(db: Session, user_id: int) -> SupportTicket | None:
    return db.scalars(
        select(SupportTicket)
        .where(
            SupportTicket.raised_by_user_id == user_id,
            SupportTicket.category == TicketCategory.HR,
            SupportTicket.subject == RESTORE_TICKET_SUBJECT,
            SupportTicket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS]),
        )
        .order_by(SupportTicket.id.desc())
    ).first()


def create_status_restore_request(
    db: Session,
    user: User,
    *,
    note: str | None = None,
) -> SupportTicket:
    existing = find_open_restore_ticket(db, user.id)
    if existing:
        return existing
    body = (
        f"Therapist {user.full_name} ({user.email}) requested profile/employment status restore.\n"
        f"is_active={user.is_active}; employment={_emp_value(user)}.\n"
    )
    if note:
        body += f"\nNote from therapist: {note.strip()[:1000]}"
    ticket = SupportTicket(
        case_id=None,
        raised_by_user_id=user.id,
        category=TicketCategory.HR,
        topic=TicketTopic.OTHER,
        subject=RESTORE_TICKET_SUBJECT,
        body=body,
        status=TicketStatus.OPEN,
    )
    db.add(ticket)
    db.flush()
    db.add(
        TicketMessage(
            ticket_id=ticket.id,
            author_user_id=user.id,
            body=body,
            is_internal=False,
        )
    )
    db.flush()
    return ticket
