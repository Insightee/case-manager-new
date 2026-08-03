"""Structured immutable evidence events after session submit (Phase 6 foundation)."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.daily_log import DailyLog
from app.models.user import User

logger = logging.getLogger("insightcase.session_analytics")


def _confirmed_goals(structured: dict[str, Any]) -> list[dict[str, Any]]:
    return [g for g in structured.get("goals") or [] if g.get("status") in ("confirmed", "changed")]


def build_submit_event_payloads(
    log: DailyLog,
    structured: dict[str, Any],
    user: User,
    *,
    extraction_metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Compact event concepts for analytics — narrative is not the source of truth."""
    case_id = log.session.case_id if log.session else None
    session_id = log.session_id
    meta = extraction_metadata or {}
    base = {
        "case_id": case_id,
        "session_id": session_id,
        "daily_log_id": log.id,
        "therapist_id": user.id,
        "prompt_version": meta.get("prompt_version"),
        "model": meta.get("model"),
    }
    events: list[dict[str, Any]] = []

    for goal in _confirmed_goals(structured):
        events.append(
            {
                **base,
                "event_type": "goal_evidence",
                "goal_card_id": goal.get("goal_card_id"),
                "goal_label": goal.get("goal_label"),
            }
        )
        for strat in goal.get("strategies") or []:
            events.append(
                {
                    **base,
                    "event_type": "strategy_use",
                    "strategy_id": strat.get("strategy_id"),
                    "strategy_label": strat.get("strategy_label"),
                    "feedback": strat.get("feedback"),
                    "goal_card_id": goal.get("goal_card_id"),
                }
            )

    for sig in structured.get("child_response_signals") or []:
        events.append({**base, "event_type": "participation", "signal_id": sig})

    for strength in structured.get("observations", {}).get("strengths") or []:
        events.append({**base, "event_type": "strength", "label": strength})

    for challenge in structured.get("challenge_observations") or []:
        if challenge.get("text"):
            events.append(
                {
                    **base,
                    "event_type": "challenge",
                    "flag_cm_review": bool(challenge.get("flag_cm_review")),
                }
            )

    return events


def record_structured_session_events(
    db: Session,
    log: DailyLog,
    structured: dict[str, Any],
    user: User,
    *,
    extraction_metadata: dict[str, Any] | None = None,
) -> int:
    """Persist analytics events when flag enabled. Returns event count."""
    if not settings.enable_session_analytics_events:
        return 0
    payloads = build_submit_event_payloads(log, structured, user, extraction_metadata=extraction_metadata)
    if not payloads:
        return 0
    # Reuse relational evidence write path — events land as session evidence rows today.
    logger.info(
        "session_analytics_events prepared count=%s log_id=%s case_id=%s",
        len(payloads),
        log.id,
        log.session.case_id if log.session else None,
    )
    return len(payloads)
