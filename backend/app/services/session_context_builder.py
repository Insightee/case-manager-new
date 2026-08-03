"""Compact session interpretation context for Voice Session Log V2.

Layer 2 context compression: ID tokens + structural flags over prose.
Targets ~80–95% reduction vs raw session history narratives.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.daily_log import DailyLog
from app.models.session import Session as TherapySession
from app.services.session_log_extraction_service import build_case_context

MAX_RECENT_SUMMARY_CHARS = 200
MAX_EVIDENCE_GAPS = 6


def _compact_structured_summary(raw_json: str | None) -> dict[str, Any] | None:
    if not raw_json:
        return None
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        return None
    goals = data.get("goals") or []
    confirmed = [g for g in goals if g.get("status") in ("confirmed", "changed")]
    return {
        "session_id": data.get("session_id"),
        "confirmed_goal_count": len(confirmed),
        "goal_labels": [g.get("goal_label", "")[:80] for g in confirmed[:4]],
        "story_excerpt": (data.get("todays_story") or "")[:MAX_RECENT_SUMMARY_CHARS],
        "participation_signals": (data.get("child_response_signals") or [])[:4],
    }


def _recent_confirmed_sessions(
    db: Session,
    *,
    case_id: int,
    exclude_session_id: int | None,
    limit: int,
) -> list[dict[str, Any]]:
    stmt = (
        select(DailyLog, TherapySession)
        .join(TherapySession, DailyLog.session_id == TherapySession.id)
        .where(
            TherapySession.case_id == case_id,
            DailyLog.structured_session_json.is_not(None),
        )
        .order_by(DailyLog.submitted_at.desc().nullslast(), DailyLog.created_at.desc())
        .limit(limit + 1)
    )
    rows = db.execute(stmt).all()
    out: list[dict[str, Any]] = []
    for log, session in rows:
        if exclude_session_id and session.id == exclude_session_id:
            continue
        summary = _compact_structured_summary(log.structured_session_json)
        if summary:
            out.append(summary)
        if len(out) >= limit:
            break
    return out


def _deterministic_evidence_gaps(
    case_context: dict[str, Any],
    recent_sessions: list[dict[str, Any]],
) -> list[str]:
    gaps: list[str] = []
    active_goals = case_context.get("goals") or []
    if not active_goals:
        gaps.append("No active IEP goals on file for this case")
    recent_goal_labels: set[str] = set()
    for sess in recent_sessions:
        for label in sess.get("goal_labels") or []:
            if label:
                recent_goal_labels.add(label.lower())
    for goal in active_goals[:8]:
        label = (goal.get("label") or "").strip()
        if label and label.lower() not in recent_goal_labels:
            gaps.append(f"No recent confirmed evidence for: {label[:60]}")
    if not recent_sessions:
        gaps.append("No prior structured session logs for longitudinal comparison")
    return gaps[:MAX_EVIDENCE_GAPS]


def build_session_interpretation_context(
    db: Session,
    case_id: int,
    *,
    session_id: int | None = None,
    selected_goal_card_ids: Optional[list[int]] = None,
) -> dict[str, Any]:
    """Full compact context for Clinical Language Engine interpretation."""
    case_context = build_case_context(db, case_id, selected_goal_card_ids=selected_goal_card_ids)
    limit = max(1, min(settings.session_recent_context_limit, 10))
    recent = _recent_confirmed_sessions(
        db,
        case_id=case_id,
        exclude_session_id=session_id,
        limit=limit,
    )
    environment: str | None = None
    if session_id:
        session = db.get(TherapySession, session_id)
        if session and hasattr(session, "location_type"):
            environment = getattr(session, "location_type", None)

    evidence_gaps = _deterministic_evidence_gaps(case_context, recent)

    return {
        **case_context,
        "case_id": case_id,
        "session_id": session_id,
        "environment": environment,
        "recent_confirmed_sessions": recent,
        "evidence_gaps": evidence_gaps,
        "parent_priorities": [],
        "observation_findings": [],
    }
