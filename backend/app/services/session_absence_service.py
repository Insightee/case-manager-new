from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.permissions import case_scope_check, is_finance_desk_user, user_has_permission
from app.models.case import BillingType, Case
from app.models.leave import LeaveBillingCategory, LeaveStatus, LeaveType, TherapistLeave
from app.core.session_defaults import default_session_mode_for_case
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.session_absence import SessionAbsenceRequest, SessionAbsenceStatus, SessionAbsenceType
from app.models.user import User
from app.services import billing_ledger_service, notification_service, parent_service
from app.services import leave_migration_service as leave_migration
from app.services import leave_notification_service as leave_notify

PENDING_CHILD_ABSENCE_MESSAGE = (
    "You have applied for child absence — session cannot be started."
)
APPROVED_CHILD_ABSENCE_MESSAGE = "The child was marked absent on this day."
PENDING_CHILD_ABSENCE_LOG_MESSAGE = (
    "You have applied for child absence — a session log cannot be added for this day."
)
PARENT_ABSENCE_DASHBOARD_DAYS = 7


class ChildAbsenceBlockError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


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
    session_date = session.scheduled_date if session else None
    is_retro = bool(session_date and leave_migration.is_retroactive_absence(session_date))
    is_reentry = bool(session_date and leave_migration.is_migration_absence_reentry(session_date))
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
        "scheduled_date": session_date.isoformat() if session_date else None,
        "start_time": str(session.start_time) if session and session.start_time else None,
        "end_time": str(session.end_time) if session and session.end_time else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "is_retroactive": is_retro,
        "is_migration_reentry": is_reentry,
    }


def has_blocking_absence_for_session(db: Session, session_id: int) -> bool:
    """True when an active absence claim should block void/cancel flows (not historical rejections)."""
    row = db.scalars(
        select(SessionAbsenceRequest).where(
            SessionAbsenceRequest.session_id == session_id,
            SessionAbsenceRequest.status.in_(
                (SessionAbsenceStatus.PENDING_APPROVAL, SessionAbsenceStatus.APPROVED)
            ),
        )
    ).first()
    return row is not None


def get_child_absence_block(db: Session, session_id: int, *, for_manual_log: bool = False) -> dict | None:
    """Return {code, message} when child absence should block start or manual log, else None."""
    session = db.get(TherapySession, session_id)
    if not session:
        return None
    if session.status == SessionStatus.CLIENT_ABSENT:
        return {"code": "CHILD_MARKED_ABSENT", "message": APPROVED_CHILD_ABSENCE_MESSAGE}

    row = db.scalars(
        select(SessionAbsenceRequest)
        .where(
            SessionAbsenceRequest.session_id == session_id,
            SessionAbsenceRequest.absence_type == SessionAbsenceType.CLIENT_ABSENT,
            SessionAbsenceRequest.status.in_(
                (SessionAbsenceStatus.PENDING_APPROVAL, SessionAbsenceStatus.APPROVED)
            ),
        )
        .order_by(SessionAbsenceRequest.created_at.desc())
    ).first()
    if not row:
        return None
    if row.status == SessionAbsenceStatus.APPROVED:
        return {"code": "CHILD_MARKED_ABSENT", "message": APPROVED_CHILD_ABSENCE_MESSAGE}
    message = (
        PENDING_CHILD_ABSENCE_LOG_MESSAGE
        if for_manual_log
        else PENDING_CHILD_ABSENCE_MESSAGE
    )
    return {"code": "PENDING_CHILD_ABSENCE", "message": message}


def assert_may_start_session(db: Session, session: TherapySession) -> None:
    block = get_child_absence_block(db, session.id)
    if block:
        raise ChildAbsenceBlockError(block["code"], block["message"])


def child_absence_calendar_status(db: Session, session_id: int | None) -> str | None:
    """Calendar flag: 'pending' | 'approved' for child absence, else None."""
    if not session_id:
        return None
    block = get_child_absence_block(db, session_id)
    if not block:
        return None
    if block["code"] == "CHILD_MARKED_ABSENT":
        return "approved"
    return "pending"


def _admin_can_review(user: User) -> bool:
    return user_has_permission(user, "leave.manage") or user_has_permission(user, "case.read.all")


def _can_review(db: Session, user: User, row: SessionAbsenceRequest) -> bool:
    if is_finance_desk_user(user) and not user_has_permission(user, "leave.manage"):
        return False
    return _admin_can_review(user)


def _absence_status_for_leave_ui(status: SessionAbsenceStatus) -> str:
    if status == SessionAbsenceStatus.PENDING_APPROVAL:
        return "PENDING"
    return status.value


def _notify_staff_on_submit(db: Session, row: SessionAbsenceRequest, therapist: User) -> None:
    from sqlalchemy import select as sa_select

    from app.models.role import Role, user_roles

    case = db.get(Case, row.case_id)
    child = case.child.full_name if case and case.child else "your child"
    date_label = row.session.scheduled_date.isoformat() if row.session else ""
    if row.absence_type == SessionAbsenceType.CLIENT_ABSENT:
        title = "Child absence approval needed"
        body = f"{therapist.full_name or 'Therapist'} reported {child} absent for {date_label}. Please review."
        if leave_migration.is_migration_absence_reentry(
            row.session.scheduled_date if row.session else date.today()
        ):
            body += (
                " Previous absence — approving records it for billing; "
                "visit times were not changed."
            )
    else:
        title = "Therapist leave approval needed"
        body = f"{therapist.full_name or 'Therapist'} requested leave for {date_label}."

    if case and case.case_manager_user_id:
        notification_service.create_notification(
            db,
            user_id=case.case_manager_user_id,
            title=title,
            body=body,
            entity_type="session_absence",
            entity_id=row.id,
        )

    admins = db.scalars(
        sa_select(User)
        .join(user_roles, user_roles.c.user_id == User.id)
        .join(Role, Role.id == user_roles.c.role_id)
        .where(Role.name.in_(("SUPER_ADMIN", "ADMIN", "HR", "CASE_MANAGER")))
    ).all()
    notified_ids: set[int] = set()
    for admin in admins:
        if admin.id in notified_ids:
            continue
        if user_has_permission(admin, "leave.manage") or user_has_permission(admin, "case.read.all"):
            notification_service.create_notification(
                db,
                user_id=admin.id,
                title=title,
                body=body,
                entity_type="session_absence",
                entity_id=row.id,
            )
            notified_ids.add(admin.id)


def _notify_parents_on_child_absence_approved(
    db: Session,
    row: SessionAbsenceRequest,
    session: TherapySession,
) -> None:
    case = row.case or db.get(Case, row.case_id)
    child = case.child.full_name if case and case.child else "your child"
    date_label = session.scheduled_date.isoformat()
    title = "Child marked absent"
    body = f"{child} was marked absent for the session on {date_label}."
    for parent_id in leave_notify._parents_for_case(db, row.case_id):
        notification_service.create_notification(
            db,
            user_id=parent_id,
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


def get_absence_for_session(db: Session, user: User, session_id: int) -> dict:
    session = db.get(TherapySession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.therapist_user_id != user.id:
        raise HTTPException(status_code=403, detail="Can only view absence on your own sessions")
    case = session.case
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=403, detail="Access denied")

    row = db.scalars(
        select(SessionAbsenceRequest)
        .where(SessionAbsenceRequest.session_id == session_id)
        .order_by(SessionAbsenceRequest.created_at.desc())
    ).first()
    if not row:
        return {"status": "none", "message": None, "absence_request": None}

    serialized = _serialize(db, row)
    status_key = row.status.value.lower()
    if row.status == SessionAbsenceStatus.PENDING_APPROVAL:
        status_key = "pending"
    return {
        "status": status_key,
        "message": None,
        "absence_request": serialized,
    }


def _ensure_session_for_child_absence(
    db: Session,
    user: User,
    case: Case,
    scheduled_date: date,
    *,
    start_time: time | None = None,
    end_time: time | None = None,
) -> TherapySession:
    from app.services import manual_session_conflict_service as manual_conflict

    existing = manual_conflict.find_existing_session_for_date(
        db,
        case_id=case.id,
        therapist_user_id=user.id,
        scheduled_date=scheduled_date,
    )
    if existing:
        if existing.status == SessionStatus.CLIENT_ABSENT:
            raise HTTPException(status_code=400, detail="Child was already marked absent for this day.")
        if existing.status == SessionStatus.COMPLETED and existing.daily_log is not None:
            raise HTTPException(
                status_code=400,
                detail="This day already has a completed session log — contact your case manager if you need a correction.",
            )
        if existing.status not in (SessionStatus.SCHEDULED, SessionStatus.IN_PROGRESS):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot log child absence — session is "
                    f"{existing.status.value.lower().replace('_', ' ')}."
                ),
            )
        if start_time and existing.start_time != start_time:
            existing.start_time = start_time
        if end_time and existing.end_time != end_time:
            existing.end_time = end_time
        return existing

    session = TherapySession(
        case_id=case.id,
        therapist_user_id=user.id,
        scheduled_date=scheduled_date,
        start_time=start_time or time(9, 0),
        end_time=end_time or time(10, 0),
        mode=default_session_mode_for_case(case),
        status=SessionStatus.SCHEDULED,
    )
    db.add(session)
    db.flush()
    return session


def create_child_absence_backfill(
    db: Session,
    user: User,
    *,
    case_id: int,
    scheduled_date: date,
    reason: str | None = None,
    notes: str | None = None,
    start_time: time | None = None,
    end_time: time | None = None,
) -> dict:
    try:
        leave_migration.validate_child_absence_date(scheduled_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    case = db.scalars(
        select(Case).where(Case.id == case_id).options(selectinload(Case.child))
    ).first()
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Case not found")

    from app.services.case_status_request_service import assert_case_allows_new_session

    try:
        assert_case_allows_new_session(db, case_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    session = _ensure_session_for_child_absence(
        db,
        user,
        case,
        scheduled_date,
        start_time=start_time,
        end_time=end_time,
    )
    return create_request(
        db,
        user,
        session.id,
        absence_type=SessionAbsenceType.CLIENT_ABSENT.value,
        reason=reason,
        notes=notes,
    )


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

    if atype == SessionAbsenceType.CLIENT_ABSENT:
        try:
            leave_migration.validate_child_absence_date(session.scheduled_date)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    existing = db.scalars(
        select(SessionAbsenceRequest).where(
            SessionAbsenceRequest.session_id == session_id,
            SessionAbsenceRequest.status == SessionAbsenceStatus.PENDING_APPROVAL,
        )
    ).first()
    if existing:
        serialized = _serialize(db, existing)
        raise HTTPException(
            status_code=409,
            detail={
                "status": "pending",
                "message": "Child absence already submitted for this session.",
                "existing": True,
                "absence_request": serialized,
            },
        )

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
        # Check for an existing leave that already covers this therapist+date to avoid
        # creating duplicate leave rows when the same absence is submitted more than once.
        from app.services.leave_service import _leave_scopes_conflict

        existing_leave = db.scalars(
            select(TherapistLeave).where(
                TherapistLeave.therapist_user_id == user.id,
                TherapistLeave.status.in_([LeaveStatus.PENDING, LeaveStatus.APPROVED]),
                TherapistLeave.start_date <= session.scheduled_date,
                TherapistLeave.end_date >= session.scheduled_date,
            )
        ).first()

        if existing_leave and _leave_scopes_conflict(existing_leave, [case.id]):
            row.therapist_leave_id = existing_leave.id
        else:
            leave = TherapistLeave(
                therapist_user_id=user.id,
                leave_type=LeaveType.CASUAL,
                service_line=(case.product_module or "unknown").strip().lower(),
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

    _notify_staff_on_submit(db, row, user)
    db.refresh(row)
    return _serialize(db, row)


def _dispute_status_for_session(db: Session, session_id: int) -> str | None:
    from app.models.support_ticket import SupportTicket, TicketStatus

    ticket = db.scalars(
        select(SupportTicket).where(
            SupportTicket.disputed_session_id == session_id,
            SupportTicket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS]),
        )
    ).first()
    return "DISPUTED" if ticket else None


def list_approved_absence_notifications_for_parent(db: Session, user: User) -> list[dict]:
    """Approved child absences for the parent dashboard (recent window + open disputes)."""
    from app.models.support_ticket import SupportTicket, TicketStatus

    case_ids = [c["id"] for c in parent_service.list_parent_cases(db, user)]
    if not case_ids:
        return []
    cutoff = date.today() - timedelta(days=PARENT_ABSENCE_DASHBOARD_DAYS)
    disputed_session_ids = select(SupportTicket.disputed_session_id).where(
        SupportTicket.disputed_session_id.is_not(None),
        SupportTicket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS]),
    )
    rows = db.scalars(
        select(SessionAbsenceRequest)
        .join(TherapySession, SessionAbsenceRequest.session_id == TherapySession.id)
        .where(
            SessionAbsenceRequest.case_id.in_(case_ids),
            SessionAbsenceRequest.status == SessionAbsenceStatus.APPROVED,
            SessionAbsenceRequest.absence_type == SessionAbsenceType.CLIENT_ABSENT,
            or_(
                TherapySession.scheduled_date >= cutoff,
                SessionAbsenceRequest.session_id.in_(disputed_session_ids),
            ),
        )
        .options(
            selectinload(SessionAbsenceRequest.session),
            selectinload(SessionAbsenceRequest.case).selectinload(Case.child),
        )
        .order_by(SessionAbsenceRequest.reviewed_at.desc(), SessionAbsenceRequest.created_at.desc())
        .limit(50)
    ).all()
    items: list[dict] = []
    for row in rows:
        payload = _serialize(db, row)
        payload["dispute_status"] = _dispute_status_for_session(db, row.session_id)
        items.append(payload)
    return items


def list_pending_for_parent(db: Session, user: User) -> list[dict]:
    """Backward-compatible alias — parents receive approved absences only."""
    return list_approved_absence_notifications_for_parent(db, user)


def list_child_absence_for_admin(db: Session, user: User) -> list[dict]:
    if not _admin_can_review(user):
        raise HTTPException(status_code=403, detail="Access denied")
    rows = db.scalars(
        select(SessionAbsenceRequest)
        .where(SessionAbsenceRequest.absence_type == SessionAbsenceType.CLIENT_ABSENT)
        .options(
            selectinload(SessionAbsenceRequest.session),
            selectinload(SessionAbsenceRequest.case).selectinload(Case.child),
        )
        .order_by(SessionAbsenceRequest.created_at.desc())
        .limit(200)
    ).all()
    items: list[dict] = []
    for row in rows:
        payload = _serialize(db, row)
        payload["record_type"] = "child_absence"
        payload["leave_status"] = _absence_status_for_leave_ui(row.status)
        items.append(payload)
    return items


def list_pending_for_admin(db: Session, user: User) -> list[dict]:
    if is_finance_desk_user(user) and not user_has_permission(user, "leave.manage"):
        raise HTTPException(status_code=403, detail="Access denied")
    if not _admin_can_review(user):
        raise HTTPException(status_code=403, detail="Access denied")
    rows = db.scalars(
        select(SessionAbsenceRequest)
        .where(
            SessionAbsenceRequest.status == SessionAbsenceStatus.PENDING_APPROVAL,
            SessionAbsenceRequest.absence_type == SessionAbsenceType.THERAPIST_LEAVE,
        )
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

    if row.absence_type == SessionAbsenceType.CLIENT_ABSENT:
        _notify_parents_on_child_absence_approved(db, row, session)

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

    # Restore session status — but only when safe (no downstream billing/log/report).
    session = row.session or (db.get(TherapySession, row.session_id) if row.session_id else None)
    if session and session.status in (SessionStatus.CLIENT_ABSENT, SessionStatus.THERAPIST_LEAVE):
        from app.models.ledger_billing import BillingLedger
        from app.models.daily_log import DailyLog
        from app.models.report import MonthlyReport

        has_ledger = db.scalars(
            select(BillingLedger).where(BillingLedger.session_id == session.id)
        ).first()
        has_log = db.scalars(
            select(DailyLog).where(DailyLog.session_id == session.id)
        ).first()
        has_report = db.scalars(
            select(MonthlyReport).where(
                MonthlyReport.case_id == session.case_id,
                MonthlyReport.status.in_(["APPROVED", "SUBMITTED"]),
            )
        ).first()

        if has_ledger or has_log or has_report:
            session.data_quality_flag = "NEEDS_REVIEW_AFTER_REJECTION"
        else:
            session.status = SessionStatus.SCHEDULED
            session.data_quality_flag = None

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
