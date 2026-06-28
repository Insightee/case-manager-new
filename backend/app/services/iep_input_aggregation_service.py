"""Aggregate therapist + parent inputs for IEP review section — no duplicate data entry."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case_manager_meeting import CaseManagerMeeting
from app.models.daily_log import DailyLog
from app.models.parent_goal_input import ParentGoalInput
from app.models.session import Session as TherapySession

IEP_DOMAIN_TAB_IDS = (
    "communication",
    "regulation_sensory",
    "participation",
    "learning_access",
    "peer_interaction",
)


def _snippet(text: str | None, *, max_len: int = 400) -> str:
    raw = (text or "").strip()
    if len(raw) <= max_len:
        return raw
    return raw[: max_len - 1].rstrip() + "…"


def _join_snippets(items: list[dict[str, Any]], *, max_items: int = 12) -> str:
    lines: list[str] = []
    for row in items[:max_items]:
        prefix = row.get("label") or row.get("source") or "Note"
        when = row.get("date") or ""
        head = f"• {prefix}" + (f" ({when})" if when else "")
        lines.append(f"{head}: {row.get('text', '')}")
    return "\n".join(lines)


def aggregate_case_inputs(db: Session, case_id: int) -> dict[str, Any]:
    """Pull therapist internal notes + parent-facing inputs from sessions, goals, meetings."""
    logs = list(
        db.scalars(
            select(DailyLog)
            .join(TherapySession, DailyLog.session_id == TherapySession.id)
            .where(
                TherapySession.case_id == case_id,
                DailyLog.submitted_at.isnot(None),
            )
            .order_by(DailyLog.submitted_at.desc())
            .limit(24)
        ).all()
    )

    therapist_snippets: list[dict[str, Any]] = []
    parent_snippets: list[dict[str, Any]] = []

    for log in logs:
        session = log.session
        when = log.submitted_at.date().isoformat() if log.submitted_at else ""
        for field, label in (
            ("session_notes", "Internal session notes"),
            ("observations", "Clinical observations"),
            ("follow_ups", "Follow-ups"),
            ("activities_done", "Activities"),
            ("goals_addressed", "Goals addressed"),
        ):
            text = getattr(log, field, None)
            if text and str(text).strip():
                therapist_snippets.append(
                    {
                        "source": "session_log",
                        "label": label,
                        "text": _snippet(str(text)),
                        "daily_log_id": log.id,
                        "date": when,
                    }
                )
        if log.parent_notes and str(log.parent_notes).strip():
            parent_snippets.append(
                {
                    "source": "session_parent_notes",
                    "label": "Family notes on session",
                    "text": _snippet(str(log.parent_notes)),
                    "daily_log_id": log.id,
                    "date": when,
                }
            )
        if log.parent_feedback and str(log.parent_feedback).strip() and log.parent_feedback_public:
            parent_snippets.append(
                {
                    "source": "session_parent_feedback",
                    "label": "Parent session feedback",
                    "text": _snippet(str(log.parent_feedback)),
                    "daily_log_id": log.id,
                    "date": when,
                }
            )

    for row in db.scalars(
        select(ParentGoalInput)
        .where(ParentGoalInput.case_id == case_id)
        .order_by(ParentGoalInput.id.desc())
        .limit(20)
    ).all():
        parent_snippets.append(
            {
                "source": "parent_goal_input",
                "label": row.input_type.replace("_", " ").title(),
                "text": _snippet(row.comment or row.input_type),
                "goal_ref": row.goal_ref,
                "date": row.created_at.date().isoformat() if row.created_at else "",
            }
        )

    meetings = list(
        db.scalars(
            select(CaseManagerMeeting)
            .where(CaseManagerMeeting.case_id == case_id)
            .order_by(CaseManagerMeeting.scheduled_date.desc())
            .limit(10)
        ).all()
    )
    for m in meetings:
        when = m.scheduled_date.isoformat() if m.scheduled_date else ""
        for field, label in (
            ("notes_summary", "Meeting summary"),
            ("notes_additional", "Meeting notes"),
            ("notes_concerns", "Meeting concerns"),
            ("notes_follow_up", "Meeting follow-up"),
            ("notes_action", "Meeting actions"),
        ):
            text = getattr(m, field, None)
            if text and str(text).strip():
                bucket = parent_snippets if m.meeting_type == "PARENT_MEETING" else therapist_snippets
                bucket.append(
                    {
                        "source": "cm_meeting",
                        "label": label,
                        "text": _snippet(str(text)),
                        "meeting_id": m.id,
                        "date": when,
                    }
                )

    return {
        "therapist_snippets": therapist_snippets,
        "parent_snippets": parent_snippets,
        "therapist_summary": _join_snippets(therapist_snippets),
        "parent_summary": _join_snippets(parent_snippets),
    }


def domain_observation_keys() -> dict[str, str]:
    return {tab_id: tab_id for tab_id in IEP_DOMAIN_TAB_IDS}
