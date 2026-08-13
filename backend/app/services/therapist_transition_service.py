from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.billing_validation import apply_billing_payload, case_billing_dict, validate_case_billing
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.case_therapist_transition import (
    TRANSITION_DEFAULT_DAY_COUNT,
    TRANSITION_HALF_DAY_PAY_INR,
    TRANSITION_FULL_DAY_PAY_INR,
    CaseTherapistTransition,
    CaseTherapistTransitionStatus,
)
from app.models.user import User
from app.services import assignment_service, case_service_service

OPEN_TRANSITION_STATUSES = frozenset(
    {
        CaseTherapistTransitionStatus.SCHEDULED,
        CaseTherapistTransitionStatus.ACTIVE,
    }
)


def _parse_transition_dates(raw_dates: list[str]) -> list[date]:
    if len(raw_dates) != TRANSITION_DEFAULT_DAY_COUNT:
        raise ValueError(f"Please choose exactly {TRANSITION_DEFAULT_DAY_COUNT} transition dates.")
    parsed: list[date] = []
    for raw in raw_dates:
        try:
            parsed.append(date.fromisoformat(str(raw)[:10]))
        except ValueError as exc:
            raise ValueError("Each transition date must be a valid calendar date.") from exc
    if len(set(parsed)) != len(parsed):
        raise ValueError("Transition dates must be unique.")
    parsed.sort()
    return parsed


def _transition_status_for_dates(dates: list[date], *, today: date | None = None) -> CaseTherapistTransitionStatus:
    ref = today or date.today()
    if ref < dates[0]:
        return CaseTherapistTransitionStatus.SCHEDULED
    if ref <= dates[-1]:
        return CaseTherapistTransitionStatus.ACTIVE
    return CaseTherapistTransitionStatus.ACTIVE


def active_transition_for_case(db: Session, case_id: int) -> CaseTherapistTransition | None:
    return db.scalars(
        select(CaseTherapistTransition)
        .where(
            CaseTherapistTransition.case_id == case_id,
            CaseTherapistTransition.status.in_(OPEN_TRANSITION_STATUSES),
        )
        .order_by(CaseTherapistTransition.id.desc())
        .limit(1)
    ).first()


def list_transitions_for_case(db: Session, case_id: int) -> list[CaseTherapistTransition]:
    return list(
        db.scalars(
            select(CaseTherapistTransition)
            .where(CaseTherapistTransition.case_id == case_id)
            .order_by(CaseTherapistTransition.id.desc())
        ).all()
    )


def _validate_pending_billing(case: Case, billing_update: dict) -> None:
    if not billing_update:
        raise ValueError("Please enter billing for the incoming therapist before starting the transition.")
    probe = Case(
        case_code=case.case_code,
        child_id=case.child_id,
        service_type=case.service_type,
        product_module=case.product_module,
        billing_type=case.billing_type,
        client_rate_per_session_inr=case.client_rate_per_session_inr,
        client_monthly_rate_inr=case.client_monthly_rate_inr,
        package_session_count=case.package_session_count,
        package_amount_inr=case.package_amount_inr,
        compensation_mode=case.compensation_mode,
        pay_share_amount_inr=case.pay_share_amount_inr,
        therapist_fixed_pay_inr=case.therapist_fixed_pay_inr,
        client_billing_mode=case.client_billing_mode,
        product_billing_rule_id=case.product_billing_rule_id,
        billing_notes=case.billing_notes,
    )
    apply_billing_payload(probe, billing_update, user_id=None)
    validate_case_billing(probe)


def create_transition(
    db: Session,
    *,
    case_id: int,
    incoming_therapist_user_id: int,
    transition_dates: list[str],
    billing_update: dict,
    created_by_user_id: int,
    notes: str | None = None,
) -> CaseTherapistTransition:
    case = db.get(Case, case_id)
    if not case:
        raise ValueError("Case not found")

    if active_transition_for_case(db, case_id):
        raise ValueError("This case already has an active therapist transition in progress.")

    dates = _parse_transition_dates(transition_dates)
    _validate_pending_billing(case, billing_update)

    case_service = case_service_service.ensure_default_case_service(db, case)
    outgoing = db.scalars(
        select(CaseAssignment).where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.case_service_id == case_service.id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
    ).first()
    if not outgoing:
        raise ValueError("Assign a primary therapist before starting a transition handover.")
    if outgoing.therapist_user_id == incoming_therapist_user_id:
        raise ValueError("The transition therapist must be different from the current therapist.")

    incoming = assignment_service.add_assignment_to_service(
        db,
        case_id=case_id,
        case_service_id=case_service.id,
        therapist_user_id=incoming_therapist_user_id,
        assigned_by_user_id=created_by_user_id,
        start_date=dates[0],
        notes="Transition handover — incoming therapist",
    )

    transition = CaseTherapistTransition(
        case_id=case_id,
        case_service_id=case_service.id,
        outgoing_therapist_user_id=outgoing.therapist_user_id,
        incoming_therapist_user_id=incoming_therapist_user_id,
        outgoing_assignment_id=outgoing.id,
        incoming_assignment_id=incoming.id,
        transition_dates=[d.isoformat() for d in dates],
        status=_transition_status_for_dates(dates),
        pending_billing_update=billing_update,
        full_day_pay_inr=TRANSITION_FULL_DAY_PAY_INR,
        half_day_pay_inr=TRANSITION_HALF_DAY_PAY_INR,
        notes=notes,
        created_by_user_id=created_by_user_id,
    )
    db.add(transition)
    db.flush()
    return transition


def complete_transition(
    db: Session,
    transition: CaseTherapistTransition,
    *,
    actor_user_id: int | None = None,
) -> CaseTherapistTransition:
    if transition.status == CaseTherapistTransitionStatus.COMPLETED:
        return transition
    if transition.status == CaseTherapistTransitionStatus.CANCELLED:
        raise ValueError("This transition was cancelled and cannot be completed.")

    case = db.get(Case, transition.case_id)
    if not case:
        raise ValueError("Case not found")

    dates = [date.fromisoformat(str(d)[:10]) for d in transition.transition_dates]
    last_date = max(dates)

    outgoing = db.get(CaseAssignment, transition.outgoing_assignment_id)
    if outgoing and outgoing.status == CaseAssignmentStatus.ACTIVE:
        outgoing.status = CaseAssignmentStatus.TRANSFERRED
        outgoing.end_date = last_date
        outgoing.reason_for_change = "Transition handover completed"
        outgoing.billing_snapshot = case_billing_dict(case)

    apply_billing_payload(case, transition.pending_billing_update, actor_user_id or transition.created_by_user_id)

    transition.status = CaseTherapistTransitionStatus.COMPLETED
    transition.completed_at = datetime.now(timezone.utc)
    db.flush()
    return transition


def complete_due_transitions(db: Session, *, today: date | None = None) -> list[CaseTherapistTransition]:
    ref = today or date.today()
    rows = list(
        db.scalars(
            select(CaseTherapistTransition).where(
                CaseTherapistTransition.status.in_(OPEN_TRANSITION_STATUSES),
            )
        ).all()
    )
    completed: list[CaseTherapistTransition] = []
    for row in rows:
        dates = [date.fromisoformat(str(d)[:10]) for d in row.transition_dates]
        if ref <= dates[-1]:
            if row.status != _transition_status_for_dates(dates, today=ref):
                row.status = _transition_status_for_dates(dates, today=ref)
            continue
        completed.append(complete_transition(db, row))
    if completed:
        db.flush()
    return completed


def transition_to_read_dict(db: Session, transition: CaseTherapistTransition) -> dict:
    user_ids = {
        transition.outgoing_therapist_user_id,
        transition.incoming_therapist_user_id,
        transition.created_by_user_id,
    }
    users = {
        u.id: u
        for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()
    }
    outgoing = users.get(transition.outgoing_therapist_user_id)
    incoming = users.get(transition.incoming_therapist_user_id)
    creator = users.get(transition.created_by_user_id)
    return {
        "id": transition.id,
        "case_id": transition.case_id,
        "case_service_id": transition.case_service_id,
        "outgoing_therapist_user_id": transition.outgoing_therapist_user_id,
        "outgoing_therapist_name": outgoing.full_name if outgoing else None,
        "incoming_therapist_user_id": transition.incoming_therapist_user_id,
        "incoming_therapist_name": incoming.full_name if incoming else None,
        "outgoing_assignment_id": transition.outgoing_assignment_id,
        "incoming_assignment_id": transition.incoming_assignment_id,
        "transition_dates": list(transition.transition_dates or []),
        "status": transition.status.value,
        "pending_billing_update": transition.pending_billing_update,
        "full_day_pay_inr": float(transition.full_day_pay_inr),
        "half_day_pay_inr": float(transition.half_day_pay_inr),
        "notes": transition.notes,
        "created_by_user_id": transition.created_by_user_id,
        "created_by_name": creator.full_name if creator else None,
        "completed_at": transition.completed_at.isoformat() if transition.completed_at else None,
        "created_at": transition.created_at.isoformat() if transition.created_at else None,
    }
