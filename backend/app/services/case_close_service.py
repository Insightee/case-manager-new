from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assignment import BookingMode, CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.recurring_schedule import RecurringScheduleAssignment, RecurringScheduleStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.slot import SlotStatus, TherapistSlot


def assert_no_blocking_invoices_for_close(db: Session, case_id: int) -> None:
    from app.models.client_billing import ClientInvoice, ClientInvoiceStatus

    blocking = db.scalars(
        select(ClientInvoice).where(
            ClientInvoice.case_id == case_id,
            ClientInvoice.status.in_(
                (ClientInvoiceStatus.DRAFT, ClientInvoiceStatus.GENERATED),
            ),
        )
    ).first()
    if blocking:
        raise ValueError(
            "Finalize or void draft client invoices before closing this case"
        )


def cleanup_future_bookings(db: Session, case_id: int) -> None:
    """Cancel future booked slots and scheduled sessions for a case."""
    from app.services import scheduling_service as sched_svc

    today = date.today()
    slots = db.scalars(
        select(TherapistSlot).where(
            TherapistSlot.case_id == case_id,
            TherapistSlot.status == SlotStatus.BOOKED,
            TherapistSlot.slot_date >= today,
        )
    ).all()
    for slot in slots:
        sched_svc.cancel_booking_with_reason(db, slot.id, reason="Case closed")

    sessions = db.scalars(
        select(TherapySession).where(
            TherapySession.case_id == case_id,
            TherapySession.status == SessionStatus.SCHEDULED,
            TherapySession.scheduled_date >= today,
        )
    ).all()
    for session in sessions:
        session.status = SessionStatus.CANCELLED
    db.flush()


def cancel_recurring_schedules(db: Session, case_id: int) -> None:
    rows = db.scalars(
        select(RecurringScheduleAssignment).where(
            RecurringScheduleAssignment.case_id == case_id,
            RecurringScheduleAssignment.status == RecurringScheduleStatus.ACTIVE,
        )
    ).all()
    for row in rows:
        row.status = RecurringScheduleStatus.CANCELLED
    db.flush()


def clear_fixed_booking_on_assignments(db: Session, case_id: int) -> None:
    assignments = db.scalars(
        select(CaseAssignment).where(CaseAssignment.case_id == case_id)
    ).all()
    for assignment in assignments:
        assignment.booking_mode = BookingMode.OPEN.value
        assignment.fixed_weekdays = None
        assignment.fixed_start_time = None
        assignment.fixed_end_time = None
        assignment.fixed_recurrence_group_id = None
    db.flush()


def end_active_assignments(db: Session, case_id: int, *, reason: str = "Case closed") -> None:
    today = date.today()
    active = db.scalars(
        select(CaseAssignment).where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
    ).all()
    for assignment in active:
        assignment.status = CaseAssignmentStatus.ENDED
        assignment.end_date = today
        assignment.reason_for_change = reason
    db.flush()


def apply_case_closed_side_effects(db: Session, case: Case) -> None:
    """Run when a case is closed: clear schedules and end therapist assignment. No parent emails."""
    cleanup_future_bookings(db, case.id)
    cancel_recurring_schedules(db, case.id)
    clear_fixed_booking_on_assignments(db, case.id)
    end_active_assignments(db, case.id)
