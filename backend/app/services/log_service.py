from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

LOG_EDIT_WINDOW = timedelta(hours=24)

from sqlalchemy import and_, case, delete, func, select
from sqlalchemy.orm import Session, lazyload, selectinload

from app.core.config import settings
from app.models.case import Case
from app.models.document_comment import DocumentComment, DocumentEntityType
from app.models.daily_log import AttendanceStatus, DailyLog, LogApprovalStatus
from app.models.iep_identity import IepGoalItem, IepStrategyItem
from app.models.iep_plan import IepPlan
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.session_evidence import SessionGoalEntry, StrategyUseEvent
from app.models.visibility import VisibilityStatus
from app.core.timezone import ensure_utc_aware, today_ist
from app.services import therapist_transition_service

PARTICIPATION_VALUES = frozenset({"engaged", "mixed", "supported"})
SUPPORT_LEVEL_VALUES = frozenset({"independent", "occasional", "consistent"})
ACHIEVEMENT_VALUES = frozenset({"emerging", "progressing", "demonstrated"})
STRATEGY_RESPONSE_VALUES = frozenset({"helpful", "partly_helpful", "rejected", "needs_adaptation"})
_MISSING_IEP_ITEM = "Looks like that goal is no longer on the active IEP. Refresh and try again."
_MISSING_STRATEGY_ITEM = "Looks like that strategy is no longer on the active IEP. Refresh and try again."
_INCOMPLETE_TAP = "Looks like we still need a few details before we can save this."


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


def _session_case_id(db: Session, log: DailyLog) -> int:
    session = log.session or db.get(TherapySession, log.session_id)
    if not session:
        raise ValueError("Session not found")
    return session.case_id


def _goal_on_case(db: Session, goal_id: int, case_id: int) -> IepGoalItem:
    row = db.scalar(
        select(IepGoalItem)
        .join(IepPlan, IepGoalItem.iep_plan_id == IepPlan.id)
        .where(IepGoalItem.id == goal_id, IepPlan.case_id == case_id)
    )
    if row is None or row.retired_at is not None:
        raise ValueError(_MISSING_IEP_ITEM)
    return row


def _strategy_on_case(db: Session, strategy_id: int, case_id: int) -> IepStrategyItem:
    row = db.scalar(
        select(IepStrategyItem)
        .join(IepPlan, IepStrategyItem.iep_plan_id == IepPlan.id)
        .where(IepStrategyItem.id == strategy_id, IepPlan.case_id == case_id)
    )
    if row is None or row.retired_at is not None:
        raise ValueError(_MISSING_STRATEGY_ITEM)
    return row


def _as_entry_dict(item) -> dict:
    if isinstance(item, dict):
        return item
    return item.model_dump() if hasattr(item, "model_dump") else dict(item)


def _replace_goal_entries(db: Session, log: DailyLog, entries: list, created_by_user_id: int | None) -> None:
    case_id = _session_case_id(db, log)
    db.execute(delete(SessionGoalEntry).where(SessionGoalEntry.daily_log_id == log.id))
    seen: set[int] = set()
    for raw in entries:
        item = _as_entry_dict(raw)
        goal_id = int(item["goal_id"])
        if goal_id in seen:
            continue
        seen.add(goal_id)
        participation = str(item.get("participation") or "")
        support_level = str(item.get("support_level") or "")
        achievement = str(item.get("achievement") or "")
        if (
            participation not in PARTICIPATION_VALUES
            or support_level not in SUPPORT_LEVEL_VALUES
            or achievement not in ACHIEVEMENT_VALUES
        ):
            raise ValueError(_INCOMPLETE_TAP)
        _goal_on_case(db, goal_id, case_id)
        note = item.get("note")
        db.add(
            SessionGoalEntry(
                daily_log_id=log.id,
                goal_id=goal_id,
                participation=participation,
                support_level=support_level,
                achievement=achievement,
                note=(str(note).strip() or None) if note is not None else None,
                created_by_user_id=created_by_user_id,
            )
        )


def _replace_strategy_events(db: Session, log: DailyLog, events: list) -> None:
    case_id = _session_case_id(db, log)
    db.execute(delete(StrategyUseEvent).where(StrategyUseEvent.daily_log_id == log.id))
    seen: set[int] = set()
    for raw in events:
        item = _as_entry_dict(raw)
        strategy_id = int(item["strategy_id"])
        if strategy_id in seen:
            continue
        seen.add(strategy_id)
        response = str(item.get("response") or "")
        if response not in STRATEGY_RESPONSE_VALUES:
            raise ValueError(_INCOMPLETE_TAP)
        _strategy_on_case(db, strategy_id, case_id)
        note = item.get("note")
        db.add(
            StrategyUseEvent(
                daily_log_id=log.id,
                strategy_id=strategy_id,
                response=response,
                note=(str(note).strip() or None) if note is not None else None,
            )
        )


def _maybe_replace_evidence(db: Session, log: DailyLog, kwargs: dict, created_by_user_id: int | None = None) -> None:
    actor_id = kwargs.pop("created_by_user_id", created_by_user_id)
    goal_entries = kwargs.pop("goal_entries", None)
    strategy_events = kwargs.pop("strategy_events", None)
    if not settings.enable_structured_evidence:
        return
    if goal_entries is None and strategy_events is None:
        return
    if goal_entries is not None:
        _replace_goal_entries(db, log, goal_entries, actor_id)
    if strategy_events is not None:
        _replace_strategy_events(db, log, strategy_events)


def _goal_entry_read(row: SessionGoalEntry) -> dict:
    return {
        "id": row.id,
        "goal_id": row.goal_id,
        "participation": row.participation,
        "support_level": row.support_level,
        "achievement": row.achievement,
        "note": row.note,
    }


def _strategy_event_read(row: StrategyUseEvent) -> dict:
    return {
        "id": row.id,
        "strategy_id": row.strategy_id,
        "response": row.response,
        "note": row.note,
    }


def attach_structured_evidence(db: Session, reads: list[dict]) -> None:
    if not settings.enable_structured_evidence:
        return
    log_ids = [int(item["id"]) for item in reads if item.get("id")]
    if not log_ids:
        return
    goal_rows = db.scalars(select(SessionGoalEntry).where(SessionGoalEntry.daily_log_id.in_(log_ids))).all()
    strat_rows = db.scalars(select(StrategyUseEvent).where(StrategyUseEvent.daily_log_id.in_(log_ids))).all()
    by_log: dict[int, dict[str, list]] = {lid: {"goal_entries": [], "strategy_events": []} for lid in log_ids}
    for row in goal_rows:
        by_log[row.daily_log_id]["goal_entries"].append(_goal_entry_read(row))
    for row in strat_rows:
        by_log[row.daily_log_id]["strategy_events"].append(_strategy_event_read(row))
    for item in reads:
        payload = by_log.get(int(item["id"]))
        if not payload:
            continue
        item["goal_entries"] = payload["goal_entries"]
        item["strategy_events"] = payload["strategy_events"]


def create_daily_log(db: Session, **kwargs) -> tuple[DailyLog, bool]:
    """Create a daily log. Returns (log, created). Idempotent on session_id."""
    created_by_user_id = kwargs.pop("created_by_user_id", None)
    goal_entries = kwargs.pop("goal_entries", None)
    strategy_events = kwargs.pop("strategy_events", None)
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
    transition_match = therapist_transition_service.transition_day_for_session(
        db,
        case_id=session.case_id,
        therapist_user_id=session.therapist_user_id,
        scheduled_date=session.scheduled_date,
    )
    if transition_match:
        existing_transition_log = db.scalars(
            select(DailyLog)
            .join(TherapySession, TherapySession.id == DailyLog.session_id)
            .where(
                DailyLog.transition_day_id == transition_match[1].id,
                TherapySession.therapist_user_id == session.therapist_user_id,
            )
            .limit(1)
        ).first()
        if existing_transition_log:
            raise ValueError(
                "A transition log from this therapist already exists for this handover day."
            )
    log = DailyLog(
        session_id=kwargs["session_id"],
        transition_id=transition_match[0].id if transition_match else None,
        transition_day_id=transition_match[1].id if transition_match else None,
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
    log.session = session
    _maybe_replace_evidence(
        db,
        log,
        {
            "goal_entries": goal_entries,
            "strategy_events": strategy_events,
            "created_by_user_id": created_by_user_id,
        },
        created_by_user_id=created_by_user_id,
    )
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

    _maybe_replace_evidence(db, log, kwargs, created_by_user_id=therapist_user_id)
    _apply_log_field_updates(log, kwargs)
    db.flush()
    return log


def _apply_log_field_updates(log: DailyLog, kwargs: dict) -> None:
    for field in ("session_notes", "activities_done", "goals_addressed", "observations", "follow_ups", "parent_notes", "late_reason"):
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

    _maybe_replace_evidence(db, log, kwargs, created_by_user_id=therapist_user_id)
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


def attach_mentor_review_meta(
    db: Session,
    reads: list[dict],
    viewer=None,
) -> None:
    """Fill mentor reviewer names and can_mark_mentor_reviewed for the viewer."""
    from app.models.user import User
    from app.services.mentor_scope_service import can_mark_log_mentor_reviewed, is_mentor_of_therapist

    reviewer_ids = {
        item.get("mentor_reviewed_by_user_id")
        for item in reads
        if item.get("mentor_reviewed_by_user_id")
    }
    names: dict[int, str] = {}
    if reviewer_ids:
        names = dict(
            db.execute(select(User.id, User.full_name).where(User.id.in_(reviewer_ids))).all()
        )

    for item in reads:
        rid = item.get("mentor_reviewed_by_user_id")
        item["mentor_reviewed_by_name"] = names.get(rid) if rid else None
        item["mentor_reviewed"] = bool(item.get("mentor_reviewed_at"))
        can_mark = False
        if viewer is not None and not item.get("mentor_reviewed_at"):
            therapist_id = item.get("therapist_user_id")
            if therapist_id and is_mentor_of_therapist(db, viewer.id, therapist_id):
                can_mark = can_mark_log_mentor_reviewed(
                    db,
                    viewer,
                    case=None,
                    therapist_user_id=therapist_id,
                    already_reviewed=False,
                )
        item["can_mark_mentor_reviewed"] = can_mark


def log_to_read(
    log: DailyLog,
    include_clinical: bool = True,
    *,
    therapist_name: str | None = None,
) -> dict:
    session = log.session
    case = session.case if session and getattr(session, "case", None) else None
    data = {
        "id": log.id,
        "session_id": log.session_id,
        "transition_id": log.transition_id,
        "transition_day_id": log.transition_day_id,
        "is_transition_log": bool(log.transition_id),
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
        "mentor_reviewed": bool(getattr(log, "mentor_reviewed_at", None)),
        "mentor_reviewed_at": ensure_utc_aware(getattr(log, "mentor_reviewed_at", None)),
        "mentor_reviewed_by_user_id": getattr(log, "mentor_reviewed_by_user_id", None),
        "mentor_reviewed_by_name": None,
        "can_mark_mentor_reviewed": False,
        "can_edit": can_therapist_edit_log(log),
        "can_resubmit": is_log_resubmittable(log),
        "resubmitted_at": ensure_utc_aware(log.resubmitted_at),
        "editable_until": log_editable_until(log),
    }
    if session:
        data["scheduled_date"] = session.scheduled_date
        data["therapist_user_id"] = session.therapist_user_id
        data["therapist_name"] = therapist_name
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
    if log.transition_id:
        data["source"] = "transition"
        transition = log.transition
        if transition and session:
            data["transition_role"] = (
                "outgoing"
                if session.therapist_user_id == transition.outgoing_therapist_user_id
                else "incoming"
            )
            transition_dates = sorted(
                date.fromisoformat(str(value)[:10])
                for value in (transition.transition_dates or [])
            )
            data["transition_day_count"] = len(transition_dates)
            if session.scheduled_date in transition_dates:
                data["transition_day_number"] = transition_dates.index(session.scheduled_date) + 1
        status = log.approval_status.value if hasattr(log.approval_status, "value") else str(log.approval_status)
        if status == "PENDING":
            data["status_label"] = "Transition log — pending review"
        elif status == "APPROVED":
            data["status_label"] = "Transition log — approved"
        elif status == "REJECTED":
            data["status_label"] = "Transition log — rejected"
    elif log.late_addition:
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


def delete_log_for_absence_replacement(
    db: Session,
    log: DailyLog,
    therapist_user_id: int,
) -> None:
    """Remove an unsubmitted/rejected log so the visit can be voided and child absence filed."""
    session = log.session or db.get(TherapySession, log.session_id)
    if not session or session.therapist_user_id != therapist_user_id:
        raise ValueError("Access denied")
    status = log.approval_status
    if isinstance(status, str):
        try:
            status = LogApprovalStatus(status)
        except ValueError:
            pass
    if status == LogApprovalStatus.APPROVED:
        raise ValueError(
            "This session log was already approved — contact your case manager if you need a correction."
        )
    if status not in (LogApprovalStatus.PENDING, LogApprovalStatus.REJECTED):
        raise ValueError("This session log cannot be removed this way")

    from app.models.ledger_billing import BillableStatus, BillingLedger

    has_invoiced = db.scalars(
        select(BillingLedger).where(
            BillingLedger.session_id == session.id,
            BillingLedger.billable_status == BillableStatus.INVOICED,
        )
    ).first()
    if has_invoiced:
        raise ValueError("Billing records exist for this session — contact your case manager")

    db.execute(delete(SessionGoalEntry).where(SessionGoalEntry.daily_log_id == log.id))
    db.execute(delete(StrategyUseEvent).where(StrategyUseEvent.daily_log_id == log.id))
    db.execute(
        delete(DocumentComment).where(
            DocumentComment.entity_type == DocumentEntityType.DAILY_LOG,
            DocumentComment.entity_id == log.id,
        )
    )
    db.delete(log)
    db.flush()
