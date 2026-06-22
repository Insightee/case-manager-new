from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.module_access import user_has_feature
from app.core.module_write import ensure_case_write_access, ensure_feature_write_access
from app.core.permissions import RoleName, case_scope_check, require_permission, user_has_permission
from app.models.case import ClientBillingMode
from app.models.daily_log import LogApprovalStatus
from app.models.user import User
from app.schemas.daily_log import DailyLogCreate, DailyLogFinanceRead, DailyLogRead, DailyLogUpdate, LogCommentRead, LogCommentCreate
from app.services import billing_ledger_service, case_service, log_service

from sqlalchemy import select
from app.models.session import Session as TherapySession, SessionStatus
from app.models.session_absence import SessionAbsenceRequest, SessionAbsenceStatus
from app.models.support_ticket import SupportTicket, TicketStatus
from app.models.document_comment import DocumentComment, DocumentEntityType

router = APIRouter(prefix="/daily-logs", tags=["daily-logs"])


def serialize_virtual_log(db: Session, session: TherapySession, case: Case, include_clinical: bool = True) -> dict:
    # 1. Determine attendance_status
    attendance_status = "THERAPIST_LEAVE"
    absence_req = None
    if session.status == SessionStatus.CLIENT_ABSENT:
        absence_req = db.scalars(
            select(SessionAbsenceRequest).where(
                SessionAbsenceRequest.session_id == session.id,
                SessionAbsenceRequest.status == SessionAbsenceStatus.APPROVED
            )
        ).first()
        if absence_req and absence_req.absence_type == "CLIENT_ABSENT":
            attendance_status = "CLIENT_LEAVE"
        else:
            attendance_status = "CLIENT_ABSENT"

    # 2. Check dispute status
    dispute_stmt = select(SupportTicket).where(
        SupportTicket.disputed_session_id == session.id,
        SupportTicket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS])
    )
    disputed_ticket = db.scalars(dispute_stmt).first()
    dispute_status = "DISPUTED" if disputed_ticket else "NONE"

    # 3. Build dict
    sub_dt = datetime.combine(session.scheduled_date, datetime.min.time(), tzinfo=timezone.utc)
    res = {
        "id": -session.id,
        "session_id": session.id,
        "case_id": session.case_id,
        "case_code": case.case_code if case else None,
        "child_name": case.child.full_name if (case and case.child) else None,
        "scheduled_date": session.scheduled_date,
        "actual_start_at": session.actual_start_at,
        "actual_end_at": session.actual_end_at,
        "edited_start_at": getattr(session, "edited_start_at", None),
        "edited_end_at": getattr(session, "edited_end_at", None),
        "actual_times_edited": bool(getattr(session, "actual_times_edited", False)),
        "actual_times_edit_reason": getattr(session, "actual_times_edit_reason", None),
        "duplicate_day_session": bool(getattr(session, "is_additional_visit", False)),
        "status_label": "Therapist Leave" if session.status == SessionStatus.THERAPIST_LEAVE else ("Client Leave" if attendance_status == "CLIENT_LEAVE" else "Client Absent"),
        "attendance_status": attendance_status,
        "submitted_at": sub_dt,
        "approval_status": LogApprovalStatus.APPROVED,
        "late_addition": False,
        "can_edit": False,
        "can_resubmit": False,
        "absence_reason": absence_req.reason if absence_req else (session.actual_times_edit_reason or None),
        "dispute_status": dispute_status,
    }
    if include_clinical:
        res.update({
            "session_notes": None,
            "activities_done": None,
            "observations": None,
            "parent_notes": None,
        })
    return res


class LogRejectAction(BaseModel):
    comment: str


def _log_case_scope(db: Session, user: User, log) -> None:
    if not log.session:
        raise HTTPException(status_code=404, detail="Log not found")
    case = case_service.get_case(db, log.session.case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=403, detail="Case access denied")


def _therapist_lists_own_logs_only(user: User) -> bool:
    if RoleName.THERAPIST.value not in user.role_names:
        return False
    if user_has_permission(user, "daily_log.review") or user_has_permission(user, "case.read.all"):
        return False
    return user_has_permission(user, "daily_log.create")


@router.get("")
def list_daily_logs(
    therapist_user_id: Optional[int] = None,
    case_id: Optional[int] = None,
    month: Optional[str] = None,
    product_module: Optional[str] = None,
    approval_status: Optional[LogApprovalStatus] = None,
    late_addition: Optional[bool] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user_has_permission(user, "session.read") and not user_has_permission(user, "daily_log.review"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    if user_has_permission(user, "session.read") and not user_has_feature(user, "session_logs", db) and not user_has_permission(user, "daily_log.create"):
        raise HTTPException(status_code=403, detail="Session logs module access required")
    own_logs_only = _therapist_lists_own_logs_only(user)
    if therapist_user_id is None and own_logs_only:
        therapist_user_id = user.id
    logs = log_service.list_logs(db, therapist_user_id=therapist_user_id, case_id=case_id, month=month, product_module=product_module)
    if approval_status is not None:
        logs = [l for l in logs if l.approval_status == approval_status]
    if late_addition is not None:
        logs = [l for l in logs if bool(l.late_addition) == late_addition]
    if own_logs_only and therapist_user_id == user.id:
        logs = [l for l in logs if l.session]
    else:
        scoped = []
        for log in logs:
            if not log.session:
                continue
            case = case_service.get_case(db, log.session.case_id)
            if case and case_scope_check(db, user, case):
                scoped.append(log)
        logs = scoped
    is_finance = RoleName.FINANCE.value in user.role_names and RoleName.SUPER_ADMIN.value not in user.role_names
    
    virtual_logs = []
    if (approval_status is None or approval_status == LogApprovalStatus.APPROVED) and (late_addition is None or late_addition is False):
        from app.models.case import Case
        session_stmt = select(TherapySession).where(
            TherapySession.status.in_([SessionStatus.CLIENT_ABSENT, SessionStatus.THERAPIST_LEAVE])
        )
        if therapist_user_id:
            session_stmt = session_stmt.where(TherapySession.therapist_user_id == therapist_user_id)
        if case_id:
            session_stmt = session_stmt.where(TherapySession.case_id == case_id)
        if product_module:
            session_stmt = session_stmt.join(Case, TherapySession.case_id == Case.id).where(Case.product_module == product_module)
        
        sessions = db.scalars(session_stmt).all()
        for s in sessions:
            case = case_service.get_case(db, s.case_id)
            if not case:
                continue
            if own_logs_only and s.therapist_user_id != user.id:
                continue
            if not own_logs_only and not case_scope_check(db, user, case):
                continue
            if month and s.scheduled_date.strftime("%b %Y") != month:
                continue
            
            vlog_dict = serialize_virtual_log(db, s, case, include_clinical=not is_finance)
            if is_finance:
                virtual_logs.append(DailyLogFinanceRead(**vlog_dict))
            else:
                virtual_logs.append(DailyLogRead(**vlog_dict))

    if is_finance:
        res = [DailyLogFinanceRead(**log_service.log_to_read(l, include_clinical=False)) for l in logs]
    else:
        res = [DailyLogRead(**log_service.log_to_read(l)) for l in logs]
    
    combined = res + virtual_logs
    combined.sort(key=lambda x: x.scheduled_date or datetime.min.date(), reverse=True)
    return combined


@router.get("/{log_id}", response_model=DailyLogRead)
def get_daily_log(
    log_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user_has_permission(user, "session.read") and not user_has_permission(user, "daily_log.review"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    if user_has_permission(user, "session.read") and not user_has_feature(user, "session_logs", db) and not user_has_permission(user, "daily_log.create"):
        raise HTTPException(status_code=403, detail="Session logs module access required")
    log = log_service.get_log(db, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    own_logs_only = _therapist_lists_own_logs_only(user)
    if own_logs_only:
        if not log.session or log.session.therapist_user_id != user.id:
            raise HTTPException(status_code=403, detail="Log access denied")
    else:
        _log_case_scope(db, user, log)
    return DailyLogRead(**log_service.log_to_read(log))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_daily_log(
    payload: DailyLogCreate,
    request: Request,
    user: User = Depends(require_permission("daily_log.create")),
    db: Session = Depends(get_db),
):
    try:
        log = log_service.create_daily_log(db, **payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    from app.services import session_log_service

    session_log_service.notify_case_managers_log_submitted(db, log, therapist=user)
    session_log_service.notify_parents_session_log_submitted(db, log, therapist=user)
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="create", entity_type="daily_log", entity_id=log.id, new_value=payload.model_dump(), **meta)
    db.commit()
    return DailyLogRead(**log_service.log_to_read(log))


@router.patch("/{log_id}", response_model=DailyLogRead)
def update_daily_log(
    log_id: int,
    payload: DailyLogUpdate,
    request: Request,
    user: User = Depends(require_permission("daily_log.create")),
    db: Session = Depends(get_db),
):
    log = log_service.get_log(db, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    try:
        log = log_service.update_daily_log(db, log, user.id, **payload.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="update", entity_type="daily_log", entity_id=log.id, **meta)
    db.commit()
    return DailyLogRead(**log_service.log_to_read(log))


@router.post("/{log_id}/resubmit", response_model=DailyLogRead)
def resubmit_daily_log(
    log_id: int,
    payload: DailyLogUpdate,
    request: Request,
    user: User = Depends(require_permission("daily_log.create")),
    db: Session = Depends(get_db),
):
    log = log_service.get_log(db, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    try:
        log = log_service.resubmit_daily_log(db, log, user.id, **payload.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    from app.services import session_log_service

    session_log_service.notify_case_managers_log_submitted(db, log, therapist=user, resubmitted=True)
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="resubmit", entity_type="daily_log", entity_id=log.id, **meta)
    db.commit()
    return DailyLogRead(**log_service.log_to_read(log))


@router.post("/{log_id}/approve")
def approve_log(
    log_id: int,
    request: Request,
    user: User = Depends(require_permission("daily_log.review")),
    db: Session = Depends(get_db),
):
    log = log_service.get_log(db, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    _log_case_scope(db, user, log)
    case = case_service.get_case(db, log.session.case_id)
    if case:
        ensure_case_write_access(user, case, db)
        ensure_feature_write_access(user, "session_logs", product_module=case.product_module, db=db)
    log.approval_status = LogApprovalStatus.APPROVED
    if not log.submitted_at:
        log.submitted_at = datetime.now(timezone.utc)
    from app.services import session_log_service

    session_log_service.publish_log_to_parents(log)
    session_log_service.notify_parents_session_log_approved(db, log)
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="approve", entity_type="daily_log", entity_id=log.id, **meta)
    try:
        billing_ledger_service.upsert_from_daily_log_approved(db, log)
        if case and case.client_billing_mode == ClientBillingMode.PREPAID:
            billing_ledger_service.consume_package_session(db, case_id=case.id, session=log.session)
    except Exception:
        pass
    db.commit()
    return {"status": "approved"}


@router.post("/{log_id}/reject")
def reject_log(
    log_id: int,
    payload: LogRejectAction,
    request: Request,
    user: User = Depends(require_permission("daily_log.review")),
    db: Session = Depends(get_db),
):
    comment = (payload.comment or "").strip()
    if not comment:
        raise HTTPException(status_code=400, detail="Rejection comment is required")
    log = log_service.get_log(db, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    _log_case_scope(db, user, log)
    case = case_service.get_case(db, log.session.case_id)
    if case:
        ensure_case_write_access(user, case, db)
        ensure_feature_write_access(user, "session_logs", product_module=case.product_module, db=db)
    log.approval_status = LogApprovalStatus.REJECTED
    log.review_note = comment
    from app.services import session_log_service

    session_log_service.notify_therapist_log_rejected(db, log, comment=comment)
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="reject", entity_type="daily_log", entity_id=log.id, **meta)
    db.commit()
    return {"status": "rejected"}


@router.get("/{log_id}/comments", response_model=list[LogCommentRead])
def list_log_comments(
    log_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if log_id > 0:
        log = log_service.get_log(db, log_id)
        if not log:
            raise HTTPException(status_code=404, detail="Log not found")
        _log_case_scope(db, user, log)
    else:
        session = db.get(TherapySession, -log_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        case = case_service.get_case(db, session.case_id)
        if not case or not case_scope_check(db, user, case):
            raise HTTPException(status_code=403, detail="Case access denied")

    comments = db.scalars(
        select(DocumentComment)
        .where(
            DocumentComment.entity_type == "daily_log",
            DocumentComment.entity_id == log_id
        )
        .order_by(DocumentComment.created_at.asc())
    ).all()
    
    out = []
    for c in comments:
        author = db.get(User, c.author_user_id)
        out.append(
            LogCommentRead(
                id=c.id,
                body=c.body,
                author_name=author.full_name if author else None,
                created_at=c.created_at
            )
        )
    return out


@router.post("/{log_id}/comments", response_model=LogCommentRead, status_code=status.HTTP_201_CREATED)
def add_log_comment(
    log_id: int,
    payload: LogCommentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case_id = None
    if log_id > 0:
        log = log_service.get_log(db, log_id)
        if not log:
            raise HTTPException(status_code=404, detail="Log not found")
        _log_case_scope(db, user, log)
        case_id = log.session.case_id if log.session else None
    else:
        session = db.get(TherapySession, -log_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        case = case_service.get_case(db, session.case_id)
        if not case or not case_scope_check(db, user, case):
            raise HTTPException(status_code=403, detail="Case access denied")
        case_id = session.case_id

    if not case_id:
        raise HTTPException(status_code=400, detail="Cannot comment on logs without a linked case")

    comment = DocumentComment(
        entity_type="daily_log",
        entity_id=log_id,
        case_id=case_id,
        author_user_id=user.id,
        body=payload.body.strip(),
        comment_type="GENERAL"
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    return LogCommentRead(
        id=comment.id,
        body=comment.body,
        author_name=user.full_name or user.email,
        created_at=comment.created_at
    )
