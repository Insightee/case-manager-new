from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case, CaseStatus
from app.models.parent import ParentGuardian, parent_child_link
from app.models.user import User
from app.services import parent_service


def acceptance_gating_enabled() -> bool:
    """When false, acceptance fields are audit/UX only and do not block portal actions."""
    return bool(settings.acceptance_gating_enabled)


def requires_acceptance(assignment: CaseAssignment | None) -> bool:
    if not acceptance_gating_enabled():
        return False
    return assignment is not None and assignment.assignment_offer_sent_at is not None


def parent_has_accepted(assignment: CaseAssignment | None) -> bool:
    if not acceptance_gating_enabled():
        return True
    if not requires_acceptance(assignment):
        return True
    return assignment.parent_accepted_at is not None


def therapist_may_operate_sessions(assignment: CaseAssignment | None) -> bool:
    if not acceptance_gating_enabled():
        return True
    if not requires_acceptance(assignment):
        return True
    return assignment.parent_accepted_at is not None


def active_assignment_for_case(db: Session, case_id: int) -> CaseAssignment | None:
    return db.scalars(
        select(CaseAssignment)
        .where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
        .order_by(CaseAssignment.id.desc())
    ).first()


def assert_therapist_may_start_session(db: Session, case_id: int) -> None:
    if not acceptance_gating_enabled():
        return
    assignment = active_assignment_for_case(db, case_id)
    if not therapist_may_operate_sessions(assignment):
        raise ValueError(
            "This case is waiting for the parent to accept the assignment before sessions can start."
        )


def assert_parent_session_access(db: Session, user: User, case_id: int) -> None:
    if not acceptance_gating_enabled():
        return
    case = db.get(Case, case_id)
    if not case:
        raise ValueError("Case not found")
    child_ids = parent_service.child_ids_for_parent(db, user.id)
    if case.child_id not in child_ids:
        raise ValueError("Case access denied")
    assignment = active_assignment_for_case(db, case_id)
    if case.status == CaseStatus.ACTIVE and requires_acceptance(assignment):
        if not parent_has_accepted(assignment):
            raise ValueError(
                "Please accept your care assignment before accessing session details."
            )


def accept_assignment_as_therapist(db: Session, assignment_id: int, therapist_user_id: int) -> CaseAssignment:
    assignment = db.get(CaseAssignment, assignment_id)
    if not assignment or assignment.status != CaseAssignmentStatus.ACTIVE:
        raise ValueError("Assignment not found")
    if assignment.therapist_user_id != therapist_user_id:
        raise ValueError("Not your assignment")
    if acceptance_gating_enabled() and not requires_acceptance(assignment):
        raise ValueError("This assignment does not require acceptance")
    if assignment.therapist_accepted_at:
        return assignment
    assignment.therapist_accepted_at = datetime.now(timezone.utc)
    db.flush()
    return assignment


def accept_assignment_as_parent(db: Session, assignment_id: int, parent_user_id: int) -> CaseAssignment:
    assignment = db.get(CaseAssignment, assignment_id)
    if not assignment or assignment.status != CaseAssignmentStatus.ACTIVE:
        raise ValueError("Assignment not found")
    case = db.get(Case, assignment.case_id)
    if not case:
        raise ValueError("Case not found")
    child_ids = parent_service.child_ids_for_parent(db, parent_user_id)
    if case.child_id not in child_ids:
        raise ValueError("Not linked to this case")
    if acceptance_gating_enabled() and not requires_acceptance(assignment):
        raise ValueError("This assignment does not require acceptance")
    if assignment.parent_accepted_at:
        return assignment
    assignment.parent_accepted_at = datetime.now(timezone.utc)
    db.flush()
    return assignment


def pending_acceptance_for_parent(db: Session, user: User) -> list[dict]:
    child_ids = parent_service.child_ids_for_parent(db, user.id)
    if not child_ids:
        return []
    cases = db.scalars(
        select(Case)
        .where(Case.child_id.in_(child_ids), Case.status == CaseStatus.ACTIVE)
        .options(selectinload(Case.child))
    ).all()
    if not cases:
        return []
    case_ids = [c.id for c in cases]
    assignments = db.scalars(
        select(CaseAssignment)
        .where(
            CaseAssignment.case_id.in_(case_ids),
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            CaseAssignment.assignment_offer_sent_at.isnot(None),
            CaseAssignment.parent_accepted_at.is_(None),
        )
    ).all()
    case_by_id = {c.id: c for c in cases}
    therapist_ids = {a.therapist_user_id for a in assignments}
    therapists = {}
    if therapist_ids:
        for u in db.scalars(select(User).where(User.id.in_(therapist_ids))).all():
            therapists[u.id] = u.full_name
    rows = []
    for a in assignments:
        case = case_by_id.get(a.case_id)
        if not case:
            continue
        rows.append(
            {
                "assignment_id": a.id,
                "case_id": case.id,
                "case_code": case.case_code,
                "child_name": case.child.full_name if case.child else "",
                "therapist_name": therapists.get(a.therapist_user_id),
                "offer_sent_at": a.assignment_offer_sent_at.isoformat() if a.assignment_offer_sent_at else None,
            }
        )
    return rows


def pending_acceptance_for_therapist(db: Session, therapist_user_id: int) -> list[dict]:
    assignments = db.scalars(
        select(CaseAssignment)
        .where(
            CaseAssignment.therapist_user_id == therapist_user_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            CaseAssignment.assignment_offer_sent_at.isnot(None),
            CaseAssignment.therapist_accepted_at.is_(None),
        )
    ).all()
    if not assignments:
        return []
    case_ids = {a.case_id for a in assignments}
    cases = {
        c.id: c
        for c in db.scalars(
            select(Case).where(Case.id.in_(case_ids)).options(selectinload(Case.child))
        ).all()
    }
    rows = []
    for a in assignments:
        case = cases.get(a.case_id)
        if not case or case.status != CaseStatus.ACTIVE:
            continue
        rows.append(
            {
                "assignment_id": a.id,
                "case_id": case.id,
                "case_code": case.case_code,
                "child_name": case.child.full_name if case.child else "",
                "parent_accepted": a.parent_accepted_at is not None,
                "offer_sent_at": a.assignment_offer_sent_at.isoformat() if a.assignment_offer_sent_at else None,
            }
        )
    return rows


def assignment_acceptance_fields(assignment: CaseAssignment) -> dict:
    offer_sent = assignment.assignment_offer_sent_at is not None
    return {
        "therapist_accepted_at": assignment.therapist_accepted_at,
        "parent_accepted_at": assignment.parent_accepted_at,
        "assignment_offer_sent_at": assignment.assignment_offer_sent_at,
        "requires_acceptance": acceptance_gating_enabled() and offer_sent,
        "parent_accepted": assignment.parent_accepted_at is not None
        if (acceptance_gating_enabled() and offer_sent)
        else True,
        "therapist_accepted": assignment.therapist_accepted_at is not None
        if (acceptance_gating_enabled() and offer_sent)
        else True,
    }
