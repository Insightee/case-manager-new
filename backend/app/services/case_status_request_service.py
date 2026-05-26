from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case, CaseStatus
from app.models.case_status_request import CaseStatusRequest, CaseStatusRequestStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.slot import SlotStatus, TherapistSlot
from app.models.user import User
from app.services import notification_service

THERAPIST_ALLOWED = {
    (CaseStatus.ACTIVE.value, CaseStatus.SUSPENDED.value),
    (CaseStatus.ACTIVE.value, CaseStatus.CLOSED.value),
    (CaseStatus.SUSPENDED.value, CaseStatus.ACTIVE.value),
}


def create_request(db: Session, user: User, case: Case, to_status: str, reason: str) -> CaseStatusRequest:
    from_status = case.status.value if hasattr(case.status, "value") else str(case.status)
    to_status = to_status.upper()
    if (from_status, to_status) not in THERAPIST_ALLOWED:
        raise ValueError("This status change requires admin approval via a different path")
    if not reason.strip():
        raise ValueError("Reason is required")
    pending = db.scalars(
        select(CaseStatusRequest).where(
            CaseStatusRequest.case_id == case.id,
            CaseStatusRequest.status == CaseStatusRequestStatus.PENDING,
        )
    ).first()
    if pending:
        raise ValueError("A status change request is already pending for this case")
    req = CaseStatusRequest(
        case_id=case.id,
        requested_by_user_id=user.id,
        from_status=from_status,
        to_status=to_status,
        reason=reason.strip(),
    )
    db.add(req)
    db.flush()
    if case.case_manager_user_id:
        notification_service.create_notification(
            db,
            user_id=case.case_manager_user_id,
            title="Case status change requested",
            body=f"{case.case_code}: {from_status} → {to_status}",
            entity_type="case_status_request",
            entity_id=req.id,
        )
    return req


def get_pending_for_case(db: Session, case_id: int) -> CaseStatusRequest | None:
    return db.scalars(
        select(CaseStatusRequest).where(
            CaseStatusRequest.case_id == case_id,
            CaseStatusRequest.status == CaseStatusRequestStatus.PENDING,
        )
    ).first()


def assert_case_allows_new_session(db: Session, case_id: int) -> None:
    pending = get_pending_for_case(db, case_id)
    if not pending:
        return
    if pending.to_status in (CaseStatus.SUSPENDED.value, CaseStatus.CLOSED.value):
        raise ValueError(
            "A pause or close request is pending admin approval — you cannot start a new session until it is reviewed"
        )


def list_for_case(db: Session, case_id: int, limit: int = 10) -> list[dict]:
    rows = db.scalars(
        select(CaseStatusRequest)
        .where(CaseStatusRequest.case_id == case_id)
        .order_by(CaseStatusRequest.created_at.desc())
        .limit(limit)
    ).all()
    out = []
    for r in rows:
        requester = db.get(User, r.requested_by_user_id)
        out.append(
            {
                "id": r.id,
                "fromStatus": r.from_status,
                "toStatus": r.to_status,
                "reason": r.reason,
                "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                "requestedBy": requester.full_name if requester else None,
                "createdAt": r.created_at.isoformat() if r.created_at else None,
                "reviewedAt": r.reviewed_at.isoformat() if r.reviewed_at else None,
                "reviewNote": r.review_note,
            }
        )
    return out


def _cancel_future_bookings(db: Session, case_id: int) -> None:
    today = date.today()
    slots = db.scalars(
        select(TherapistSlot).where(
            TherapistSlot.case_id == case_id,
            TherapistSlot.status == SlotStatus.BOOKED,
            TherapistSlot.slot_date >= today,
        )
    ).all()
    for slot in slots:
        slot.status = SlotStatus.CANCELLED
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


def list_pending(db: Session, limit: int = 50) -> list[dict]:
    rows = db.scalars(
        select(CaseStatusRequest)
        .where(CaseStatusRequest.status == CaseStatusRequestStatus.PENDING)
        .order_by(CaseStatusRequest.created_at.desc())
        .limit(limit)
    ).all()
    result = []
    for r in rows:
        case = db.get(Case, r.case_id)
        requester = db.get(User, r.requested_by_user_id)
        result.append(
            {
                "id": r.id,
                "caseId": case.case_code if case else "",
                "caseDbId": r.case_id,
                "productModule": case.product_module if case else None,
                "childName": case.child.full_name if case and case.child else "",
                "fromStatus": r.from_status,
                "toStatus": r.to_status,
                "reason": r.reason,
                "requestedBy": requester.full_name if requester else "",
                "createdAt": r.created_at.isoformat() if r.created_at else None,
            }
        )
    return result


def approve_request(db: Session, request_id: int, admin_user: User, note: str | None = None) -> Case:
    req = db.get(CaseStatusRequest, request_id)
    if not req or req.status != CaseStatusRequestStatus.PENDING:
        raise ValueError("Request not found")
    case = db.get(Case, req.case_id)
    if not case:
        raise ValueError("Case not found")
    case.status = CaseStatus(req.to_status)
    if req.to_status in (CaseStatus.SUSPENDED.value, CaseStatus.CLOSED.value):
        _cancel_future_bookings(db, case.id)
    req.status = CaseStatusRequestStatus.APPROVED
    req.reviewed_by_user_id = admin_user.id
    req.review_note = (note or "").strip() or None
    req.reviewed_at = datetime.now(timezone.utc)
    notification_service.create_notification(
        db,
        user_id=req.requested_by_user_id,
        title="Status change approved",
        body=f"{case.case_code} is now {req.to_status}",
        entity_type="case",
        entity_id=case.id,
    )
    db.flush()
    return case


def reject_request(db: Session, request_id: int, admin_user: User, note: str) -> CaseStatusRequest:
    req = db.get(CaseStatusRequest, request_id)
    if not req or req.status != CaseStatusRequestStatus.PENDING:
        raise ValueError("Request not found")
    req.status = CaseStatusRequestStatus.REJECTED
    req.reviewed_by_user_id = admin_user.id
    req.review_note = note.strip()
    req.reviewed_at = datetime.now(timezone.utc)
    case = db.get(Case, req.case_id)
    if case:
        notification_service.create_notification(
            db,
            user_id=req.requested_by_user_id,
            title="Status change not approved",
            body=f"{case.case_code}: {req.review_note}",
            entity_type="case_status_request",
            entity_id=req.id,
        )
    db.flush()
    return req
