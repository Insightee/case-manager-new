"""Deterministic data preview for Insights tab — no AI."""

from __future__ import annotations

import hashlib
import json
from calendar import monthrange
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.case import Case
from app.models.clinical_evidence import SessionGoalEntry, StrategyUseEvent
from app.models.daily_log import DailyLog
from app.models.goal_repository import RepositoryItemStatus
from app.models.iep_plan import IepPlanStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.services import goal_repository_service as repo_svc
from app.services import iep_plan_service as iep_svc
from app.services.clinical_workbench_service import ACTIVE_IEP_STATUSES, _parse_iep_goals

ACTIVE_IEP = ACTIVE_IEP_STATUSES


def _month_bounds(month: str) -> tuple[date, date]:
    year, mo = int(month[:4]), int(month[5:7])
    last = monthrange(year, mo)[1]
    return date(year, mo, 1), date(year, mo, last)


def _input_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def build_data_preview(db: Session, case_id: int, month: str) -> dict[str, Any]:
    case = db.get(Case, case_id)
    if not case:
        raise ValueError("Case not found")

    start, end = _month_bounds(month)
    sessions = db.scalars(
        select(TherapySession)
        .where(
            TherapySession.case_id == case_id,
            TherapySession.status == SessionStatus.COMPLETED,
            TherapySession.scheduled_date >= start,
            TherapySession.scheduled_date <= end,
        )
        .options(selectinload(TherapySession.daily_log))
    ).all()

    logs_submitted = 0
    logs_missing_details = 0
    for sess in sessions:
        log = sess.daily_log
        if not log or not log.submitted_at:
            continue
        logs_submitted += 1
        goal_entries = db.scalars(
            select(SessionGoalEntry).where(SessionGoalEntry.daily_log_id == log.id)
        ).all()
        has_strategy = bool(
            db.scalars(select(StrategyUseEvent).where(StrategyUseEvent.daily_log_id == log.id)).first()
        )
        if not goal_entries and not (log.goals_addressed or "").strip():
            logs_missing_details += 1
        elif goal_entries and not has_strategy:
            logs_missing_details += 1

    plan = iep_svc.get_latest_plan(db, case_id)
    iep_goals = _parse_iep_goals(plan)
    active_goals_count = len(iep_goals) if plan and plan.status in ACTIVE_IEP else len(iep_goals)

    strategy_labels: set[str] = set()
    log_ids = [
        s.daily_log.id
        for s in sessions
        if s.daily_log and s.daily_log.submitted_at
    ]
    if log_ids:
        for ev in db.scalars(select(StrategyUseEvent).where(StrategyUseEvent.daily_log_id.in_(log_ids))).all():
            if ev.strategy_label:
                strategy_labels.add(ev.strategy_label)

    strategy_candidates = repo_svc.list_strategy_candidates(db, case_id)
    custom_strategies_count = sum(
        1
        for s in strategy_candidates
        if s["status"] in (RepositoryItemStatus.LOCAL.value, RepositoryItemStatus.CANDIDATE.value)
    )

    parent_input_status = "unknown"
    school_input_status = "unknown"
    # TODO: wire parent/school input tables when available

    preview_core = {
        "case_id": case_id,
        "month": month,
        "sessions_available": len(sessions),
        "logs_submitted": logs_submitted,
        "logs_missing_details": logs_missing_details,
        "active_goals_count": active_goals_count,
        "strategies_used_count": len(strategy_labels),
        "custom_strategies_count": custom_strategies_count,
        "parent_input_status": parent_input_status,
        "school_input_status": school_input_status,
    }

    existing_snapshot_id = None
    try:
        from app.models.clinical_snapshot import ClinicalSnapshot

        ih = _input_hash(preview_core)
        snap = db.scalars(
            select(ClinicalSnapshot)
            .where(
                ClinicalSnapshot.case_id == case_id,
                ClinicalSnapshot.month == month,
                ClinicalSnapshot.input_hash == ih,
            )
            .order_by(ClinicalSnapshot.id.desc())
            .limit(1)
        ).first()
        if snap:
            existing_snapshot_id = snap.id
    except Exception:
        pass

    return {
        **preview_core,
        "existing_snapshot_id": existing_snapshot_id,
        "input_hash": _input_hash(preview_core),
    }
