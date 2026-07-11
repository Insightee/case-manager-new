"""Deterministic monthly evidence compiler from materialized clinical events."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.clinical_report import ClinicalReport
from app.models.monthly_report_evidence_snapshot import MonthlyReportEvidenceSnapshot
from app.models.report import MonthlyReport
from app.models.session import Session as TherapySession, SessionStatus
from app.services import clinical_evidence_event_service as cee_svc
from app.services.report_log_query import submitted_logs_for_report_month

COMPILER_VERSION = "1.0.0"


def _hash_sources(parts: list[str]) -> str:
    raw = "|".join(sorted(parts))
    return hashlib.sha256(raw.encode()).hexdigest()


def compile_monthly_evidence_snapshot(
    db: Session,
    *,
    case_id: int,
    month: str,
    report_id: int | None = None,
    clinical_report_id: int | None = None,
    user_id: int | None = None,
    force: bool = False,
) -> dict[str, Any]:
    events = cee_svc.materialize_for_case_month(db, case_id, month)
    logs = []
    if report_id:
        report = db.get(MonthlyReport, report_id)
        if report:
            logs = submitted_logs_for_report_month(db, report)
    elif clinical_report_id:
        cr = db.get(ClinicalReport, clinical_report_id)
        if cr:
            from app.services.report_engine_service import _report_month_from_metadata

            month = _report_month_from_metadata(cr) or month

    log_ids = [str(log.id) for log in logs]
    source_parts = log_ids + [str(e.get("identity", {}).get("evidence_event_id")) for e in events]
    source_hash = _hash_sources(source_parts)

    if not force:
        existing = db.scalars(
            select(MonthlyReportEvidenceSnapshot)
            .where(
                MonthlyReportEvidenceSnapshot.case_id == case_id,
                MonthlyReportEvidenceSnapshot.month == month,
                MonthlyReportEvidenceSnapshot.source_hash == source_hash,
            )
            .order_by(MonthlyReportEvidenceSnapshot.id.desc())
        ).first()
        if existing:
            return json.loads(existing.evidence_json)

    scheduled = db.scalars(
        select(TherapySession).where(
            TherapySession.case_id == case_id,
            TherapySession.scheduled_date >= f"{month}-01",
            TherapySession.scheduled_date < _next_month(month),
        )
    ).all()

    sessions_block = {
        "scheduled_count": len(scheduled),
        "completed_count": sum(1 for s in scheduled if s.status == SessionStatus.COMPLETED),
        "child_absent_count": sum(1 for s in scheduled if getattr(s, "attendance_status", None) == "ABSENT"),
        "cancelled_count": sum(1 for s in scheduled if s.status == SessionStatus.CANCELLED),
        "missing_log_count": sum(
            1 for s in scheduled if s.status == SessionStatus.COMPLETED and not getattr(s, "has_daily_log", False)
        ),
    }

    goals_map: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "goal_id": None,
            "goal_title": "",
            "goal_status": "active",
            "addressed_session_count": 0,
            "evidence_event_count": 0,
            "environments": set(),
            "strategies_used": {},
            "adaptations": [],
            "participation_patterns": [],
            "support_level_patterns": [],
            "barriers": [],
            "therapist_next_steps": [],
            "evidence_gaps": [],
            "source_log_ids": set(),
        }
    )

    for ev in events:
        gid = str(ev.get("goal_linkage", {}).get("goal_entry_id") or ev.get("goal_linkage", {}).get("goal_title"))
        g = goals_map[gid]
        g["goal_id"] = ev.get("goal_linkage", {}).get("goal_entry_id")
        g["goal_title"] = ev.get("goal_linkage", {}).get("goal_title") or g["goal_title"]
        g["evidence_event_count"] += 1
        log_id = ev.get("identity", {}).get("daily_log_id")
        if log_id:
            g["source_log_ids"].add(log_id)
        env = ev.get("context", {}).get("environment_fit")
        if env:
            g["environments"].add(env)
        for b in ev.get("context", {}).get("barrier_type") or []:
            g["barriers"].append(b)
        pq = ev.get("support_and_response", {}).get("participation_quality")
        if pq:
            g["participation_patterns"].append(pq)
        interp = ev.get("therapist_view", {}).get("therapist_interpretation")
        if interp:
            g["therapist_next_steps"].append(interp)
        strat = ev.get("strategy_linkage", {}) or {}
        sid = strat.get("strategy_id") or strat.get("strategy_title")
        if sid:
            bucket = g["strategies_used"].setdefault(
                str(sid),
                {
                    "strategy_id": strat.get("strategy_id"),
                    "strategy_name": strat.get("strategy_title"),
                    "use_count": 0,
                    "adapted_count": 0,
                    "response_patterns": [],
                    "support_patterns": [],
                    "parent_safe_summary": None,
                },
            )
            bucket["use_count"] += 1
            if strat.get("adaptation_type"):
                bucket["adapted_count"] += 1
                g["adaptations"].extend(strat.get("adaptation_type") or [])
            cr = ev.get("support_and_response", {}).get("child_response")
            if cr:
                bucket["response_patterns"].append(cr)
        if not ev.get("support_and_response", {}).get("child_response") and strat.get("strategy_title"):
            g["evidence_gaps"].append("strategy_without_child_response")

    goals_out = []
    for g in goals_map.values():
        g["environments"] = sorted(g["environments"])
        g["source_log_ids"] = sorted(g["source_log_ids"])
        g["addressed_session_count"] = len(g["source_log_ids"])
        g["strategies_used"] = list(g["strategies_used"].values())
        if g["addressed_session_count"] == 0:
            g["evidence_gaps"].append("goal_not_addressed_in_month")
        goals_out.append(g)

    quality_flags = []
    if sessions_block["missing_log_count"]:
        quality_flags.append({"code": "missing_logs", "message": "Some completed visits are missing logs"})
    if not goals_out:
        quality_flags.append({"code": "no_goal_evidence", "message": "No structured goal evidence this month"})

    session_projections = []
    if logs:
        from app.services import session_evidence_projection_service as sep_svc

        for log in logs:
            session_projections.append(sep_svc.build_session_evidence_projection(db, log).to_dict())

    payload = {
        "case_id": case_id,
        "month": month,
        "sessions": sessions_block,
        "goals": goals_out,
        "session_projections": session_projections,
        "parent_inputs": [],
        "uploads": [],
        "quality_flags": quality_flags,
        "compiler_version": COMPILER_VERSION,
        "source_hash": source_hash,
    }

    snap = MonthlyReportEvidenceSnapshot(
        report_id=report_id,
        clinical_report_id=clinical_report_id,
        case_id=case_id,
        month=month,
        evidence_json=json.dumps(payload, default=str),
        source_hash=source_hash,
        compiler_version=COMPILER_VERSION,
        generated_by_user_id=user_id,
    )
    db.add(snap)
    db.commit()
    return payload


def _next_month(month: str) -> str:
    y, m = month.split("-")
    mi = int(m)
    yi = int(y)
    if mi == 12:
        return f"{yi + 1}-01-01"
    return f"{yi}-{mi + 1:02d}-01"


def get_latest_snapshot(db: Session, case_id: int, month: str) -> dict[str, Any] | None:
    row = db.scalars(
        select(MonthlyReportEvidenceSnapshot)
        .where(MonthlyReportEvidenceSnapshot.case_id == case_id, MonthlyReportEvidenceSnapshot.month == month)
        .order_by(MonthlyReportEvidenceSnapshot.id.desc())
    ).first()
    if not row:
        return None
    return json.loads(row.evidence_json)
