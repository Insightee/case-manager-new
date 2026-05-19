from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assignment import CaseAssignment, CaseAssignmentStatus


def list_assignments(db: Session, case_id: int) -> list[CaseAssignment]:
    stmt = select(CaseAssignment).where(CaseAssignment.case_id == case_id).order_by(CaseAssignment.start_date.desc())
    return list(db.scalars(stmt).all())


def create_assignment(
    db: Session,
    *,
    case_id: int,
    therapist_user_id: int,
    assigned_by_user_id: int,
    start_date: date,
    reason_for_change: str | None = None,
    notes: str | None = None,
) -> CaseAssignment:
    active = db.scalars(
        select(CaseAssignment).where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
    ).all()
    for a in active:
        a.status = CaseAssignmentStatus.TRANSFERRED
        a.end_date = start_date
        a.reason_for_change = reason_for_change or "Reassigned"

    assignment = CaseAssignment(
        case_id=case_id,
        therapist_user_id=therapist_user_id,
        assigned_by_user_id=assigned_by_user_id,
        start_date=start_date,
        status=CaseAssignmentStatus.ACTIVE,
        reason_for_change=reason_for_change,
        notes=notes,
    )
    db.add(assignment)
    db.flush()
    return assignment
