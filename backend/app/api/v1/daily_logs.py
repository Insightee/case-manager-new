from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.db_errors import commit_or_http
from app.core.module_access import user_has_feature
from app.core.module_write import ensure_case_write_access, ensure_feature_write_access
from app.core.permissions import RoleName, case_scope_check, require_permission, user_has_permission
from app.models.case import ClientBillingMode
from app.models.daily_log import LogApprovalStatus
from app.models.user import User
from app.schemas.daily_log import (
    DailyLogCreate,
    DailyLogFinanceRead,
    DailyLogRead,
    DailyLogUpdate,
    LogCommentCountRead,
    LogCommentCreate,
    LogCommentRead,
)
from app.services import billing_ledger_service, case_service, log_comment_notify_service, log_service, session_log_service
from app.services import virtual_session_log_service as virtual_logs

from sqlalchemy import select
from app.models.session import Session as TherapySession, SessionStatus
from app.models.session_absence import SessionAbsenceRequest, SessionAbsenceStatus
from app.models.support_ticket import SupportTicket, TicketStatus
from app.models.document_comment import DocumentComment, DocumentEntityType

router = APIRouter(prefix="/daily-logs", tags=["daily-logs"])


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

    virtual_log_dicts = virtual_logs.collect_virtual_logs(
        db,
        therapist_user_id=therapist_user_id,
        case_id=case_id,
        month=month,
        product_module=product_module,
        approval_status_filter=approval_status,
        late_addition=late_addition,
        include_clinical=not is_finance,
    )
    virtual_logs_out = []
    virtual_dicts_for_counts = []
    for vlog_dict in virtual_log_dicts:
        if own_logs_only and vlog_dict.get("case_id"):
            session_row = db.get(TherapySession, vlog_dict["session_id"])
            if not session_row or session_row.therapist_user_id != user.id:
                continue
        elif vlog_dict.get("case_id"):
            case = case_service.get_case(db, vlog_dict["case_id"])
            if not case or not case_scope_check(db, user, case):
                continue
        if is_finance:
            virtual_logs_out.append(DailyLogFinanceRead(**vlog_dict))
        else:
            virtual_dicts_for_counts.append(vlog_dict)

    if is_finance:
        res = [DailyLogFinanceRead(**log_service.log_to_read(l, include_clinical=False)) for l in logs]
        combined = res + virtual_logs_out
    else:
        log_dicts = [log_service.log_to_read(l) for l in logs]
        log_service.attach_comment_counts(db, log_dicts + virtual_dicts_for_counts, parent_visible_only=False)
        res = [DailyLogRead(**d) for d in log_dicts]
        combined = res + [DailyLogRead(**v) for v in virtual_dicts_for_counts]
    combined.sort(key=lambda x: x.scheduled_date or datetime.min.date(), reverse=True)
    return combined


@router.get("/comment-counts")
def get_log_comment_counts(
    log_ids: str = Query(..., description="Comma-separated daily log IDs"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user_has_permission(user, "session.read") and not user_has_permission(user, "daily_log.review"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    parsed_ids: list[int] = []
    for part in log_ids.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            parsed_ids.append(int(part))
        except ValueError:
            continue
    if not parsed_ids:
        return {}

    own_logs_only = _therapist_lists_own_logs_only(user)
    allowed_ids: list[int] = []
    for log_id in parsed_ids:
        if log_id > 0:
            log = log_service.get_log(db, log_id)
            if not log:
                continue
            if own_logs_only:
                if not log.session or log.session.therapist_user_id != user.id:
                    continue
            else:
                if not log.session:
                    continue
                case = case_service.get_case(db, log.session.case_id)
                if not case or not case_scope_check(db, user, case):
                    continue
            allowed_ids.append(log_id)
        else:
            session = db.get(TherapySession, -log_id)
            if not session:
                continue
            case = case_service.get_case(db, session.case_id)
            if not case or not case_scope_check(db, user, case):
                continue
            if own_logs_only and session.therapist_user_id != user.id:
                continue
            allowed_ids.append(log_id)

    counts = log_service.comment_counts_for_log_ids(db, allowed_ids, parent_visible_only=False)
    return {
        str(log_id): LogCommentCountRead(
            comment_count=counts.get(log_id, (0, 0))[0],
            open_parent_comment_count=counts.get(log_id, (0, 0))[1],
        )
        for log_id in allowed_ids
    }


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
    read = log_service.log_to_read(log)
    log_service.attach_comment_counts(db, [read], parent_visible_only=False)
    return DailyLogRead(**read)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_daily_log(
    payload: DailyLogCreate,
    request: Request,
    user: User = Depends(require_permission("daily_log.create")),
    db: Session = Depends(get_db),
):
    evidence = payload.session_evidence
    body = payload.model_dump(exclude={"session_evidence"})
    try:
        log, created = log_service.create_daily_log(db, **body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        _apply_session_evidence(db, log, user, evidence)
    except HTTPException:
        raise
    if created:
        commit_or_http(db)
        db.refresh(log)
        try:
            session_log_service.notify_case_managers_log_submitted(db, log, therapist=user)
            session_log_service.notify_parents_session_log_submitted(db, log, therapist=user)
            meta = get_request_meta(request)
            log_audit(
                db,
                actor_user_id=user.id,
                action="create",
                entity_type="daily_log",
                entity_id=log.id,
                new_value=payload.model_dump(),
                **meta,
            )
            commit_or_http(db)
        except HTTPException as exc:
            import logging

            logging.getLogger("insightcase").warning(
                "Post-create notify/audit failed for daily_log %s (HTTP %s): %s; log was saved",
                log.id,
                exc.status_code,
                exc.detail,
            )
            db.rollback()
        except Exception:
            import logging

            logging.getLogger("insightcase").exception(
                "Post-create notify/audit failed for daily_log %s; log was saved",
                log.id,
            )
            db.rollback()
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
    evidence = payload.session_evidence
    body = payload.model_dump(exclude={"session_evidence"}, exclude_unset=True)
    try:
        log = log_service.update_daily_log(db, log, user.id, **body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        _apply_session_evidence(db, log, user, evidence)
    except HTTPException:
        raise
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
    evidence = payload.session_evidence
    body = payload.model_dump(exclude={"session_evidence"}, exclude_unset=True)
    try:
        log = log_service.resubmit_daily_log(db, log, user.id, **body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        _apply_session_evidence(db, log, user, evidence)
    except HTTPException:
        raise
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
    log.approval_status = LogApprovalStatus.APPROVED.value
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
    log.approval_status = LogApprovalStatus.REJECTED.value
    log.review_note = comment
    from app.services import session_log_service

    session_log_service.notify_therapist_log_rejected(db, log, comment=comment)
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="reject", entity_type="daily_log", entity_id=log.id, **meta)
    db.commit()
    return {"status": "rejected"}


class SessionGoalEntryIn(BaseModel):
    goal_card_id: Optional[int] = None
    goal_label: str
    domain_key: Optional[str] = None
    support_level: Optional[str] = None
    response_note: Optional[str] = None
    measurement_note: Optional[str] = None
    visibility: Optional[str] = "INTERNAL_ONLY"
    schema_version: Optional[int] = None
    participation_score: Optional[int] = None
    independence_score: Optional[int] = None
    goal_achievement_score: Optional[int] = None
    activity_used: Optional[str] = None
    goal_repository_item_id: Optional[int] = None
    evidence_count: Optional[int] = None
    clinical_extension: Optional[dict[str, Any]] = None
    strategies: list["StrategyUseEventIn"] = Field(default_factory=list)


class StrategyUseEventIn(BaseModel):
    strategy_id: Optional[int] = None
    strategy_label: str
    outcome_note: Optional[str] = None
    short_note: Optional[str] = None
    goal_card_id: Optional[int] = None
    goal_entry_id: Optional[int] = None
    schema_version: Optional[int] = None
    environment: Optional[str] = None
    activity_used: Optional[str] = None
    participation_score: Optional[int] = None
    independence_score: Optional[int] = None
    goal_achievement_score: Optional[int] = None
    strategy_feedback: Optional[str] = None
    custom_strategy_id: Optional[int] = None
    clinical_extension: Optional[dict[str, Any]] = None


class SessionEvidenceSave(BaseModel):
    goals: list[SessionGoalEntryIn] = Field(default_factory=list)
    strategies: list[StrategyUseEventIn] = Field(default_factory=list)


def _apply_session_evidence(db, log, user, evidence: SessionEvidenceSave | dict | None) -> None:
    if not evidence:
        return
    from app.services import clinical_evidence_service as ev_svc

    if isinstance(evidence, dict):
        payload = SessionEvidenceSave(**evidence)
    else:
        payload = evidence
    if not payload.goals and not payload.strategies:
        return
    case_id = log.session.case_id
    ev_svc.save_session_evidence(
        db,
        daily_log=log,
        case_id=case_id,
        goals=[g.model_dump() for g in payload.goals],
        strategies=[s.model_dump() for s in payload.strategies],
        created_by_user_id=user.id,
        commit=False,
    )


@router.get("/{log_id}/session-evidence")
def get_session_evidence(
    log_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import clinical_evidence_service as ev_svc

    log = log_service.get_log(db, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    _log_case_scope(db, user, log)
    return ev_svc.entries_for_log(db, log_id)


@router.put("/{log_id}/session-evidence")
def save_session_evidence(
    log_id: int,
    payload: SessionEvidenceSave,
    user: User = Depends(require_permission("daily_log.create")),
    db: Session = Depends(get_db),
):
    from app.services import clinical_evidence_service as ev_svc

    log = log_service.get_log(db, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    case_id = log.session.case_id
    case = case_service.get_case(db, case_id)
    if case:
        ensure_case_write_access(user, case, db)
    result = ev_svc.save_session_evidence(
        db,
        daily_log=log,
        case_id=case_id,
        goals=[g.model_dump() for g in payload.goals],
        strategies=[s.model_dump() for s in payload.strategies],
        created_by_user_id=user.id,
        commit=True,
    )
    return result


class AiNoteRequest(BaseModel):
    note: str = Field(min_length=1)


@router.post("/{log_id}/ai/improve-note")
def ai_improve_note(
    log_id: int,
    payload: AiNoteRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import ai_gateway_service as ai_svc

    log = log_service.get_log(db, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    _log_case_scope(db, user, log)
    case = log.session.case if log.session else None
    child_name = case.child_name if case and hasattr(case, "child_name") else "the child"
    return ai_svc.AIGatewayService.improve_session_log_note(
        db,
        user_id=user.id,
        case_id=case.id if case else None,
        note=payload.note,
        child_name=child_name,
    )


@router.post("/{log_id}/ai/check-evidence")
def ai_check_evidence(
    log_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from sqlalchemy import select

    from app.models.clinical_evidence import SessionGoalEntry, StrategyUseEvent

    log = log_service.get_log(db, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    _log_case_scope(db, user, log)

    missing: list[str] = []
    entries = db.scalars(select(SessionGoalEntry).where(SessionGoalEntry.daily_log_id == log.id)).all()
    if not (log.goals_addressed or "").strip() and not entries:
        missing.append("goal link")
    strategies = db.scalars(select(StrategyUseEvent).where(StrategyUseEvent.daily_log_id == log.id)).all()
    if not strategies:
        missing.append("strategy used")
    if entries and not any((e.response_note or "").strip() for e in entries):
        missing.append("child response")
    if entries and not any((e.support_level or "").strip() for e in entries):
        missing.append("support level")
    if not (log.activities_done or "").strip():
        missing.append("activities / environment context")
    if not (log.follow_ups or "").strip():
        missing.append("next step")
    return {"missing": missing, "complete": len(missing) == 0}


@router.post("/{log_id}/ai/suggest-capture")
def ai_suggest_capture(
    log_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import clinical_insight_summary_service as summary_svc
    from datetime import datetime, timezone

    log = log_service.get_log(db, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    _log_case_scope(db, user, log)
    case_id = log.session.case_id
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    summary = summary_svc.build_monthly_case_summary(db, case_id, month)
    suggestions = []
    for g in summary.get("goals", [])[:3]:
        title = g.get("goal_title") or "Goal"
        suggestions.append(
            f"For {title}, capture whether strategies were used, support level, and child response."
        )
    if not suggestions:
        suggestions.append("Link this session to active IEP goals and record child response.")
    return {"suggestions": suggestions}


@router.post("/{log_id}/ai/match-strategy")
def ai_match_strategy(
    log_id: int,
    label: str = Query(..., min_length=2),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import reference_retrieval_service as ref_svc

    log = log_service.get_log(db, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    _log_case_scope(db, user, log)
    matches = ref_svc.retrieve_strategy_references(db, label, user.id, top_k=3)
    return {
        "matches": [{"title": m.get("chunk_title"), "excerpt": m.get("chunk_text", "")[:200]} for m in matches],
        "options": ["use_existing", "keep_custom", "send_cm_review"],
    }


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
        own_logs_only = _therapist_lists_own_logs_only(user)
        if own_logs_only:
            if not log.session or log.session.therapist_user_id != user.id:
                raise HTTPException(status_code=403, detail="Log access denied")
        else:
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
                author_role=c.author_role,
                visibility=c.visibility,
                status=c.status,
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
        own_logs_only = _therapist_lists_own_logs_only(user)
        if own_logs_only:
            if not log.session or log.session.therapist_user_id != user.id:
                raise HTTPException(status_code=403, detail="Log access denied")
        else:
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

    # Determine author role
    author_role = "therapist"
    if "SUPER_ADMIN" in user.role_names or "MODULE_ADMIN" in user.role_names:
        author_role = "admin"
    elif "CASE_MANAGER" in user.role_names:
        author_role = "case_manager"
    elif "PARENT" in user.role_names:
        author_role = "parent"

    comment = DocumentComment(
        entity_type="daily_log",
        entity_id=log_id,
        case_id=case_id,
        author_user_id=user.id,
        author_role=author_role,
        visibility=payload.visibility or "parent_team",
        status="open",
        body=payload.body.strip(),
        comment_type="GENERAL"
    )
    db.add(comment)
    db.flush()

    # Acknowledge parent comments if team replies in public thread
    if author_role in ("therapist", "case_manager", "admin") and (payload.visibility or "parent_team") == "parent_team":
        db.execute(
            DocumentComment.__table__.update()
            .where(
                DocumentComment.entity_type == "daily_log",
                DocumentComment.entity_id == log_id,
                DocumentComment.author_role == "parent",
                DocumentComment.status == "open"
            )
            .values(status="acknowledged")
        )

    log_comment_notify_service.notify_parents_on_staff_log_reply(
        db,
        comment_id=comment.id,
        log_id=log_id,
        case_id=case_id,
        staff_user=user,
        author_role=author_role,
        visibility=payload.visibility or "parent_team",
    )

    db.commit()
    db.refresh(comment)

    return LogCommentRead(
        id=comment.id,
        body=comment.body,
        author_name=user.full_name or user.email,
        author_role=comment.author_role,
        visibility=comment.visibility,
        status=comment.status,
        created_at=comment.created_at
    )


class CommentStatusUpdate(BaseModel):
    status: str


@router.patch("/comments/{comment_id}/status", response_model=LogCommentRead)
def update_comment_status(
    comment_id: int,
    payload: CommentStatusUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.status not in ("open", "acknowledged", "resolved"):
        raise HTTPException(status_code=400, detail="Invalid status value")
    comment = db.get(DocumentComment, comment_id)
    if not comment or comment.entity_type != "daily_log":
        raise HTTPException(status_code=404, detail="Comment not found")

    case = case_service.get_case(db, comment.case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=403, detail="Case access denied")

    is_admin_or_cm = (
        "SUPER_ADMIN" in user.role_names
        or "MODULE_ADMIN" in user.role_names
        or "CASE_MANAGER" in user.role_names
    )
    if not is_admin_or_cm and payload.status == "resolved":
        raise HTTPException(status_code=403, detail="Only Case Manager or Admin can resolve comments")

    comment.status = payload.status
    db.commit()
    db.refresh(comment)

    author = db.get(User, comment.author_user_id)
    return LogCommentRead(
        id=comment.id,
        body=comment.body,
        author_name=author.full_name if author else None,
        author_role=comment.author_role,
        visibility=comment.visibility,
        status=comment.status,
        created_at=comment.created_at
    )
