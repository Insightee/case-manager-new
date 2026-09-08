from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case, CaseStatus
from app.models.case_status_request import CaseStatusRequest, CaseStatusRequestStatus
from app.models.user import User
from app.services import notification_service
from app.services.case_close_service import (
    assert_no_blocking_invoices_for_close,
    cleanup_future_bookings,
)

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
    if to_status == CaseStatus.CLOSED.value:
        assert_no_blocking_invoices_for_close(db, case.id)
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
    """Delegate to canonical operational gate (DEC-02)."""
    from app.services.session_operational_gate_service import assert_case_allows_new_session as _assert

    _assert(db, case_id)


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
    if req.to_status == CaseStatus.CLOSED.value:
        assert_no_blocking_invoices_for_close(db, case.id)

    from app.services import client_status_service

    # Prefer the audited client-status path for close/reactivate so reason + date are stored.
    if req.to_status in (
        CaseStatus.CLOSED.value,
        CaseStatus.SUSPENDED.value,
        CaseStatus.ACTIVE.value,
    ):
        try:
            client_status_service.change_client_status(
                db,
                case=case,
                user=admin_user,
                new_status=req.to_status,
                effective_date=datetime.now(timezone.utc).date(),
                reason=req.reason or f"Approved status request #{req.id}",
                internal_notes=(note or "").strip() or None,
            )
        except ValueError:
            # Fallback for transitions not in ADMIN_ALLOWED_TRANSITIONS (e.g. therapist request edges).
            case.status = CaseStatus(req.to_status)
            if req.to_status == CaseStatus.CLOSED.value:
                from app.services.case_close_service import apply_case_closed_side_effects

                apply_case_closed_side_effects(db, case)
            elif req.to_status == CaseStatus.SUSPENDED.value:
                cleanup_future_bookings(db, case.id)
            case.status_effective_date = datetime.now(timezone.utc).date()
            case.status_reason = req.reason
            case.status_changed_by_user_id = admin_user.id
    else:
        case.status = CaseStatus(req.to_status)

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
