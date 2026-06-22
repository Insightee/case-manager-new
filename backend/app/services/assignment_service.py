from __future__ import annotations

from datetime import date, time

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.assignment import BookingMode, CaseAssignment, CaseAssignmentStatus
from app.models.case import Case, CaseStatus
from app.models.therapist_profile import TherapistProfile
from app.services import case_service_service

# Cases linked to an active therapist assignment that should mirror therapist primary CM.
CASE_CM_SYNC_STATUSES = frozenset(
    {
        CaseStatus.ACTIVE,
        CaseStatus.PENDING_ALLOTMENT,
        CaseStatus.PENDING_REPLACEMENT,
    }
)


def resolve_primary_case_manager_user_id(db: Session, therapist_user_id: int) -> int | None:
    profile = db.scalars(
        select(TherapistProfile).where(TherapistProfile.user_id == therapist_user_id)
    ).first()
    if not profile or not profile.supervisor_user_id:
        return None
    return profile.supervisor_user_id


def assigned_case_ids_for_therapist(db: Session, therapist_user_id: int) -> list[int]:
    """Case ids with an active assignment for this therapist and a sync-eligible status."""
    stmt = (
        select(Case.id)
        .join(CaseAssignment, CaseAssignment.case_id == Case.id)
        .where(
            CaseAssignment.therapist_user_id == therapist_user_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            Case.status.in_(CASE_CM_SYNC_STATUSES),
        )
        .distinct()
        .order_by(Case.id)
    )
    return list(db.scalars(stmt).all())


def sync_case_managers_for_therapist(db: Session, therapist_user_id: int, cm_user_id: int) -> int:
    """Set case_manager_user_id on all sync-eligible assigned cases for a therapist."""
    if not cm_user_id:
        return 0
    updated = 0
    for case_id in assigned_case_ids_for_therapist(db, therapist_user_id):
        case = db.get(Case, case_id)
        if case and case.case_manager_user_id != cm_user_id:
            case.case_manager_user_id = cm_user_id
            updated += 1
    if updated:
        db.flush()
    return updated


def backfill_case_managers_from_therapist_profiles(db: Session, *, dry_run: bool = True) -> dict:
    """Align case CM with each therapist profile primary CM for assigned sync-eligible cases."""
    profiles = list(
        db.scalars(
            select(TherapistProfile).where(TherapistProfile.supervisor_user_id.is_not(None))
        ).all()
    )
    mismatches: list[dict] = []
    cases_updated = 0
    therapists_touched = 0

    for profile in profiles:
        cm_id = profile.supervisor_user_id
        if not cm_id:
            continue
        therapist_updated = 0
        for case_id in assigned_case_ids_for_therapist(db, profile.user_id):
            case = db.get(Case, case_id)
            if not case or case.case_manager_user_id == cm_id:
                continue
            mismatches.append(
                {
                    "case_id": case.id,
                    "case_code": case.case_code,
                    "therapist_user_id": profile.user_id,
                    "old_case_manager_user_id": case.case_manager_user_id,
                    "new_case_manager_user_id": cm_id,
                }
            )
            if not dry_run:
                case.case_manager_user_id = cm_id
            therapist_updated += 1
            cases_updated += 1
        if therapist_updated:
            therapists_touched += 1

    if not dry_run and cases_updated:
        db.flush()

    return {
        "dry_run": dry_run,
        "therapists_touched": therapists_touched,
        "cases_updated": cases_updated,
        "mismatches": mismatches,
    }


def sync_case_manager_from_therapist(db: Session, case: Case, therapist_user_id: int) -> bool:
    """Align case.case_manager_user_id with the therapist's primary case manager."""
    cm_id = resolve_primary_case_manager_user_id(db, therapist_user_id)
    if not cm_id or case.case_manager_user_id == cm_id:
        return False
    case.case_manager_user_id = cm_id
    db.flush()
    return True


def _sync_case_manager_after_assignment(db: Session, case_id: int, therapist_user_id: int) -> None:
    case = db.get(Case, case_id)
    if case:
        sync_case_manager_from_therapist(db, case, therapist_user_id)


def list_assignments(db: Session, case_id: int) -> list[CaseAssignment]:
    stmt = select(CaseAssignment).where(CaseAssignment.case_id == case_id).order_by(CaseAssignment.start_date.desc())
    return list(db.scalars(stmt).all())


def list_active_cases_for_therapist(db: Session, therapist_user_id: int) -> list[dict]:
    from app.models.case import CaseStatus

    rows = db.scalars(
        select(CaseAssignment)
        .where(
            CaseAssignment.therapist_user_id == therapist_user_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
        .options(selectinload(CaseAssignment.case).selectinload(Case.child))
    ).all()
    seen: set[int] = set()
    items: list[dict] = []
    for assignment in rows:
        case = assignment.case
        if not case or case.id in seen:
            continue
        if case.status in (CaseStatus.CLOSED, CaseStatus.SUSPENDED):
            continue
        seen.add(case.id)
        items.append(
            {
                "id": case.id,
                "case_code": case.case_code,
                "child_name": case.child.full_name if case.child else None,
                "product_module": case.product_module,
                "service_type": case.service_type,
                "status": case.status.value,
            }
        )
    items.sort(key=lambda row: (row.get("child_name") or "", row.get("case_code") or ""))
    return items


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
    case = db.get(Case, case_id)
    if not case:
        raise ValueError("Case not found")
    case_service = case_service_service.ensure_default_case_service(db, case)
    # Compatibility path for legacy endpoint: preserve historical re-allot behavior.
    return replace_assignment_in_service(
        db,
        case_id=case_id,
        case_service_id=case_service.id,
        therapist_user_id=therapist_user_id,
        assigned_by_user_id=assigned_by_user_id,
        start_date=start_date,
        reason_for_change=reason_for_change,
        notes=notes,
    )


def add_assignment_to_service(
    db: Session,
    *,
    case_id: int,
    case_service_id: int,
    therapist_user_id: int,
    assigned_by_user_id: int,
    start_date: date,
    reason_for_change: str | None = None,
    notes: str | None = None,
) -> CaseAssignment:
    # Prevent duplicate active assignment for same therapist and service line.
    duplicate_active = db.scalars(
        select(CaseAssignment).where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.case_service_id == case_service_id,
            CaseAssignment.therapist_user_id == therapist_user_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
    ).first()
    if duplicate_active:
        raise ValueError("Therapist already has an active assignment for this service line")

    assignment = CaseAssignment(
        case_id=case_id,
        case_service_id=case_service_id,
        therapist_user_id=therapist_user_id,
        assigned_by_user_id=assigned_by_user_id,
        start_date=start_date,
        status=CaseAssignmentStatus.ACTIVE,
        reason_for_change=reason_for_change,
        notes=notes,
    )
    db.add(assignment)
    db.flush()
    _sync_case_manager_after_assignment(db, case_id, therapist_user_id)
    return assignment


def replace_assignment_in_service(
    db: Session,
    *,
    case_id: int,
    case_service_id: int,
    therapist_user_id: int,
    assigned_by_user_id: int,
    start_date: date,
    reason_for_change: str | None = None,
    notes: str | None = None,
) -> CaseAssignment:
    active = db.scalars(
        select(CaseAssignment).where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.case_service_id == case_service_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
    ).all()
    for a in active:
        a.status = CaseAssignmentStatus.TRANSFERRED
        a.end_date = start_date
        a.reason_for_change = reason_for_change or "Reassigned"

    assignment = CaseAssignment(
        case_id=case_id,
        case_service_id=case_service_id,
        therapist_user_id=therapist_user_id,
        assigned_by_user_id=assigned_by_user_id,
        start_date=start_date,
        status=CaseAssignmentStatus.ACTIVE,
        reason_for_change=reason_for_change,
        notes=notes,
    )
    db.add(assignment)
    db.flush()
    _sync_case_manager_after_assignment(db, case_id, therapist_user_id)
    return assignment


def _parse_time(value: str | None) -> time | None:
    if not value:
        return None
    parts = value.strip().split(":")
    return time(int(parts[0]), int(parts[1]))


def update_assignment_booking(db: Session, assignment_id: int, data: dict) -> CaseAssignment:
    assignment = db.get(CaseAssignment, assignment_id)
    if not assignment:
        raise ValueError("Assignment not found")
    if data.get("booking_mode") is not None:
        mode = data["booking_mode"]
        if mode not in (BookingMode.OPEN.value, BookingMode.FIXED.value):
            raise ValueError("booking_mode must be OPEN or FIXED")
        assignment.booking_mode = mode
    if "fixed_weekdays" in data:
        days = data.get("fixed_weekdays") or []
        assignment.set_fixed_weekdays(days)
    if data.get("fixed_start_time") is not None:
        assignment.fixed_start_time = _parse_time(data["fixed_start_time"])
    if data.get("fixed_end_time") is not None:
        assignment.fixed_end_time = _parse_time(data["fixed_end_time"])
    if "fixed_recurrence_group_id" in data:
        assignment.fixed_recurrence_group_id = data.get("fixed_recurrence_group_id")
    db.flush()
    return assignment


def assignment_to_read_dict(assignment: CaseAssignment, therapist_name: str | None = None) -> dict:
    from app.services.appointment_policy import assignment_booking_summary
    from app.services.assignment_acceptance_service import assignment_acceptance_fields

    summary = assignment_booking_summary(assignment)
    data = {
        "id": assignment.id,
        "case_id": assignment.case_id,
        "case_service_id": assignment.case_service_id,
        "therapist_user_id": assignment.therapist_user_id,
        "therapist_name": therapist_name,
        "assigned_by_user_id": assignment.assigned_by_user_id,
        "start_date": assignment.start_date,
        "end_date": assignment.end_date,
        "status": assignment.status.value,
        "reason_for_change": assignment.reason_for_change,
        "notes": assignment.notes,
        "booking_mode": assignment.booking_mode,
        "fixed_weekdays": assignment.get_fixed_weekdays(),
        "fixed_start_time": assignment.fixed_start_time.strftime("%H:%M") if assignment.fixed_start_time else None,
        "fixed_end_time": assignment.fixed_end_time.strftime("%H:%M") if assignment.fixed_end_time else None,
        "fixed_recurrence_group_id": assignment.fixed_recurrence_group_id,
        "fixed_window_label": summary.get("fixed_window_label"),
    }
    data.update(assignment_acceptance_fields(assignment))
    return data
