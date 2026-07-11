"""Build SessionEvidenceProjection and audience previews from canonical session records."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.daily_log import DailyLog
from app.models.session import Session as TherapySession
from app.schemas.session_evidence_projection import (
    GoalEvidenceProjection,
    SessionEvidenceProjection,
    StrategyUseProjection,
)
from app.services import clinical_evidence_service as ev_svc
from app.services import structured_session_log_service as sse_svc


def build_session_evidence_projection(db: Session, log: DailyLog) -> SessionEvidenceProjection:
    """Canonical read contract from relational evidence + structured snapshot."""
    session = log.session or db.get(TherapySession, log.session_id)
    case_id = session.case_id if session else 0
    structured = sse_svc.structured_session_from_log(log)

    goal_rows: list[GoalEvidenceProjection] = []
    strategy_rows: list[StrategyUseProjection] = []
    evidence = ev_svc.entries_for_log(db, log.id)
    for g in evidence.get("goals") or []:
        goal_rows.append(
            GoalEvidenceProjection(
                goal_card_id=g.get("goal_card_id"),
                goal_label=g.get("goal_label") or "",
                evidence_notes=[g.get("measurement_note") or ""] if g.get("measurement_note") else [],
                participation=g.get("participation"),
                goal_achievement=g.get("goal_achievement"),
                strategies=[s.get("strategy_label") or "" for s in (g.get("strategies") or [])],
            )
        )
        for s in g.get("strategies") or []:
            strategy_rows.append(
                StrategyUseProjection(
                    strategy_id=s.get("strategy_id"),
                    strategy_label=s.get("strategy_label") or "",
                    feedback=s.get("strategy_feedback"),
                    short_note=s.get("short_note"),
                    goal_label=g.get("goal_label"),
                )
            )
    for s in evidence.get("strategies") or []:
        strategy_rows.append(
            StrategyUseProjection(
                strategy_id=s.get("strategy_id"),
                strategy_label=s.get("strategy_label") or "",
                feedback=s.get("strategy_feedback"),
                short_note=s.get("short_note"),
            )
        )

    child_signals: list[str] = []
    strengths: list[str] = []
    challenges: list[str] = []
    parent_summary = log.parent_notes or ""
    session_story = log.activities_done or ""
    extraction_version: Optional[int] = None
    recording_id: Optional[int] = None
    cm_flags: list[str] = []

    if structured:
        session_story = structured.todays_story or session_story
        child_signals = list(structured.child_response_signals or [])
        strengths = list(structured.observations.strengths or [])
        challenges = [c.text for c in structured.challenge_observations if c.text.strip()]
        parent_summary = structured.parent_summary or parent_summary
        extraction_version = structured.extraction_version
        recording_id = structured.recording_id
        if structured.goal_candidates:
            cm_flags.append("emerging_goal_candidates_sent")
        if structured.strategy_candidates:
            cm_flags.append("strategy_candidates_sent")
        if any(c.flag_cm_review for c in structured.challenge_observations):
            cm_flags.append("challenge_flagged_cm_review")

    if session and getattr(session, "actual_times_edited", False):
        cm_flags.append("session_times_edited")

    return SessionEvidenceProjection(
        session_id=log.session_id,
        case_id=case_id,
        daily_log_id=log.id,
        submitted_at=log.submitted_at,
        session_story=session_story,
        confirmed_goal_evidence=goal_rows,
        confirmed_strategy_uses=strategy_rows,
        child_response_signals=child_signals,
        strengths=strengths,
        challenges=challenges,
        therapist_reflection=log.therapist_reflection,
        parent_safe_summary=parent_summary,
        cm_review_flags=cm_flags,
        source_recording_id=recording_id,
        extraction_version=extraction_version,
    )


def build_therapist_preview(db: Session, log: DailyLog) -> dict[str, Any]:
    proj = build_session_evidence_projection(db, log)
    return {
        "kind": "therapist",
        "session_story": proj.session_story,
        "goals": [g.model_dump() for g in proj.confirmed_goal_evidence],
        "strategies": [s.model_dump() for s in proj.confirmed_strategy_uses],
        "child_response_signals": proj.child_response_signals,
        "strengths": proj.strengths,
        "challenges": proj.challenges,
        "therapist_reflection": proj.therapist_reflection,
    }


def build_cm_preview(db: Session, log: DailyLog) -> dict[str, Any]:
    proj = build_session_evidence_projection(db, log)
    structured = sse_svc.structured_session_from_log(log)
    return {
        "kind": "clinical",
        "session_story": proj.session_story,
        "goals": [g.model_dump() for g in proj.confirmed_goal_evidence],
        "strategies": [s.model_dump() for s in proj.confirmed_strategy_uses],
        "child_response_signals": proj.child_response_signals,
        "challenges": proj.challenges,
        "therapist_reflection": proj.therapist_reflection,
        "cm_review_flags": proj.cm_review_flags,
        "goal_candidates": [c.model_dump() for c in (structured.goal_candidates if structured else [])],
        "strategy_candidates": [c.model_dump() for c in (structured.strategy_candidates if structured else [])],
        "extraction_version": proj.extraction_version,
        "source_recording_id": proj.source_recording_id,
    }


def build_parent_preview(db: Session, log: DailyLog) -> dict[str, Any]:
    proj = build_session_evidence_projection(db, log)
    return {
        "kind": "parent",
        "summary": proj.parent_safe_summary,
        "strengths": proj.strengths,
        "helpful_supports": proj.confirmed_strategy_uses[:3],
    }
