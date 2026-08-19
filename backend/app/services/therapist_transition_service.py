from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.billing_validation import apply_billing_payload, case_billing_dict, validate_case_billing
from app.core.timezone import today_ist
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.daily_log import DailyLog
from app.models.leave import LeaveStatus, TherapistLeave
from app.models.case_therapist_transition import (
    TRANSITION_DEFAULT_DAY_COUNT,
    TRANSITION_HALF_DAY_PAY_INR,
    TRANSITION_FULL_DAY_PAY_INR,
    CaseTherapistTransition,
    CaseTherapistTransitionDay,
    CaseTherapistTransitionStatus,
)
from app.models.session import Session as TherapySession
from app.models.user import User
from app.services import assignment_service, billing_approval_service, case_day_type_service, case_service_service

OPEN_TRANSITION_STATUSES = frozenset(
    {
        CaseTherapistTransitionStatus.SCHEDULED,
        CaseTherapistTransitionStatus.ACTIVE,
    }
)

logger = logging.getLogger(__name__)


def coerced_transition_dates(raw_dates) -> list[date]:
    """Parse handover dates; skip invalid values instead of crashing callers."""
    if not raw_dates:
        return []
    out: list[date] = []
    for value in raw_dates:
        try:
            parsed = date.fromisoformat(str(value)[:10])
        except (TypeError, ValueError):
            continue
        out.append(parsed)
    return out


def _parse_transition_dates(
    raw_dates: list[str],
    *,
    today: date | None = None,
    allowed_past_dates: set[date] | None = None,
) -> list[date]:
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
    ref = today or today_ist()
    permitted = allowed_past_dates or set()
    if any(value < ref and value not in permitted for value in parsed):
        raise ValueError("Choose today or a future date for the transition.")
    return parsed


def _day_type_value(case: Case) -> str:
    if case_day_type_service.product_requires_day_type(case.product_module) and not case.day_type:
        raise ValueError("Select half day or full day before starting a therapist transition.")
    return case.day_type.value if case.day_type else "FULL_DAY"


def _transition_pay_rate(day_type: str) -> float:
    if day_type == "HALF_DAY":
        return float(TRANSITION_HALF_DAY_PAY_INR)
    return float(TRANSITION_FULL_DAY_PAY_INR)


def _leave_applies_to_case(leave: TherapistLeave, case_id: int) -> bool:
    scoped_ids = {int(value) for value in (leave.case_ids or [])}
    if leave.case_id is not None:
        scoped_ids.add(int(leave.case_id))
    return not scoped_ids or case_id in scoped_ids


def unavailable_transition_dates(
    db: Session,
    *,
    case_id: int,
    therapist_user_ids: set[int],
    start_date: date,
    end_date: date,
) -> dict[str, list[int]]:
    if not therapist_user_ids:
        return {}
    leaves = db.scalars(
        select(TherapistLeave).where(
            TherapistLeave.therapist_user_id.in_(therapist_user_ids),
            TherapistLeave.status.in_([LeaveStatus.PENDING, LeaveStatus.APPROVED]),
            TherapistLeave.start_date <= end_date,
            TherapistLeave.end_date >= start_date,
        )
    ).all()
    unavailable: dict[str, list[int]] = {}
    for leave in leaves:
        if not _leave_applies_to_case(leave, case_id):
            continue
        current = max(start_date, leave.start_date)
        last = min(end_date, leave.end_date)
        while current <= last:
            unavailable.setdefault(current.isoformat(), []).append(leave.therapist_user_id)
            current = current.fromordinal(current.toordinal() + 1)
    return unavailable


def _validate_therapist_leave_dates(
    db: Session,
    *,
    case_id: int,
    therapist_user_ids: set[int],
    dates: list[date],
) -> None:
    unavailable = unavailable_transition_dates(
        db,
        case_id=case_id,
        therapist_user_ids=therapist_user_ids,
        start_date=min(dates),
        end_date=max(dates),
    )
    conflicts = [d.isoformat() for d in dates if d.isoformat() in unavailable]
    if conflicts:
        raise ValueError(
            f"One of the therapists has pending or approved leave on: {', '.join(conflicts)}."
        )


def _transition_status_for_dates(dates: list[date], *, today: date | None = None) -> CaseTherapistTransitionStatus:
    ref = today or today_ist()
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


def _submitted_log_dates_for_participants(
    db: Session,
    *,
    case_id: int,
    therapist_user_ids: set[int],
    dates: list[date],
) -> set[date]:
    return set(
        db.scalars(
            select(TherapySession.scheduled_date)
            .join(DailyLog, DailyLog.session_id == TherapySession.id)
            .where(
                TherapySession.case_id == case_id,
                TherapySession.therapist_user_id.in_(therapist_user_ids),
                TherapySession.scheduled_date.in_(dates),
                DailyLog.submitted_at.is_not(None),
            )
        ).all()
    )


def submitted_transition_dates(db: Session, transition_id: int) -> set[date]:
    linked_dates = set(
        db.scalars(
            select(CaseTherapistTransitionDay.transition_date)
            .join(
                DailyLog,
                DailyLog.transition_day_id == CaseTherapistTransitionDay.id,
            )
            .where(
                CaseTherapistTransitionDay.transition_id == transition_id,
                DailyLog.submitted_at.is_not(None),
            )
        ).all()
    )
    transition = db.get(CaseTherapistTransition, transition_id)
    if not transition:
        return linked_dates
    dates = [date.fromisoformat(str(value)[:10]) for value in transition.transition_dates]
    participant_dates = _submitted_log_dates_for_participants(
        db,
        case_id=transition.case_id,
        therapist_user_ids={
            transition.outgoing_therapist_user_id,
            transition.incoming_therapist_user_id,
        },
        dates=dates,
    )
    return linked_dates | participant_dates


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
    day_type = _day_type_value(case)

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
    participant_ids = {outgoing.therapist_user_id, incoming_therapist_user_id}
    _validate_therapist_leave_dates(
        db,
        case_id=case_id,
        therapist_user_ids=participant_ids,
        dates=dates,
    )
    existing_log_dates = _submitted_log_dates_for_participants(
        db,
        case_id=case_id,
        therapist_user_ids=participant_ids,
        dates=dates,
    )
    if existing_log_dates:
        labels = ", ".join(sorted(item.isoformat() for item in existing_log_dates))
        raise ValueError(f"Transition dates cannot already have submitted therapist logs: {labels}.")

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
        day_type=day_type,
        full_day_pay_inr=TRANSITION_FULL_DAY_PAY_INR,
        half_day_pay_inr=TRANSITION_HALF_DAY_PAY_INR,
        notes=notes,
        created_by_user_id=created_by_user_id,
    )
    db.add(transition)
    db.flush()
    pay_rate = _transition_pay_rate(day_type)
    for transition_date in dates:
        db.add(
            CaseTherapistTransitionDay(
                transition_id=transition.id,
                transition_date=transition_date,
                day_type=day_type,
                pay_rate_inr=pay_rate,
            )
        )
    db.flush()
    return transition


def transition_day_for_session(
    db: Session,
    *,
    case_id: int,
    therapist_user_id: int,
    scheduled_date: date,
) -> tuple[CaseTherapistTransition, CaseTherapistTransitionDay] | None:
    transitions = db.scalars(
        select(CaseTherapistTransition).where(
            CaseTherapistTransition.case_id == case_id,
            CaseTherapistTransition.status.in_(OPEN_TRANSITION_STATUSES),
            or_(
                CaseTherapistTransition.outgoing_therapist_user_id == therapist_user_id,
                CaseTherapistTransition.incoming_therapist_user_id == therapist_user_id,
            ),
        )
    ).all()
    for transition in transitions:
        transition_dates = {
            date.fromisoformat(str(value)[:10]) for value in (transition.transition_dates or [])
        }
        if scheduled_date not in transition_dates:
            continue
        day = db.scalars(
            select(CaseTherapistTransitionDay).where(
                CaseTherapistTransitionDay.transition_id == transition.id,
                CaseTherapistTransitionDay.transition_date == scheduled_date,
            )
        ).first()
        if not day:
            case = db.get(Case, case_id)
            case_day_type = case.day_type.value if case and case.day_type else None
            day_type = transition.day_type or case_day_type or "FULL_DAY"
            if not transition.day_type:
                transition.day_type = day_type
            day = CaseTherapistTransitionDay(
                transition_id=transition.id,
                transition_date=scheduled_date,
                day_type=day_type,
                pay_rate_inr=_transition_pay_rate(day_type),
            )
            db.add(day)
            db.flush()
        return transition, day
    return None


def transition_context_for_session(
    db: Session,
    *,
    case_id: int,
    therapist_user_id: int,
    scheduled_date: date,
) -> dict | None:
    """Return read-only handover context for a therapist session."""
    transitions = db.scalars(
        select(CaseTherapistTransition).where(
            CaseTherapistTransition.case_id == case_id,
            CaseTherapistTransition.status.in_(OPEN_TRANSITION_STATUSES),
            or_(
                CaseTherapistTransition.outgoing_therapist_user_id == therapist_user_id,
                CaseTherapistTransition.incoming_therapist_user_id == therapist_user_id,
            ),
        )
    ).all()
    for transition in transitions:
        transition_dates = sorted(
            date.fromisoformat(str(value)[:10]) for value in (transition.transition_dates or [])
        )
        if scheduled_date not in transition_dates:
            continue
        role = (
            "outgoing"
            if transition.outgoing_therapist_user_id == therapist_user_id
            else "incoming"
        )
        participant_ids = {
            transition.outgoing_therapist_user_id,
            transition.incoming_therapist_user_id,
        }
        users = {
            user.id: user
            for user in db.scalars(select(User).where(User.id.in_(participant_ids))).all()
        }
        outgoing = users.get(transition.outgoing_therapist_user_id)
        incoming = users.get(transition.incoming_therapist_user_id)
        case = db.get(Case, case_id)
        case_day_type = case.day_type.value if case and case.day_type else None
        return {
            "is_transition_session": True,
            "transition_id": transition.id,
            "transition_role": role,
            "transition_day_number": transition_dates.index(scheduled_date) + 1,
            "transition_day_count": len(transition_dates),
            "transition_day_type": transition.day_type or case_day_type,
            "outgoing_therapist_name": outgoing.full_name if outgoing else None,
            "incoming_therapist_name": incoming.full_name if incoming else None,
        }
    return None


def update_transition_dates(
    db: Session,
    transition: CaseTherapistTransition,
    *,
    transition_dates: list[str],
) -> CaseTherapistTransition:
    if transition.status not in OPEN_TRANSITION_STATUSES:
        raise ValueError("Only an open therapist transition can be rescheduled.")
    locked_dates = submitted_transition_dates(db, transition.id)
    dates = _parse_transition_dates(
        transition_dates,
        allowed_past_dates=locked_dates,
    )
    if not locked_dates.issubset(set(dates)):
        labels = ", ".join(sorted(value.isoformat() for value in locked_dates))
        raise ValueError(f"Dates with submitted transition logs cannot be changed: {labels}.")

    participant_ids = {
        transition.outgoing_therapist_user_id,
        transition.incoming_therapist_user_id,
    }
    editable_dates = [value for value in dates if value not in locked_dates]
    if editable_dates:
        _validate_therapist_leave_dates(
            db,
            case_id=transition.case_id,
            therapist_user_ids=participant_ids,
            dates=editable_dates,
        )
    existing_log_dates = _submitted_log_dates_for_participants(
        db,
        case_id=transition.case_id,
        therapist_user_ids=participant_ids,
        dates=editable_dates,
    )
    if existing_log_dates:
        labels = ", ".join(sorted(value.isoformat() for value in existing_log_dates))
        raise ValueError(f"New transition dates cannot already have submitted logs: {labels}.")

    existing_days = {
        item.transition_date: item
        for item in db.scalars(
            select(CaseTherapistTransitionDay).where(
                CaseTherapistTransitionDay.transition_id == transition.id
            )
        ).all()
    }
    for transition_date, day in existing_days.items():
        if transition_date not in dates:
            db.delete(day)
    day_type = transition.day_type or "FULL_DAY"
    for transition_date in dates:
        if transition_date not in existing_days:
            db.add(
                CaseTherapistTransitionDay(
                    transition_id=transition.id,
                    transition_date=transition_date,
                    day_type=day_type,
                    pay_rate_inr=_transition_pay_rate(day_type),
                )
            )

    transition.transition_dates = [value.isoformat() for value in dates]
    transition.status = _transition_status_for_dates(dates)
    incoming = db.get(CaseAssignment, transition.incoming_assignment_id)
    if incoming and not locked_dates:
        incoming.start_date = dates[0]
    db.flush()
    return transition


def cancel_transition(
    db: Session,
    transition: CaseTherapistTransition,
    *,
    actor_user_id: int,
    reason: str | None = None,
) -> CaseTherapistTransition:
    if transition.status not in OPEN_TRANSITION_STATUSES:
        raise ValueError("Only an open therapist transition can be cancelled.")
    if submitted_transition_dates(db, transition.id):
        raise ValueError("This transition can no longer be cancelled because a transition log exists.")
    incoming = db.get(CaseAssignment, transition.incoming_assignment_id)
    if incoming and incoming.status == CaseAssignmentStatus.ACTIVE:
        incoming.status = CaseAssignmentStatus.ENDED
        incoming.end_date = incoming.start_date
        incoming.reason_for_change = "Transition handover cancelled"
    transition.status = CaseTherapistTransitionStatus.CANCELLED
    transition.cancelled_by_user_id = actor_user_id
    transition.cancelled_at = datetime.now(timezone.utc)
    transition.cancellation_reason = (reason or "").strip() or None
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

    dates = coerced_transition_dates(transition.transition_dates)
    last_date = max(dates) if dates else today_ist()

    outgoing = db.get(CaseAssignment, transition.outgoing_assignment_id)
    if outgoing and outgoing.status == CaseAssignmentStatus.ACTIVE:
        outgoing.status = CaseAssignmentStatus.TRANSFERRED
        outgoing.end_date = last_date
        outgoing.reason_for_change = "Transition handover completed"
        outgoing.billing_snapshot = case_billing_dict(case)

    billing_payload = transition.pending_billing_update or {}
    actor_id = actor_user_id or transition.created_by_user_id
    try:
        requester = db.get(User, actor_id) if actor_id else None
        if requester is None:
            apply_billing_payload(case, billing_payload, actor_id)
        else:
            try:
                billing_approval_service.apply_or_request(
                    db,
                    case=case,
                    proposed=billing_payload,
                    requester=requester,
                )
            except ValueError as exc:
                if "already pending" not in str(exc).lower():
                    logger.warning(
                        "Transition %s billing approval skipped (%s); applying payload directly",
                        transition.id,
                        exc,
                    )
                    apply_billing_payload(case, billing_payload, requester.id)
    except Exception:
        logger.exception(
            "Transition %s billing apply failed; completing handover without billing write",
            transition.id,
        )

    transition.status = CaseTherapistTransitionStatus.COMPLETED
    transition.completed_at = datetime.now(timezone.utc)
    db.flush()
    return transition


def complete_due_transitions(db: Session, *, today: date | None = None) -> list[CaseTherapistTransition]:
    ref = today or today_ist()
    rows = list(
        db.scalars(
            select(CaseTherapistTransition).where(
                CaseTherapistTransition.status.in_(OPEN_TRANSITION_STATUSES),
            )
        ).all()
    )
    completed: list[CaseTherapistTransition] = []
    for row in rows:
        dates = sorted(coerced_transition_dates(row.transition_dates))
        if not dates:
            logger.warning("Skipping therapist transition %s: no valid handover dates", row.id)
            continue
        if ref <= dates[-1]:
            expected = _transition_status_for_dates(dates, today=ref)
            if row.status != expected:
                row.status = expected
            continue
        try:
            with db.begin_nested():
                completed.append(complete_transition(db, row))
        except Exception:
            logger.exception("Could not auto-complete therapist transition %s", row.id)
    if completed:
        db.flush()
    return completed


def complete_due_transition_for_case(
    db: Session,
    case_id: int,
    *,
    today: date | None = None,
) -> CaseTherapistTransition | None:
    transition = active_transition_for_case(db, case_id)
    if not transition:
        return None
    ref = today or today_ist()
    dates = sorted(coerced_transition_dates(transition.transition_dates))
    if not dates:
        logger.warning("Skipping therapist transition %s for case %s: no valid handover dates", transition.id, case_id)
        return transition
    if ref > max(dates):
        try:
            with db.begin_nested():
                return complete_transition(db, transition)
        except Exception:
            logger.exception("Could not auto-complete therapist transition %s for case %s", transition.id, case_id)
            return transition
    expected = _transition_status_for_dates(dates, today=ref)
    if transition.status != expected:
        transition.status = expected
        db.flush()
    return transition


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
    locked_dates = submitted_transition_dates(db, transition.id)
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
        "day_type": transition.day_type,
        "full_day_pay_inr": float(transition.full_day_pay_inr),
        "half_day_pay_inr": float(transition.half_day_pay_inr),
        "locked_dates": sorted(value.isoformat() for value in locked_dates),
        "can_cancel": transition.status in OPEN_TRANSITION_STATUSES and not locked_dates,
        "notes": transition.notes,
        "created_by_user_id": transition.created_by_user_id,
        "created_by_name": creator.full_name if creator else None,
        "completed_at": transition.completed_at.isoformat() if transition.completed_at else None,
        "cancelled_at": transition.cancelled_at.isoformat() if transition.cancelled_at else None,
        "cancellation_reason": transition.cancellation_reason,
        "created_at": transition.created_at.isoformat() if transition.created_at else None,
    }
