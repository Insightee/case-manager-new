from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.permissions import RoleName, case_scope_check, user_has_permission
from app.models.case import BillingType, Case
from app.models.leave import LeaveBillingCategory, LeaveStatus, LeaveType, TherapistLeave
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.session_absence import SessionAbsenceRequest, SessionAbsenceStatus, SessionAbsenceType
from app.models.user import User
from app.services import billing_ledger_service, notification_service, parent_service
from app.services import leave_notification_service as leave_notify


def _user_name(db: Session, user_id: int | None) -> str | None:
    if not user_id:
        return None
    u = db.get(User, user_id)
    if not u:
        return None
    return u.full_name or u.email


def _serialize(db: Session, row: SessionAbsenceRequest) -> dict:
    session = row.session or db.get(TherapySession, row.session_id)
    case = row.case or db.get(Case, row.case_id)
    child_name = case.child.full_name if case and case.child else None
    return {
        "id": row.id,
        "session_id": row.session_id,
        "case_id": row.case_id,
        "case_code": case.case_code if case else None,
        "child_name": child_name,
        "therapist_user_id": row.therapist_user_id,
        "therapist_name": _user_name(db, row.therapist_user_id),
        "absence_type": row.absence_type.value,
        "status": row.status.value,
        "reason": row.reason,
        "notes": row.notes,
        "leave_billing_category": row.leave_billing_category,
        "requested_by_user_id": row.requested_by_user_id,
        "reviewed_by_user_id": row.reviewed_by_user_id,
        "review_note": row.review_note,
        "billing_outcome": row.billing_outcome,
        "scheduled_date": session.scheduled_date.isoformat() if session else None,
        "start_time": str(session.start_time) if session and session.start_time else None,
        "end_time": str(session.end_time) if session and session.end_time else None,
        "created_at": row.created_at,
        "reviewed_at": row.reviewed_at,
    }


def _parent_can_review(db: Session, user: User, case_id: int) -> bool:
    if RoleName.PARENT.value not in user.role_names:
        return False
    return parent_service.get_parent_case(db, user, case_id) is not None


def _admin_can_review(user: User) -> bool:
    return user_has_permission(user, "leave.manage") or user_has_permission(user, "case.read.all")


def _can_review(db: Session, user: User, row: SessionAbsenceRequest) -> bool:
    if row.absence_type == SessionAbsenceType.CLIENT_ABSENT:
        return _parent_can_review(db, user, row.case_id) or _admin_can_review(user)
    return _admin_can_review(user)


def _notify_on_submit(db: Session, row: SessionAbsenceRequest, therapist: User) -> None:
    case = db.get(Case, row.case_id)
    child = case.child.full_name if case and case.child else "your child"
    date_label = row.session.scheduled_date.isoformat() if row.session else ""
    if row.absence_type == SessionAbsenceType.CLIENT_ABSENT:
        title = "Child absence approval needed"
        body = f"{therapist.full_name or 'Therapist'} reported {child} absent for {date_label}. Please review."
        for parent_id in leave_notify._parents_for_case(db, row.case_id):
            notification_service.create_notification(
                db,
                user_id=parent_id,
                title=title,
                body=body,
                entity_type="session_absence",
                entity_id=row.id,
            )
        if case and case.case_manager_user_id:
            notification_service.create_notification(
                db,
                user_id=case.case_manager_user_id,
                title=title,
                body=body,
                entity_type="session_absence",
                entity_id=row.id,
            )
    else:
        title = "Therapist leave approval needed"
        body = f"{therapist.full_name or 'Therapist'} requested leave for {date_label}."
        from sqlalchemy import select as sa_select

        from app.models.role import Role, user_roles

        admins = db.scalars(
            sa_select(User)
            .join(user_roles, user_roles.c.user_id == User.id)
            .join(Role, Role.id == user_roles.c.role_id)
            .where(Role.name.in_(("SUPER_ADMIN", "ADMIN", "HR")))
        ).all()
        for admin in admins:
            if user_has_permission(admin, "leave.manage"):
                notification_service.create_notification(
                    db,
                    user_id=admin.id,
                    title=title,
                    body=body,
                    entity_type="session_absence",
                    entity_id=row.id,
                )


def _apply_billing(db: Session, session: TherapySession, case: Case, absence_type: SessionAbsenceType) -> str:
    product = (case.product_module or "").strip().lower()
    if absence_type == SessionAbsenceType.THERAPIST_LEAVE:
        session.status = SessionStatus.THERAPIST_LEAVE
        ledger = billing_ledger_service.sync_session_status(db, session)
        outcome = {"session_status": session.status.value, "event": "THERAPIST_LEAVE"}
        if ledger:
            outcome["ledger_event"] = ledger.event_type.value
            outcome["billable_status"] = ledger.billable_status.value
        return json.dumps(outcome)

    session.status = SessionStatus.CLIENT_ABSENT
    if case.billing_type == BillingType.PACKAGE:
        ledger = billing_ledger_service.consume_package_session(db, case_id=case.id, session=session)
        outcome = {"session_status": session.status.value, "package_consumed": True}
        if ledger:
            outcome["ledger_id"] = ledger.id
        return json.dumps(outcome)

    if product == "shadow_support":
        from app.models.ledger_billing import BillableStatus, LedgerEventType

        ledger = billing_ledger_service.upsert_from_session_event(
            db,
            session,
            event_type=LedgerEventType.CLIENT_NO_SHOW,
            billable_default=BillableStatus.NON_BILLABLE,
        )
        outcome = {"session_status": session.status.value, "shadow_non_billable": True}
        if ledger:
            outcome["billable_status"] = ledger.billable_status.value
        return json.dumps(outcome)

    ledger = billing_ledger_service.sync_session_status(db, session)
    outcome = {"session_status": session.status.value, "per_session_not_billed": True}
    if ledger:
        outcome["billable_status"] = ledger.billable_status.value
    return json.dumps(outcome)


def create_request(
    db: Session,
    user: User,
    session_id: int,
    *,
    absence_type: str,
    reason: str | None = None,
    notes: str | None = None,
    leave_billing_category: str | None = None,
) -> dict:
    session = db.scalars(
        select(TherapySession)
        .where(TherapySession.id == session_id)
        .options(selectinload(TherapySession.case).selectinload(Case.child))
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.therapist_user_id != user.id:
        raise HTTPException(status_code=403, detail="Can only mark absence on your own sessions")
    case = session.case
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=403, detail="Access denied")
    if session.status not in (SessionStatus.SCHEDULED, SessionStatus.IN_PROGRESS):
        raise HTTPException(status_code=400, detail="Session cannot be marked absent in its current state")

    try:
        atype = SessionAbsenceType(absence_type.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid absence_type") from None

    existing = db.scalars(
        select(SessionAbsenceRequest).where(
            SessionAbsenceRequest.session_id == session_id,
            SessionAbsenceRequest.status == SessionAbsenceStatus.PENDING_APPROVAL,
        )
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="A pending absence request already exists for this session")

    row = SessionAbsenceRequest(
        session_id=session.id,
        case_id=session.case_id,
        therapist_user_id=session.therapist_user_id,
        absence_type=atype,
        status=SessionAbsenceStatus.PENDING_APPROVAL,
        reason=(reason or "").strip() or None,
        notes=(notes or "").strip() or None,
        leave_billing_category=(leave_billing_category or "").strip().upper() or None,
        requested_by_user_id=user.id,
    )
    row.session = session
    db.add(row)
    db.flush()

    if atype == SessionAbsenceType.THERAPIST_LEAVE:
        billing_cat = LeaveBillingCategory.UNPAID
        if row.leave_billing_category:
            try:
                billing_cat = LeaveBillingCategory(row.leave_billing_category)
            except ValueError:
                pass
        leave = TherapistLeave(
            therapist_user_id=user.id,
            leave_type=LeaveType.CASUAL,
            service_line=(case.product_module or "homecare").strip().lower(),
            billing_category=billing_cat,
            case_id=case.id,
            start_date=session.scheduled_date,
            end_date=session.scheduled_date,
            reason=row.reason or row.notes,
        )
        db.add(leave)
        db.flush()
        row.therapist_leave_id = leave.id
        leave_notify.notify_leave_submitted(db, leave, user)

    _notify_on_submit(db, row, user)
    db.refresh(row)
    return _serialize(db, row)


def list_pending_for_parent(db: Session, user: User) -> list[dict]:
    case_ids = [
        c["id"]
        for c in parent_service.list_parent_cases(db, user)
    ]
    if not case_ids:
        return []
    rows = db.scalars(
        select(SessionAbsenceRequest)
        .where(
            SessionAbsenceRequest.case_id.in_(case_ids),
            SessionAbsenceRequest.status == SessionAbsenceStatus.PENDING_APPROVAL,
            SessionAbsenceRequest.absence_type == SessionAbsenceType.CLIENT_ABSENT,
        )
        .options(
            selectinload(SessionAbsenceRequest.session),
            selectinload(SessionAbsenceRequest.case).selectinload(Case.child),
        )
        .order_by(SessionAbsenceRequest.created_at.desc())
    ).all()
    return [_serialize(db, r) for r in rows]


def list_pending_for_admin(db: Session, user: User) -> list[dict]:
    if not _admin_can_review(user):
        raise HTTPException(status_code=403, detail="Access denied")
    rows = db.scalars(
        select(SessionAbsenceRequest)
        .where(SessionAbsenceRequest.status == SessionAbsenceStatus.PENDING_APPROVAL)
        .options(
            selectinload(SessionAbsenceRequest.session),
            selectinload(SessionAbsenceRequest.case).selectinload(Case.child),
        )
        .order_by(SessionAbsenceRequest.created_at.desc())
        .limit(100)
    ).all()
    return [_serialize(db, r) for r in rows]


def approve_request(db: Session, user: User, request_id: int, *, review_note: str | None = None) -> dict:
    row = db.scalars(
        select(SessionAbsenceRequest)
        .where(SessionAbsenceRequest.id == request_id)
        .options(
            selectinload(SessionAbsenceRequest.session),
            selectinload(SessionAbsenceRequest.case).selectinload(Case.child),
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Absence request not found")
    if row.status != SessionAbsenceStatus.PENDING_APPROVAL:
        raise HTTPException(status_code=400, detail="Request is not pending approval")
    if not _can_review(db, user, row):
        raise HTTPException(status_code=403, detail="Cannot approve this request")

    session = row.session
    case = row.case
    if not session or not case:
        raise HTTPException(status_code=400, detail="Linked session or case missing")

    row.status = SessionAbsenceStatus.APPROVED
    row.reviewed_by_user_id = user.id
    row.review_note = (review_note or "").strip() or None
    row.reviewed_at = datetime.now(timezone.utc)
    row.billing_outcome = _apply_billing(db, session, case, row.absence_type)

    if row.therapist_leave_id:
        leave = db.get(TherapistLeave, row.therapist_leave_id)
        if leave and leave.status == LeaveStatus.PENDING:
            leave.status = LeaveStatus.APPROVED
            leave.reviewed_by_user_id = user.id

    therapist = db.get(User, row.therapist_user_id)
    if therapist:
        notification_service.create_notification(
            db,
            user_id=therapist.id,
            title="Absence request approved",
            body=f"Your {row.absence_type.value.replace('_', ' ').lower()} for {session.scheduled_date} was approved.",
            entity_type="session_absence",
            entity_id=row.id,
        )

    db.flush()
    return _serialize(db, row)


def reject_request(db: Session, user: User, request_id: int, *, review_note: str | None = None) -> dict:
    row = db.scalars(
        select(SessionAbsenceRequest)
        .where(SessionAbsenceRequest.id == request_id)
        .options(selectinload(SessionAbsenceRequest.session))
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Absence request not found")
    if row.status != SessionAbsenceStatus.PENDING_APPROVAL:
        raise HTTPException(status_code=400, detail="Request is not pending approval")
    if not _can_review(db, user, row):
        raise HTTPException(status_code=403, detail="Cannot reject this request")

    row.status = SessionAbsenceStatus.REJECTED
    row.reviewed_by_user_id = user.id
    row.review_note = (review_note or "").strip() or None
    row.reviewed_at = datetime.now(timezone.utc)

    if row.therapist_leave_id:
        leave = db.get(TherapistLeave, row.therapist_leave_id)
        if leave and leave.status == LeaveStatus.PENDING:
            leave.status = LeaveStatus.REJECTED
            leave.reviewed_by_user_id = user.id
            leave.review_note = row.review_note

    therapist = db.get(User, row.therapist_user_id)
    if therapist:
        notification_service.create_notification(
            db,
            user_id=therapist.id,
            title="Absence request declined",
            body=row.review_note or "Your absence request was not approved.",
            entity_type="session_absence",
            entity_id=row.id,
        )

    db.flush()
    return _serialize(db, row)
