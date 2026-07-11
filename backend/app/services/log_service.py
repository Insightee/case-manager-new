from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

LOG_EDIT_WINDOW = timedelta(hours=24)

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session, lazyload, selectinload

from app.models.case import Case
from app.models.document_comment import DocumentComment, DocumentEntityType
from app.models.daily_log import AttendanceStatus, DailyLog, LogApprovalStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.visibility import VisibilityStatus
from app.core.timezone import ensure_utc_aware, today_ist


def _normalize_attendance(value: str | AttendanceStatus) -> str:
    if isinstance(value, AttendanceStatus):
        return value.value
    raw = (value or "").strip().upper()
    legacy = {"PRESENT": AttendanceStatus.PRESENT, "ABSENT": AttendanceStatus.ABSENT, "LATE": AttendanceStatus.LATE, "PARTIAL": AttendanceStatus.PARTIAL}
    if raw in legacy:
        return legacy[raw].value
    if raw == "PRESENT" or raw == "present":
        return AttendanceStatus.PRESENT.value
    return raw or AttendanceStatus.PRESENT.value


def log_editable_until(log: DailyLog) -> datetime | None:
    if log.approval_status != LogApprovalStatus.PENDING or not log.submitted_at:
        return None
    submitted = log.submitted_at
    if submitted.tzinfo is None:
        submitted = submitted.replace(tzinfo=timezone.utc)
    return submitted + LOG_EDIT_WINDOW


def is_log_editable(log: DailyLog) -> bool:
    until = log_editable_until(log)
    if until is None:
        return False
    return datetime.now(timezone.utc) <= until


def is_log_resubmittable(log: DailyLog) -> bool:
    return log.approval_status == LogApprovalStatus.REJECTED


def can_therapist_edit_log(log: DailyLog) -> bool:
    if is_log_resubmittable(log):
        return True
    return is_log_editable(log)


def log_queue_sort_at(log: DailyLog) -> datetime | None:
    return log.resubmitted_at or log.submitted_at


def log_queue_order_desc():
    """SQLAlchemy order clause: most recently submitted/resubmitted first."""
    return func.coalesce(DailyLog.resubmitted_at, DailyLog.submitted_at).desc().nullslast()


def get_log(db: Session, log_id: int) -> DailyLog | None:
    return db.scalars(
        select(DailyLog).where(DailyLog.id == log_id).options(selectinload(DailyLog.session))
    ).first()


def list_logs(
    db: Session,
    *,
    therapist_user_id: int | None = None,
    case_id: int | None = None,
    month: str | None = None,
    product_module: str | None = None,
) -> list[DailyLog]:
    stmt = select(DailyLog).join(TherapySession).options(
        selectinload(DailyLog.session).selectinload(TherapySession.case)
    )
    if therapist_user_id:
        stmt = stmt.where(TherapySession.therapist_user_id == therapist_user_id)
    if case_id:
        stmt = stmt.where(TherapySession.case_id == case_id)
    if product_module:
        stmt = stmt.join(Case, TherapySession.case_id == Case.id).where(Case.product_module == product_module)
    logs = list(db.scalars(stmt).all())
    if month:
        logs = [l for l in logs if l.session and l.session.scheduled_date.strftime("%b %Y") == month]
    return logs


def create_daily_log(db: Session, **kwargs) -> tuple[DailyLog, bool]:
    """Create a daily log. Returns (log, created). Idempotent on session_id."""
    # Case uses lazy="joined" on TherapySession; lock only sessions (Postgres rejects
    # FOR UPDATE on the nullable side of an outer join to cases).
    session = db.scalars(
        select(TherapySession)
        .where(TherapySession.id == kwargs["session_id"])
        .options(lazyload(TherapySession.case))
        .with_for_update(of=TherapySession)
    ).first()
    if not session:
        raise ValueError("Session not found")
    if session.status != SessionStatus.COMPLETED:
        raise ValueError("End the session before submitting a log")
    existing = db.scalars(select(DailyLog).where(DailyLog.session_id == kwargs["session_id"])).first()
    if existing:
        return existing, False

    late = session.scheduled_date < today_ist()
    late_reason = kwargs.get("late_reason")
    if late and not (late_reason and str(late_reason).strip()):
        raise ValueError("Late reason is required for sessions from past days")

    attendance = _normalize_attendance(kwargs.get("attendance_status", AttendanceStatus.PRESENT))
    log = DailyLog(
        session_id=kwargs["session_id"],
        attendance_status=attendance,
        session_notes=kwargs.get("session_notes"),
        activities_done=kwargs.get("activities_done"),
        goals_addressed=kwargs.get("goals_addressed"),
        observations=kwargs.get("observations"),
        follow_ups=kwargs.get("follow_ups"),
        parent_notes=kwargs.get("parent_notes"),
        submitted_at=datetime.now(timezone.utc),
        approval_status=LogApprovalStatus.PENDING.value,
        late_addition=late,
        late_reason=late_reason.strip() if late and late_reason else None,
        visibility_status=VisibilityStatus.INTERNAL_ONLY.value,
    )
    db.add(log)
    db.flush()
    return log, True


def update_daily_log(db: Session, log: DailyLog, therapist_user_id: int, **kwargs) -> DailyLog:
    session = log.session or db.get(TherapySession, log.session_id)
    if not session or session.therapist_user_id != therapist_user_id:
        raise ValueError("Access denied")
    if is_log_resubmittable(log):
        pass
    elif log.approval_status != LogApprovalStatus.PENDING:
        raise ValueError("Only pending or rejected logs can be edited")
    elif not is_log_editable(log):
        raise ValueError("Logs can only be edited within 24 hours of submission")

    _apply_log_field_updates(log, kwargs)
    db.flush()
    return log


def _apply_log_field_updates(log: DailyLog, kwargs: dict) -> None:
    for field in (
        "session_notes",
        "activities_done",
        "goals_addressed",
        "observations",
        "follow_ups",
        "parent_notes",
        "late_reason",
        "parent_voice_attachment_id",
    ):
        if field in kwargs and kwargs[field] is not None:
            setattr(log, field, kwargs[field])
    if kwargs.get("attendance_status") is not None:
        log.attendance_status = _normalize_attendance(kwargs["attendance_status"])


def _validate_log_for_submission(log: DailyLog) -> None:
    activities = (log.activities_done or "").strip()
    if len(activities) < 3:
        raise ValueError("Describe what you did in this session (at least a few words).")
    if log.late_addition and not (log.late_reason and str(log.late_reason).strip()):
        raise ValueError("Late reason is required for sessions from past days")


def resubmit_daily_log(db: Session, log: DailyLog, therapist_user_id: int, **kwargs) -> DailyLog:
    session = log.session or db.get(TherapySession, log.session_id)
    if not session or session.therapist_user_id != therapist_user_id:
        raise ValueError("Access denied")
    if not is_log_resubmittable(log):
        raise ValueError("Only rejected logs can be resubmitted")

    _apply_log_field_updates(log, kwargs)
    _validate_log_for_submission(log)
    log.approval_status = LogApprovalStatus.PENDING.value
    log.review_note = None
    log.submitted_at = datetime.now(timezone.utc)
    log.resubmitted_at = datetime.now(timezone.utc)
    db.flush()
    return log


def comment_counts_for_log_ids(
    db: Session,
    log_ids: list[int],
    *,
    parent_visible_only: bool = False,
) -> dict[int, tuple[int, int]]:
    """Return {log_id: (comment_count, open_parent_comment_count)}."""
    if not log_ids:
        return {}

    filters = [
        DocumentComment.entity_type == DocumentEntityType.DAILY_LOG.value,
        DocumentComment.entity_id.in_(log_ids),
    ]
    if parent_visible_only:
        filters.append(DocumentComment.visibility == "parent_team")

    open_parent_expr = func.sum(
        case(
            (
                and_(
                    DocumentComment.author_role == "parent",
                    DocumentComment.status == "open",
                    DocumentComment.visibility == "parent_team",
                ),
                1,
            ),
            else_=0,
        )
    )

    rows = db.execute(
        select(
            DocumentComment.entity_id,
            func.count(DocumentComment.id),
            open_parent_expr,
        )
        .where(*filters)
        .group_by(DocumentComment.entity_id)
    ).all()

    return {
        int(entity_id): (int(total), int(open_parent or 0))
        for entity_id, total, open_parent in rows
    }


def attach_comment_counts(
    db: Session,
    reads: list[dict],
    *,
    parent_visible_only: bool = False,
) -> None:
    log_ids = [item["id"] for item in reads if item.get("id") is not None]
    counts = comment_counts_for_log_ids(db, log_ids, parent_visible_only=parent_visible_only)
    for item in reads:
        log_id = item.get("id")
        total, open_parent = counts.get(log_id, (0, 0))
        item["comment_count"] = total
        item["open_parent_comment_count"] = open_parent


def log_to_read(log: DailyLog, include_clinical: bool = True, include_structured: bool = False) -> dict:
    session = log.session
    case = session.case if session and getattr(session, "case", None) else None
    data = {
        "id": log.id,
        "session_id": log.session_id,
        "case_id": session.case_id if session else None,
        "case_code": case.case_code if case else (session.case.case_code if session and getattr(session, "case", None) else None),
        "attendance_status": log.attendance_status,
        "activities_done": log.activities_done,
        "goals_addressed": log.goals_addressed,
        "follow_ups": log.follow_ups,
        "submitted_at": log.submitted_at,
        "approval_status": log.approval_status,
        "late_addition": bool(log.late_addition),
        "late_reason": log.late_reason,
        "review_note": log.review_note,
        "parent_session_rating": log.parent_session_rating,
        "parent_feedback": log.parent_feedback,
        "parent_feedback_at": ensure_utc_aware(log.parent_feedback_at),
        "can_edit": can_therapist_edit_log(log),
        "can_resubmit": is_log_resubmittable(log),
        "resubmitted_at": ensure_utc_aware(log.resubmitted_at),
        "editable_until": log_editable_until(log),
    }
    if session:
        data["scheduled_date"] = session.scheduled_date
        data["actual_start_at"] = ensure_utc_aware(session.actual_start_at)
        data["actual_end_at"] = ensure_utc_aware(session.actual_end_at)
        data["edited_start_at"] = ensure_utc_aware(getattr(session, "edited_start_at", None))
        data["edited_end_at"] = ensure_utc_aware(getattr(session, "edited_end_at", None))
        data["actual_times_edited"] = bool(getattr(session, "actual_times_edited", False))
        data["actual_times_edit_reason"] = getattr(session, "actual_times_edit_reason", None)
        data["duplicate_day_session"] = bool(getattr(session, "is_additional_visit", False))
        if case and getattr(case, "child", None):
            data["child_name"] = case.child.full_name
    if session and not data.get("case_code") and getattr(session, "case", None):
        data["case_code"] = session.case.case_code
    if include_clinical:
        data["session_notes"] = log.session_notes
        data["observations"] = log.observations
        data["parent_notes"] = log.parent_notes
    if include_structured and include_clinical:
        # Single-log reads only — keeps list payloads lean.
        raw = getattr(log, "structured_session_json", None)
        if raw:
            try:
                data["structured_session_json"] = json.loads(raw) if isinstance(raw, str) else raw
            except (TypeError, ValueError):
                pass
        data["therapist_reflection"] = getattr(log, "therapist_reflection", None)
    if log.late_addition:
        data["source"] = "forgotten"
        status = log.approval_status.value if hasattr(log.approval_status, "value") else str(log.approval_status)
        if status == "PENDING":
            data["status_label"] = "Forgotten session — pending approval"
        elif status == "APPROVED":
            data["status_label"] = "Forgotten session — approved"
        elif status == "REJECTED":
            data["status_label"] = "Forgotten session — rejected"
    elif session and getattr(session, "is_additional_visit", False):
        status = log.approval_status.value if hasattr(log.approval_status, "value") else str(log.approval_status)
        if status == "PENDING":
            data["status_label"] = "Second session same day — pending review"
        elif status == "APPROVED":
            data["status_label"] = "Second session same day — approved"
        elif status == "REJECTED":
            data["status_label"] = "Second session same day — rejected"
    return data
