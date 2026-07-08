"""Session Log Insights & Evidence — the 3 fixed "what's helping / needs adapting / concerns" cards."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.clinical_evidence import StrategyUseEvent
from app.models.daily_log import DailyLog
from app.models.incident import Incident
from app.models.session import Session as TherapySession
from app.services.insights.helpers import combined_source_line, make_insight

NEEDS_ADAPTING_FEEDBACK = ("NEEDS_ADAPTATION", "NOT_HELPFUL", "CHILD_REJECTED")


def _case_log_ids(db: Session, case_id: int) -> list[int]:
    return list(
        db.scalars(
            select(DailyLog.id).join(TherapySession, DailyLog.session_id == TherapySession.id).where(
                TherapySession.case_id == case_id
            )
        ).all()
    )


def build_evidence_cards(db: Session, case_id: int) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]], list[dict]]:
    log_ids = _case_log_ids(db, case_id)
    events: list[StrategyUseEvent] = []
    if log_ids:
        events = list(
            db.scalars(
                select(StrategyUseEvent)
                .where(StrategyUseEvent.daily_log_id.in_(log_ids))
                .order_by(StrategyUseEvent.id.desc())
            ).all()
        )

    helpful_events = [e for e in events if e.strategy_feedback == "HELPFUL"]
    adapting_events = [e for e in events if e.strategy_feedback in NEEDS_ADAPTING_FEEDBACK]
    rejected_events = [e for e in events if e.strategy_feedback == "CHILD_REJECTED"]

    incidents = list(db.scalars(select(Incident).where(Incident.case_id == case_id)).all())

    helping_note = next((e.outcome_note or e.short_note for e in helpful_events if (e.outcome_note or e.short_note)), None)
    helping_strategy = helpful_events[0].strategy_label if helpful_events else None
    helping_summary = (
        f"{helping_strategy} appeared helpful during recent sessions — {helping_note.strip()}"
        if helping_note and helping_strategy
        else (f"{helping_strategy} appeared helpful during recent sessions." if helping_strategy else "Not enough evidence yet to identify a consistently helpful support.")
    )

    adapting_note = next((e.outcome_note or e.short_note for e in adapting_events if (e.outcome_note or e.short_note)), None)
    adapting_strategy = adapting_events[0].strategy_label if adapting_events else None
    adapting_summary = (
        f"{adapting_strategy} may need adapting — {adapting_note.strip()}"
        if adapting_note and adapting_strategy
        else (f"{adapting_strategy} may need adapting based on recent session feedback." if adapting_strategy else "No clear support-need pattern flagged yet.")
    )

    concern_summary = "No incidents or distress patterns logged recently."
    if incidents:
        latest = incidents[0]
        concern_summary = f"{latest.title.strip()}. This may indicate distress, sensory load, or a communication need."
    elif rejected_events:
        concern_summary = (
            f"{rejected_events[0].strategy_label} was not accepted in recent sessions — worth observing the context."
        )

    cards = {
        "helping": {
            "id": "evidence_helping",
            "title": "What's helping",
            "summary": helping_summary,
            "sourceLine": combined_source_line([(len(helpful_events), "session log")]),
            "sourceCount": len(helpful_events),
        },
        "needsAdapting": {
            "id": "evidence_needs_adapting",
            "title": "What needs adapting",
            "summary": adapting_summary,
            "sourceLine": combined_source_line([(len(adapting_events), "session log")]),
            "sourceCount": len(adapting_events),
        },
        "supportConcerns": {
            "id": "evidence_support_concerns",
            "title": "Support needs / concerns",
            "summary": concern_summary,
            "sourceLine": combined_source_line(
                [(len(incidents), "incident note"), (len(rejected_events), "session log")]
            ),
            "sourceCount": len(incidents) + len(rejected_events),
        },
    }

    insights = [
        make_insight(
            insight_id=card["id"],
            insight_type="evidence",
            title=card["title"],
            summary=card["summary"],
            source_type="session_logs" if key != "supportConcerns" else "incident_notes",
            source_count=card["sourceCount"],
            source_label=card["sourceLine"],
            recommended_action="Add to Monthly Report",
            review_path="cm_review" if key == "supportConcerns" else "therapist_review",
        )
        for key, card in cards.items()
    ]

    patterns = {
        "helpfulSupports": sorted({e.strategy_label for e in helpful_events if e.strategy_label})[:5],
        "needsAdapting": sorted({e.strategy_label for e in adapting_events if e.strategy_label})[:5],
        "supportConcerns": [i.title for i in incidents[:3]],
    }
    return cards, patterns, insights
