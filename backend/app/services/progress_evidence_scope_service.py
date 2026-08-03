"""Review-period evidence scoping for progress reports — approved logs only."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.clinical_evidence import SessionGoalEntry, StrategyUseEvent
from app.models.clinical_report import ClinicalReport, ClinicalReportSection, ClinicalReportStatus, ClinicalReportType
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.session import Session as TherapySession
from app.services.progress_status_rules import suggest_goal_status, suggest_strategy_status


@dataclass
class EvidenceScope:
    review_period_start: date
    review_period_end: date
    evidence_cutoff_at: datetime
    source_iep_report_id: int | None = None
    source_iep_version_id: int | None = None
    iep_goals: list[dict] = field(default_factory=list)


def _json_loads(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def _month_key_from_report(report: ClinicalReport) -> str | None:
    meta = _json_loads(report.metadata_json)
    return meta.get("month")


def month_overlaps_period(month_key: str, period_start: date, period_end: date) -> bool:
    try:
        month_date = date.fromisoformat(f"{month_key}-01")
    except ValueError:
        return False
    month_end = date(month_date.year, month_date.month, 28)
    while True:
        try:
            month_end = month_end.replace(day=month_end.day + 1)
        except ValueError:
            break
    return month_date <= period_end and month_end >= period_start


def parse_scope_from_metadata(report: ClinicalReport) -> EvidenceScope:
    meta = _json_loads(report.metadata_json)
    start_raw = meta.get("review_period_start") or meta.get("period_start")
    end_raw = meta.get("review_period_end") or meta.get("period_end")
    if not start_raw or not end_raw:
        raise ValueError("Progress report missing review period metadata")
    period_start = date.fromisoformat(str(start_raw))
    period_end = date.fromisoformat(str(end_raw))
    cutoff_raw = meta.get("evidence_cutoff_at")
    if cutoff_raw:
        cutoff = datetime.fromisoformat(str(cutoff_raw).replace("Z", "+00:00"))
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=timezone.utc)
    else:
        cutoff = datetime.combine(period_end, time(23, 59, 59), tzinfo=timezone.utc)
    return EvidenceScope(
        review_period_start=period_start,
        review_period_end=period_end,
        evidence_cutoff_at=cutoff,
        source_iep_report_id=meta.get("source_iep_report_id"),
        source_iep_version_id=meta.get("source_iep_version_id"),
    )


def resolve_pinned_iep_snapshot(db: Session, case_id: int, *, existing: EvidenceScope | None = None) -> EvidenceScope:
    if existing and existing.source_iep_report_id and existing.iep_goals:
        return existing
    iep_report = db.scalar(
        select(ClinicalReport)
        .where(
            ClinicalReport.case_id == case_id,
            ClinicalReport.report_type == ClinicalReportType.IEP.value,
            ClinicalReport.status.in_((ClinicalReportStatus.APPROVED.value, ClinicalReportStatus.LOCKED.value)),
            ClinicalReport.archived_at.is_(None),
        )
        .order_by(ClinicalReport.approved_at.desc(), ClinicalReport.id.desc())
    )
    goals: list[dict] = []
    iep_id = None
    version_id = None
    if iep_report:
        iep_id = iep_report.id
        version_id = iep_report.current_version_id
        sec = db.scalar(
            select(ClinicalReportSection).where(
                ClinicalReportSection.report_id == iep_report.id,
                ClinicalReportSection.section_key == "goals_plan",
            )
        )
        if sec and sec.structured_data_json:
            plan = _json_loads(sec.structured_data_json)
            for g in plan.get("goals") or []:
                if str(g.get("lifecycle_status") or g.get("status") or "active").lower() in {"archived", "removed"}:
                    continue
                goals.append({
                    "goal_id": g.get("iep_goal_id") or g.get("source_goal_id"),
                    "label": g.get("title") or g.get("goal_statement") or "Goal",
                    "domain_key": g.get("domain"),
                    "iep_goal_id": g.get("iep_goal_id"),
                })
    base = existing or EvidenceScope(
        review_period_start=date.today(),
        review_period_end=date.today(),
        evidence_cutoff_at=datetime.now(timezone.utc),
    )
    base.source_iep_report_id = iep_id
    base.source_iep_version_id = version_id
    base.iep_goals = goals
    return base


def list_scoped_approved_logs(db: Session, case_id: int, scope: EvidenceScope) -> list[DailyLog]:
    rows = db.scalars(
        select(DailyLog)
        .join(TherapySession, DailyLog.session_id == TherapySession.id)
        .where(
            TherapySession.case_id == case_id,
            DailyLog.submitted_at.isnot(None),
            DailyLog.approval_status == LogApprovalStatus.APPROVED.value,
            TherapySession.scheduled_date >= scope.review_period_start,
            TherapySession.scheduled_date <= scope.review_period_end,
            DailyLog.submitted_at <= scope.evidence_cutoff_at,
        )
        .order_by(TherapySession.scheduled_date.asc())
    ).all()
    return list(rows)


def list_scoped_monthly_reports(db: Session, case_id: int, scope: EvidenceScope) -> list[ClinicalReport]:
    approved = []
    for report in db.scalars(
        select(ClinicalReport).where(
            ClinicalReport.case_id == case_id,
            ClinicalReport.report_type == ClinicalReportType.MONTHLY.value,
            ClinicalReport.status.in_((ClinicalReportStatus.APPROVED.value, ClinicalReportStatus.LOCKED.value)),
            ClinicalReport.archived_at.is_(None),
        )
    ).all():
        month_key = _month_key_from_report(report)
        if month_key and month_overlaps_period(month_key, scope.review_period_start, scope.review_period_end):
            approved.append(report)
    return approved


def _compute_evidence_strength(session_count: int, achievement_scores: list[int]) -> str:
    if session_count <= 0:
        return "weak"
    avg = sum(achievement_scores) / len(achievement_scores) if achievement_scores else 0
    if session_count >= 5 or avg >= 3:
        return "strong_operational"
    if session_count >= 2 or avg >= 2:
        return "moderate"
    return "weak"


def _compute_latest_trend(scores: list[int]) -> str | None:
    if len(scores) < 2:
        return None
    if scores[-1] < scores[-2]:
        return "needs_support"
    if scores[-1] > scores[-2]:
        return "improving"
    return "stable"


def aggregate_goal_metrics(
    db: Session,
    scope: EvidenceScope,
    scoped_logs: list[DailyLog],
    iep_goals: list[dict],
) -> tuple[list[dict], list[dict]]:
    log_ids = [log.id for log in scoped_logs]
    session_dates = {
        log.id: log.session.scheduled_date.isoformat()
        for log in scoped_logs
        if log.session and log.session.scheduled_date
    }
    goal_entries: list[SessionGoalEntry] = []
    if log_ids:
        goal_entries = list(
            db.scalars(select(SessionGoalEntry).where(SessionGoalEntry.daily_log_id.in_(log_ids))).all()
        )
    strategy_events: list[StrategyUseEvent] = []
    if log_ids:
        strategy_events = list(
            db.scalars(select(StrategyUseEvent).where(StrategyUseEvent.daily_log_id.in_(log_ids))).all()
        )

    by_goal: dict[str, dict] = {}
    for g in iep_goals:
        gid = str(g.get("goal_id") or g.get("iep_goal_id") or g.get("label"))
        by_goal[gid] = {
            "goal_id": g.get("goal_id") or g.get("iep_goal_id"),
            "label": g.get("label"),
            "domain_key": g.get("domain_key"),
            "sessions_addressed": 0,
            "session_log_ids": [],
            "session_dates": [],
            "environments": set(),
            "strategies_used": set(),
            "achievement_scores": [],
            "evidence_event_count": 0,
        }

    orphan_entries: dict[str, dict] = {}
    for entry in goal_entries:
        gid = str(entry.goal_card_id or entry.goal_label)
        bucket = by_goal.get(gid)
        if not bucket:
            for key, g in by_goal.items():
                if g["label"] == entry.goal_label:
                    bucket = g
                    gid = key
                    break
        if not bucket:
            bucket = orphan_entries.setdefault(gid, {
                "goal_id": entry.goal_card_id,
                "label": entry.goal_label,
                "domain_key": entry.domain_key,
                "sessions_addressed": 0,
                "session_log_ids": [],
                "session_dates": [],
                "environments": set(),
                "strategies_used": set(),
                "achievement_scores": [],
                "evidence_event_count": 0,
            })
        if entry.daily_log_id not in bucket["session_log_ids"]:
            bucket["sessions_addressed"] += 1
            bucket["session_log_ids"].append(entry.daily_log_id)
            if entry.daily_log_id in session_dates:
                bucket["session_dates"].append(session_dates[entry.daily_log_id])
        bucket["evidence_event_count"] += 1
        if entry.goal_achievement_score is not None:
            bucket["achievement_scores"].append(entry.goal_achievement_score)
        env_json = _json_loads(entry.core_environments_json)
        for env in env_json.get("environments") or env_json.get("items") or []:
            if env:
                bucket["environments"].add(str(env))

    for event in strategy_events:
        for bucket in list(by_goal.values()) + list(orphan_entries.values()):
            if event.goal_card_id and bucket.get("goal_id") == event.goal_card_id:
                bucket["strategies_used"].add(event.strategy_label)
            elif event.goal_entry_id:
                pass
        if event.environment:
            for bucket in list(by_goal.values()) + list(orphan_entries.values()):
                if event.strategy_label in bucket["strategies_used"] or not bucket["strategies_used"]:
                    bucket["environments"].add(event.environment)

    for event in strategy_events:
        for bucket in list(by_goal.values()) + list(orphan_entries.values()):
            if event.goal_card_id and bucket.get("goal_id") == event.goal_card_id:
                bucket["strategies_used"].add(event.strategy_label)

    goal_metrics = []
    for bucket in list(by_goal.values()) + list(orphan_entries.values()):
        strength = _compute_evidence_strength(bucket["sessions_addressed"], bucket["achievement_scores"])
        trend = _compute_latest_trend(bucket["achievement_scores"])
        metrics = {
            "goal_id": bucket["goal_id"],
            "label": bucket["label"],
            "domain_key": bucket.get("domain_key"),
            "sessions_addressed": bucket["sessions_addressed"],
            "evidence_strength": strength,
            "latest_trend": trend,
            "strategies_used": sorted(bucket["strategies_used"]),
            "environments": sorted(bucket["environments"]),
            "session_log_ids": bucket["session_log_ids"],
            "session_dates": bucket["session_dates"],
            "evidence_event_count": bucket["evidence_event_count"],
        }
        metrics["suggested_status"] = suggest_goal_status(metrics)
        goal_metrics.append(metrics)

    strategy_by_label: dict[str, dict] = {}
    for event in strategy_events:
        label = event.strategy_label
        bucket = strategy_by_label.setdefault(label, {
            "label": label,
            "use_count": 0,
            "feedback_distribution": {},
            "linked_goal_ids": set(),
        })
        bucket["use_count"] += 1
        fb = (event.strategy_feedback or "UNKNOWN").upper()
        bucket["feedback_distribution"][fb] = bucket["feedback_distribution"].get(fb, 0) + 1
        if event.goal_card_id:
            bucket["linked_goal_ids"].add(event.goal_card_id)

    strategy_metrics = []
    for bucket in strategy_by_label.values():
        bucket["linked_goal_ids"] = sorted(bucket["linked_goal_ids"])
        bucket["suggested_status"] = suggest_strategy_status(bucket)
        strategy_metrics.append(bucket)
    return goal_metrics, strategy_metrics


def build_evidence_summary_for_goal(goal_metrics: dict, monthly_ids: list[int]) -> dict:
    sessions = int(goal_metrics.get("sessions_addressed") or 0)
    warning = None
    if sessions <= 0:
        warning = "No approved sessions in period"
    elif goal_metrics.get("evidence_event_count", 0) == 0:
        warning = "Goal on IEP but no structured entries"
    return {
        "session_count": sessions,
        "evidence_event_count": int(goal_metrics.get("evidence_event_count") or 0),
        "monthly_report_ids": monthly_ids,
        "environments": goal_metrics.get("environments") or [],
        "strategies_used": goal_metrics.get("strategies_used") or [],
        "missing_evidence_warning": warning,
        "session_dates": goal_metrics.get("session_dates") or [],
    }
