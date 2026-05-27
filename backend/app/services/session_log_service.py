from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.module_access import get_allowed_case_product_modules
from app.core.permissions import case_scope_check, user_has_permission
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.parent import ParentGuardian, parent_child_link
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.user import User
from app.models.visibility import VisibilityStatus
from app.services import case_service, log_service, notification_service
from app.services import parent_service

AdminLogStatus = Literal["missing", "pending", "submitted", "approved"]


def session_log_read(db: Session, log: DailyLog, *, status_label: str | None = None) -> dict:
    data = log_service.log_to_read(log)
    session = log.session
    case = session.case if session and getattr(session, "case", None) else None
    if session and not case:
        case = case_service.get_case(db, session.case_id)
    therapist_name = None
    if session:
        t = db.get(User, session.therapist_user_id)
        therapist_name = t.full_name if t else None
    data["external_case_ref"] = case.external_case_ref if case else None
    data["therapist_user_id"] = session.therapist_user_id if session else None
    data["therapist_name"] = therapist_name
    data["status"] = status_label
    data["parent_notified_at"] = log.parent_notified_at
    return data


def list_therapist_my_cases(db: Session, user: User) -> dict:
    data = case_service.list_cases_for_user(db, user, assigned_only=True, page=1, page_size=500)
    case_ids = [c["id"] for c in data["items"]]
    if not case_ids:
        return {"items": [], "total": 0}

    active_sessions = {
        row.case_id
        for row in db.scalars(
            select(TherapySession).where(
                TherapySession.case_id.in_(case_ids),
                TherapySession.therapist_user_id == user.id,
                TherapySession.status == SessionStatus.IN_PROGRESS,
            )
        ).all()
    }

    last_log_by_case: dict[int, str] = {}
    log_rows = db.execute(
        select(TherapySession.case_id, DailyLog.approval_status)
        .join(DailyLog, DailyLog.session_id == TherapySession.id)
        .where(TherapySession.case_id.in_(case_ids), TherapySession.therapist_user_id == user.id)
        .order_by(DailyLog.submitted_at.desc())
    ).all()
    for case_id, approval in log_rows:
        if case_id not in last_log_by_case:
            last_log_by_case[case_id] = approval.value if hasattr(approval, "value") else str(approval)

    items = []
    for row in data["items"]:
        items.append(
            {
                "case_id": row["id"],
                "case_code": row["case_code"],
                "external_case_ref": row.get("external_case_ref"),
                "child_id": row["child_id"],
                "child_name": row.get("child_name"),
                "product_module": row["product_module"],
                "service_type": row["service_type"],
                "status": row["status"].value if hasattr(row["status"], "value") else str(row["status"]),
                "has_active_session": row["id"] in active_sessions,
                "last_log_status": last_log_by_case.get(row["id"]),
            }
        )
    return {"items": items, "total": len(items)}


def create_therapist_session_log(db: Session, user: User, payload: dict) -> DailyLog:
    session = db.scalars(
        select(TherapySession)
        .where(TherapySession.id == payload["session_id"])
        .options(selectinload(TherapySession.case))
    ).first()
    if not session:
        raise ValueError("Session not found")
    if session.therapist_user_id != user.id:
        raise ValueError("Access denied")
    case = session.case or case_service.get_case(db, session.case_id)
    if not case or not case_scope_check(db, user, case):
        raise ValueError("Case access denied")
    log = log_service.create_daily_log(db, **payload)
    notify_case_managers_log_submitted(db, log, therapist=user)
    return log


def notify_case_managers_log_submitted(db: Session, log: DailyLog, *, therapist: User) -> int:
    """In-app alert to CM/supervisor when a therapist submits a session log (parent sees after CM approve)."""
    session = log.session or db.get(TherapySession, log.session_id)
    if not session:
        return 0
    case = session.case or case_service.get_case(db, session.case_id)
    if not case:
        return 0
    child_name = case.child.full_name if case.child else "client"
    title = f"Session log submitted — {case.case_code}"
    body = (
        f"{therapist.full_name or 'Therapist'} submitted a log for {child_name} "
        f"({session.scheduled_date.isoformat()}). Review and approve for parent visibility."
    )
    recipient_ids: set[int] = set()
    if case.case_manager_user_id:
        recipient_ids.add(case.case_manager_user_id)
    count = 0
    for uid in recipient_ids:
        if uid == therapist.id:
            continue
        notification_service.create_notification(
            db,
            user_id=uid,
            title=title,
            body=body,
            entity_type="daily_log",
            entity_id=log.id,
        )
        count += 1
    return count


def parent_user_ids_for_case(db: Session, case: Case) -> list[int]:
    if not case.child_id:
        return []
    rows = db.scalars(
        select(ParentGuardian.user_id)
        .join(parent_child_link, ParentGuardian.id == parent_child_link.c.parent_guardian_id)
        .where(parent_child_link.c.child_id == case.child_id)
    ).all()
    return list(dict.fromkeys(rows))


def notify_parents_session_log_approved(
    db: Session,
    log: DailyLog,
    *,
    send_email: bool = False,
) -> int:
    session = log.session or db.get(TherapySession, log.session_id)
    if not session:
        return 0
    case = session.case or case_service.get_case(db, session.case_id)
    if not case:
        return 0
    child_name = case.child.full_name if case.child else "your child"
    therapist_name = parent_service.active_therapist_name(db, case.id) or "your therapist"
    title = f"Session update for {child_name}"
    body = (
        f"A session log from {therapist_name} on {session.scheduled_date.isoformat()} "
        f"has been approved and is ready to view in the parent portal."
    )
    count = 0
    now = datetime.now(timezone.utc)
    for uid in parent_user_ids_for_case(db, case):
        notification_service.create_notification(
            db,
            user_id=uid,
            title=title,
            body=body,
            entity_type="daily_log",
            entity_id=log.id,
        )
        count += 1
    if count:
        log.parent_notified_at = now
    return count


def publish_log_to_parents(log: DailyLog) -> None:
    """Set visibility for parent portal after CM approval."""
    log.visibility_status = VisibilityStatus.APPROVED_FOR_PARENT


def _case_ids_for_admin(db: Session, user: User, product_module: str | None) -> list[int] | None:
    allowed = get_allowed_case_product_modules(user)
    stmt = select(Case.id)
    if allowed is not None:
        if not allowed:
            return []
        stmt = stmt.where(Case.product_module.in_(allowed))
    if product_module:
        stmt = stmt.where(Case.product_module == product_module)
    cases = db.scalars(stmt).all()
    if user_has_permission(user, "case.read.all") or user_has_permission(user, "admin.override"):
        return list(cases)
    scoped = []
    for cid in cases:
        case = case_service.get_case(db, cid)
        if case and case_scope_check(db, user, case):
            scoped.append(cid)
    return scoped


def list_admin_session_logs(
    db: Session,
    user: User,
    *,
    status: AdminLogStatus | None = None,
    case_id: int | None = None,
    therapist_user_id: int | None = None,
    product_module: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    case_ids = _case_ids_for_admin(db, user, product_module)
    if case_ids is not None and not case_ids:
        return {"items": [], "total": 0, "page": page, "page_size": page_size, "pages": 1}
    if case_id is not None:
        if case_ids is not None and case_id not in case_ids:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "pages": 1}
        case_ids = [case_id]

    if status == "missing":
        return _list_missing_logs(
            db,
            case_ids=case_ids,
            therapist_user_id=therapist_user_id,
            from_date=from_date,
            to_date=to_date,
            page=page,
            page_size=page_size,
        )

    stmt = (
        select(DailyLog)
        .join(TherapySession, DailyLog.session_id == TherapySession.id)
        .join(Case, TherapySession.case_id == Case.id)
        .options(
            selectinload(DailyLog.session).selectinload(TherapySession.case).selectinload(Case.child),
        )
        .order_by(DailyLog.submitted_at.desc().nullslast(), TherapySession.scheduled_date.desc())
    )
    if case_ids is not None:
        stmt = stmt.where(TherapySession.case_id.in_(case_ids))
    if therapist_user_id:
        stmt = stmt.where(TherapySession.therapist_user_id == therapist_user_id)
    if from_date:
        stmt = stmt.where(TherapySession.scheduled_date >= from_date)
    if to_date:
        stmt = stmt.where(TherapySession.scheduled_date <= to_date)

    if status in ("pending", "submitted"):
        stmt = stmt.where(
            DailyLog.submitted_at.isnot(None),
            DailyLog.approval_status == LogApprovalStatus.PENDING,
        )
        label = "pending"
    elif status == "approved":
        stmt = stmt.where(DailyLog.approval_status == LogApprovalStatus.APPROVED)
        label = "approved"
    else:
        label = None

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    offset = (page - 1) * page_size
    logs = db.scalars(stmt.offset(offset).limit(page_size)).all()
    items = [session_log_read(db, log, status_label=label) for log in logs]
    pages = max(1, (total + page_size - 1) // page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": pages}


def _list_missing_logs(
    db: Session,
    *,
    case_ids: list[int] | None,
    therapist_user_id: int | None,
    from_date: date | None,
    to_date: date | None,
    page: int,
    page_size: int,
) -> dict:
    stmt = (
        select(TherapySession)
        .outerjoin(DailyLog, DailyLog.session_id == TherapySession.id)
        .where(
            TherapySession.status == SessionStatus.COMPLETED,
            DailyLog.id.is_(None),
        )
        .options(selectinload(TherapySession.case).selectinload(Case.child))
        .order_by(TherapySession.scheduled_date.desc())
    )
    if case_ids is not None:
        stmt = stmt.where(TherapySession.case_id.in_(case_ids))
    if therapist_user_id:
        stmt = stmt.where(TherapySession.therapist_user_id == therapist_user_id)
    if from_date:
        stmt = stmt.where(TherapySession.scheduled_date >= from_date)
    if to_date:
        stmt = stmt.where(TherapySession.scheduled_date <= to_date)

    sessions = db.scalars(stmt).all()
    total = len(sessions)
    offset = (page - 1) * page_size
    page_sessions = sessions[offset : offset + page_size]
    items = []
    for s in page_sessions:
        case = s.case
        items.append(
            {
                "id": 0,
                "session_id": s.id,
                "case_id": s.case_id,
                "case_code": case.case_code if case else None,
                "external_case_ref": case.external_case_ref if case else None,
                "child_name": case.child.full_name if case and case.child else None,
                "therapist_user_id": s.therapist_user_id,
                "therapist_name": (db.get(User, s.therapist_user_id).full_name if db.get(User, s.therapist_user_id) else None),
                "scheduled_date": s.scheduled_date,
                "attendance_status": "",
                "submitted_at": None,
                "approval_status": LogApprovalStatus.PENDING,
                "late_addition": False,
                "can_edit": False,
                "status": "missing",
            }
        )
    pages = max(1, (total + page_size - 1) // page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": pages}


def admin_session_logs_summary(
    db: Session,
    user: User,
    *,
    from_date: date | None = None,
    to_date: date | None = None,
    product_module: str | None = None,
) -> dict:
    """Operational counts for CM/admin monitoring."""
    from app.core.timezone import today_ist
    from app.models.child import Child

    today = today_ist()
    range_from = from_date or today
    range_to = to_date or today
    case_ids = _case_ids_for_admin(db, user, product_module)
    if case_ids is not None and not case_ids:
        return _empty_summary(today, range_from, range_to)

    def _session_filters(stmt):
        if case_ids is not None:
            stmt = stmt.where(TherapySession.case_id.in_(case_ids))
        if range_from:
            stmt = stmt.where(TherapySession.scheduled_date >= range_from)
        if range_to:
            stmt = stmt.where(TherapySession.scheduled_date <= range_to)
        return stmt

    submitted_today = int(
        db.scalar(
            select(func.count())
            .select_from(DailyLog)
            .join(TherapySession, DailyLog.session_id == TherapySession.id)
            .where(
                DailyLog.submitted_at.isnot(None),
                func.date(DailyLog.submitted_at) == today,
                *([TherapySession.case_id.in_(case_ids)] if case_ids is not None else []),
            )
        )
        or 0
    )
    pending_review = int(
        db.scalar(
            _session_filters(
                select(func.count())
                .select_from(DailyLog)
                .join(TherapySession, DailyLog.session_id == TherapySession.id)
                .where(
                    DailyLog.submitted_at.isnot(None),
                    DailyLog.approval_status == LogApprovalStatus.PENDING,
                )
            )
        )
        or 0
    )
    approved_in_range = int(
        db.scalar(
            _session_filters(
                select(func.count())
                .select_from(DailyLog)
                .join(TherapySession, DailyLog.session_id == TherapySession.id)
                .where(DailyLog.approval_status == LogApprovalStatus.APPROVED)
            )
        )
        or 0
    )
    missing_logs = int(
        db.scalar(
            _session_filters(
                select(func.count())
                .select_from(TherapySession)
                .outerjoin(DailyLog, DailyLog.session_id == TherapySession.id)
                .where(TherapySession.status == SessionStatus.COMPLETED, DailyLog.id.is_(None))
            )
        )
        or 0
    )

    by_therapist_rows = db.execute(
        _session_filters(
            select(
                TherapySession.therapist_user_id,
                User.full_name,
                func.count(DailyLog.id),
            )
            .join(DailyLog, DailyLog.session_id == TherapySession.id)
            .join(User, User.id == TherapySession.therapist_user_id)
            .where(DailyLog.submitted_at.isnot(None))
            .group_by(TherapySession.therapist_user_id, User.full_name)
            .order_by(func.count(DailyLog.id).desc())
            .limit(50)
        )
    ).all()

    by_case_rows = db.execute(
        _session_filters(
            select(
                Case.id,
                Case.case_code,
                Child.first_name,
                Child.last_name,
                func.count(DailyLog.id),
            )
            .select_from(Case)
            .join(TherapySession, TherapySession.case_id == Case.id)
            .join(DailyLog, DailyLog.session_id == TherapySession.id)
            .outerjoin(Child, Case.child_id == Child.id)
            .where(DailyLog.submitted_at.isnot(None))
            .group_by(Case.id, Case.case_code, Child.first_name, Child.last_name)
            .order_by(func.count(DailyLog.id).desc())
            .limit(50)
        )
    ).all()

    attendance_rows = db.execute(
        _session_filters(
            select(DailyLog.attendance_status, func.count(DailyLog.id))
            .join(TherapySession, DailyLog.session_id == TherapySession.id)
            .where(DailyLog.submitted_at.isnot(None))
            .group_by(DailyLog.attendance_status)
        )
    ).all()

    return {
        "date_range": {"from": range_from.isoformat(), "to": range_to.isoformat()},
        "today": today.isoformat(),
        "submitted_today": submitted_today,
        "pending_review": pending_review,
        "approved_in_range": approved_in_range,
        "missing_logs": missing_logs,
        "by_therapist": [
            {"therapist_user_id": r[0], "therapist_name": r[1], "logs_submitted": r[2]}
            for r in by_therapist_rows
        ],
        "by_case": [
            {
                "case_id": r[0],
                "case_code": r[1],
                "child_name": f"{r[2] or ''} {r[3] or ''}".strip() or None,
                "logs_submitted": r[4],
            }
            for r in by_case_rows
        ],
        "attendance": {str(r[0]): r[1] for r in attendance_rows},
    }


def _empty_summary(today: date, range_from: date, range_to: date) -> dict:
    return {
        "date_range": {"from": range_from.isoformat(), "to": range_to.isoformat()},
        "today": today.isoformat(),
        "submitted_today": 0,
        "pending_review": 0,
        "approved_in_range": 0,
        "missing_logs": 0,
        "by_therapist": [],
        "by_case": [],
        "attendance": {},
    }
