from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timezone import today_ist
from app.models.case import Case
from app.models.parent_meeting_request import ParentMeetingRequest, ParentMeetingRequestStatus
from app.models.user import User
from app.services import appointment_notification_service as appt_notify
from app.services import appointment_policy as policy
from app.services.appointment_booking_service import find_next_open_parent_slot


def create_meeting_request(
    db: Session,
    *,
    case_id: int,
    parent_user: User,
    therapist_user_id: int,
    requested_date: date,
    note: str | None = None,
) -> ParentMeetingRequest:
    if requested_date < today_ist():
        raise ValueError("Pick today or a future date.")
    max_date = today_ist() + timedelta(days=60)
    if requested_date > max_date:
        raise ValueError("Pick a date within the next 60 days.")

    case = db.get(Case, case_id)
    if not case:
        raise ValueError("Case not found")

    assignment = policy.get_active_assignment_for_case(db, case_id, therapist_user_id)
    if not assignment:
        raise ValueError("That therapist is not assigned to this case.")

    existing = db.scalars(
        select(ParentMeetingRequest).where(
            ParentMeetingRequest.case_id == case_id,
            ParentMeetingRequest.therapist_user_id == therapist_user_id,
            ParentMeetingRequest.requested_date == requested_date,
            ParentMeetingRequest.status == ParentMeetingRequestStatus.PENDING,
        )
    ).first()
    if existing:
        return existing

    row = ParentMeetingRequest(
        case_id=case_id,
        parent_user_id=parent_user.id,
        therapist_user_id=therapist_user_id,
        requested_date=requested_date,
        status=ParentMeetingRequestStatus.PENDING,
        note=(note or "").strip() or None,
    )
    db.add(row)
    db.flush()
    appt_notify.notify_therapist_parent_meeting_requested(db, row, parent_name=parent_user.full_name or "Parent")
    return row


def list_pending_for_therapist(db: Session, therapist_user_id: int) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(ParentMeetingRequest)
        .where(
            ParentMeetingRequest.therapist_user_id == therapist_user_id,
            ParentMeetingRequest.status == ParentMeetingRequestStatus.PENDING,
        )
        .order_by(ParentMeetingRequest.requested_date.asc(), ParentMeetingRequest.created_at.asc())
    ).all()
    out: list[dict[str, Any]] = []
    for r in rows:
        case = db.get(Case, r.case_id)
        parent = db.get(User, r.parent_user_id)
        out.append(serialize_request(r, case=case, parent=parent))
    return out


def serialize_request(
    row: ParentMeetingRequest,
    *,
    case: Case | None = None,
    parent: User | None = None,
) -> dict[str, Any]:
    return {
        "id": row.id,
        "case_id": row.case_id,
        "case_code": case.case_code if case else None,
        "child_name": case.child.full_name if case and case.child else None,
        "parent_name": parent.full_name if parent else None,
        "therapist_user_id": row.therapist_user_id,
        "requested_date": row.requested_date.isoformat(),
        "status": row.status.value,
        "note": row.note,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def fulfill_pending_for_case_date(
    db: Session,
    *,
    case_id: int,
    therapist_user_id: int,
    booked_date: date,
) -> int:
    rows = db.scalars(
        select(ParentMeetingRequest).where(
            ParentMeetingRequest.case_id == case_id,
            ParentMeetingRequest.therapist_user_id == therapist_user_id,
            ParentMeetingRequest.requested_date == booked_date,
            ParentMeetingRequest.status == ParentMeetingRequestStatus.PENDING,
        )
    ).all()
    for row in rows:
        row.status = ParentMeetingRequestStatus.FULFILLED
    if rows:
        db.flush()
    return len(rows)


def dismiss_request(db: Session, therapist_user_id: int, request_id: int) -> dict[str, Any]:
    row = db.get(ParentMeetingRequest, request_id)
    if not row or row.therapist_user_id != therapist_user_id:
        raise ValueError("Meeting request not found")
    if row.status != ParentMeetingRequestStatus.PENDING:
        raise ValueError("This request is already closed")
    row.status = ParentMeetingRequestStatus.DISMISSED
    db.flush()
    case = db.get(Case, row.case_id)
    parent = db.get(User, row.parent_user_id)
    return serialize_request(row, case=case, parent=parent)


def next_open_slot_summary(
    db: Session,
    case_id: int,
    therapist_user_id: int,
    parent_user_id: int,
    *,
    horizon_days: int = 7,
) -> dict[str, Any]:
    slot = find_next_open_parent_slot(
        db,
        case_id,
        therapist_user_id,
        parent_user_id,
        horizon_days=horizon_days,
    )
    return {"horizon_days": horizon_days, "next_slot": slot}
