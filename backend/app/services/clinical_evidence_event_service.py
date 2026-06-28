"""Materialize ClinicalEvidenceEventContract objects from structured session evidence rows.

Logical view only — no parallel evidence table in V1.
See docs/CLINICAL_EVIDENCE_EVENT_CONTRACT.md.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clinical_evidence_contract import (
    CONTRACT_STATUS,
    CONTRACT_VERSION,
    PARENT_VISIBLE_STATUSES,
    PARTICIPATION_ENUM_TO_QUALITY,
    PARTICIPATION_ENUM_TO_SIGNAL,
    PARTICIPATION_SCORE_TO_SIGNAL,
    STRATEGY_FEEDBACK_TO_INTERPRETATION,
    normalize_clinical_extension,
)
from app.core.clinical_scoring import SESSION_ENVIRONMENTS
from app.models.clinical_evidence import SessionGoalEntry, StrategyUseEvent
from app.models.daily_log import DailyLog
from app.models.session import Session as TherapySession
from app.models.strategy_recommendation_feedback import StrategyRecommendationFeedback
from app.services.report_log_query import submitted_logs_for_case_month

_EVIDENCE_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def evidence_event_id(goal_entry_id: Optional[int], strategy_use_event_id: Optional[int]) -> str:
    """Stable UUID5 across re-materialization."""
    key = f"goal:{goal_entry_id if goal_entry_id is not None else 'none'}:strategy:{strategy_use_event_id or 'none'}"
    return str(uuid.uuid5(_EVIDENCE_NAMESPACE, key))


def derive_goal_concept_id(
    *,
    goal_card_id: Optional[int],
    goal_repository_item_id: Optional[int],
    goal_title: str,
) -> str:
    """Stable concept id for cross-surface goal linking before global goal library maturity."""
    normalized = " ".join((goal_title or "").lower().split())
    parts = [
        f"card:{goal_card_id}" if goal_card_id else "",
        f"repo:{goal_repository_item_id}" if goal_repository_item_id else "",
        f"title:{normalized}",
    ]
    raw = "|".join(p for p in parts if p)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def normalize_environment(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    upper = raw.strip().upper()
    if upper in SESSION_ENVIRONMENTS:
        return upper
    aliases = {
        "CLASSROOM": "SCHOOL",
        "CORRIDOR": "SCHOOL",
        "PLAYGROUND": "SCHOOL",
        "CLINIC": "CENTER",
        "THERAPY_ROOM": "CENTER",
        "TELEHEALTH": "ONLINE",
        "REMOTE": "ONLINE",
    }
    return aliases.get(upper, "OTHER")


def derive_participation_signal(
    *,
    participation: Optional[str],
    participation_score: Optional[int],
) -> Optional[str]:
    if participation and participation in PARTICIPATION_ENUM_TO_SIGNAL:
        return PARTICIPATION_ENUM_TO_SIGNAL[participation]
    if participation_score is not None and participation_score in PARTICIPATION_SCORE_TO_SIGNAL:
        return PARTICIPATION_SCORE_TO_SIGNAL[participation_score]
    return None


def derive_participation_quality(participation: Optional[str]) -> Optional[str]:
    """Safe direct map from structured participation enum only."""
    if participation and participation in PARTICIPATION_ENUM_TO_QUALITY:
        return PARTICIPATION_ENUM_TO_QUALITY[participation]
    return None


def derive_therapist_interpretation(strategy_feedback: Optional[str]) -> Optional[str]:
    if not strategy_feedback:
        return None
    return STRATEGY_FEEDBACK_TO_INTERPRETATION.get(strategy_feedback.upper())


def compute_evidence_strength(event: dict[str, Any]) -> str:
    """Data completeness signal — not a clinical conclusion. Internal only."""
    goal = event.get("goal_linkage") or {}
    strategy = event.get("strategy_linkage") or {}
    context = event.get("context") or {}
    support = event.get("support_and_response") or {}

    has_scores = any(
        goal.get(k) is not None
        for k in ("participation_score", "independence_score", "goal_achievement_score")
    )
    has_participation_enum = bool(goal.get("goal_status_participation"))
    has_strategy = bool(strategy.get("strategy_title"))
    has_feedback = bool(strategy.get("strategy_feedback"))
    has_activity = bool(context.get("activity"))
    has_environment = bool(context.get("environment"))
    has_participation_signal = bool(support.get("participation_signal"))

    if has_strategy and has_feedback and (has_activity or has_environment) and (has_scores or has_participation_enum):
        return "strong"
    if has_strategy or has_scores or has_participation_enum or has_participation_signal or has_activity:
        return "moderate"
    return "weak"


def compute_evidence_gaps(event: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    goal = event.get("goal_linkage") or {}
    strategy = event.get("strategy_linkage") or {}
    support = event.get("support_and_response") or {}

    if goal.get("goal_title") and not strategy.get("strategy_title"):
        gaps.append("Goal addressed without linked strategy or support.")
    if not support.get("participation_signal"):
        gaps.append("No participation signal from structured measurement.")
    if strategy.get("strategy_feedback") == "HELPFUL" and not (event.get("context") or {}).get("activity"):
        gaps.append("Strategy marked helpful but no activity context recorded.")
    if not support.get("child_response"):
        gaps.append("No child response captured (V2 UI field).")
    return gaps


def compute_parent_visible(event: dict[str, Any]) -> bool:
    """Default false. Never true for sensitive evidence or internal-only strength metadata."""
    gov = event.get("visibility_and_governance") or {}
    sensitivity = gov.get("sensitivity_level") or "normal"
    if sensitivity != "normal":
        return False
    prov = event.get("provenance") or {}
    visibility = prov.get("entry_visibility") or "INTERNAL_ONLY"
    return visibility in PARENT_VISIBLE_STATUSES


def compute_learning_eligibility(event: dict[str, Any]) -> str:
    gov = event.get("visibility_and_governance") or {}
    sensitivity = gov.get("sensitivity_level") or "normal"
    if sensitivity in ("safeguarding_related", "staff_supervision_related", "do_not_use_for_ai"):
        return "not_eligible"
    strategy = event.get("strategy_linkage") or {}
    if strategy.get("is_custom_strategy"):
        return "case_specific_only"
    return "eligible_after_review"


def compute_ai_learning_allowed(event: dict[str, Any]) -> bool:
    gov = event.get("visibility_and_governance") or {}
    if gov.get("sensitivity_level") == "do_not_use_for_ai":
        return False
    return gov.get("learning_eligibility") in ("eligible_now", "eligible_after_review", "deidentified_research_candidate")


def _parse_row_extension(row: Any) -> dict[str, Any]:
    raw = getattr(row, "clinical_extension_json", None)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return normalize_clinical_extension(parsed) if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _merged_clinical_extension(goal: SessionGoalEntry, strategy: Optional[StrategyUseEvent]) -> dict[str, Any]:
    merged = _parse_row_extension(goal)
    if strategy:
        strat_ext = _parse_row_extension(strategy)
        for key, value in strat_ext.items():
            if key == "field_provenance":
                merged["field_provenance"] = {
                    **(merged.get("field_provenance") or {}),
                    **(value or {}),
                }
            elif value is not None and value != "" and value != []:
                merged[key] = value
    return merged


def _resolve_recommendation_feedback(
    db: Optional[Session],
    *,
    case_id: Optional[int],
    strategy: Optional[StrategyUseEvent],
    merged_ext: dict[str, Any],
) -> dict[str, Any]:
    """Link materialized events to strategy picker feedback when present."""
    default = {
        "was_brain_recommended": False,
        "recommendation_id": None,
        "therapist_action": None,
        "dismiss_reason": None,
    }
    if not db or not case_id:
        return default

    feedback_row = None
    feedback_id = merged_ext.get("recommendation_feedback_id")
    if feedback_id:
        feedback_row = db.get(StrategyRecommendationFeedback, int(feedback_id))
    elif strategy and strategy.strategy_id:
        feedback_row = db.scalars(
            select(StrategyRecommendationFeedback)
            .where(
                StrategyRecommendationFeedback.case_id == case_id,
                StrategyRecommendationFeedback.strategy_repository_item_id == strategy.strategy_id,
            )
            .order_by(StrategyRecommendationFeedback.created_at.desc())
        ).first()

    if not feedback_row:
        return default

    action_map = {
        "accepted": "accepted",
        "adapted": "adapted",
        "not_relevant": "dismissed",
        "already_tried": "dismissed",
        "needs_cm_input": "escalated",
        "dismissed": "dismissed",
    }
    brain_sources = {"library_match", "brain_recommendation", "ai_recommendation"}
    was_brain = feedback_row.recommendation_source in brain_sources or bool(feedback_id)

    return {
        "was_brain_recommended": was_brain,
        "recommendation_id": feedback_row.id,
        "therapist_action": action_map.get(feedback_row.feedback_status),
        "dismiss_reason": feedback_row.dismissal_reason,
    }


def _apply_clinical_extension(event: dict[str, Any], ext: dict[str, Any]) -> None:
    if not ext:
        return
    prov = event.setdefault("provenance", {}).setdefault("field_provenance", {})

    child_response = ext.get("child_response")
    if child_response:
        event.setdefault("support_and_response", {})["child_response"] = child_response
        prov["child_response"] = (ext.get("field_provenance") or {}).get("child_response", "human_selected")

    env_fit = ext.get("environment_fit")
    if env_fit:
        event.setdefault("context", {})["environment_fit"] = env_fit
        prov["environment_fit"] = (ext.get("field_provenance") or {}).get("environment_fit", "human_selected")

    barriers = ext.get("barrier_type") or []
    if barriers:
        event.setdefault("context", {})["barrier_type"] = barriers
        prov["barrier_type"] = (ext.get("field_provenance") or {}).get("barrier_type", "human_selected")

    participation_quality = ext.get("participation_quality")
    if participation_quality:
        event.setdefault("support_and_response", {})["participation_quality"] = participation_quality
        prov["participation_quality"] = (ext.get("field_provenance") or {}).get("participation_quality", "human_selected")

    regulation = ext.get("regulation_signal")
    if regulation:
        event.setdefault("support_and_response", {})["regulation_signal"] = regulation

    agency = ext.get("child_agency_signal")
    if agency:
        event.setdefault("support_and_response", {})["child_agency_signal"] = agency

    interpretation = ext.get("therapist_interpretation")
    if interpretation:
        event.setdefault("therapist_view", {})["therapist_interpretation"] = interpretation
        prov["therapist_interpretation"] = (ext.get("field_provenance") or {}).get("therapist_interpretation", "human_selected")

    strategy_status = ext.get("strategy_status")
    if strategy_status:
        event.setdefault("strategy_linkage", {})["strategy_use_status"] = strategy_status

    adaptation_type = ext.get("adaptation_type") or []
    if adaptation_type:
        event.setdefault("strategy_linkage", {})["adaptation_type"] = adaptation_type
        prov["adaptation_type"] = (ext.get("field_provenance") or {}).get("adaptation_type", "human_selected")

    adaptation_note = ext.get("adaptation_note")
    if adaptation_note:
        event.setdefault("strategy_linkage", {})["adaptation_note"] = adaptation_note
        prov["adaptation_note"] = (ext.get("field_provenance") or {}).get("adaptation_note", "human_written")

    if ext.get("support_needed"):
        event.setdefault("goal_linkage", {})["support_needed"] = ext["support_needed"]
    if ext.get("goal_movement"):
        event.setdefault("goal_linkage", {})["goal_movement"] = ext["goal_movement"]


def _therapist_note(goal: SessionGoalEntry, strategy: Optional[StrategyUseEvent]) -> Optional[str]:
    """Structured note fields only — never session_notes prose."""
    parts = []
    if goal.measurement_note:
        parts.append(goal.measurement_note.strip())
    elif goal.response_note:
        parts.append(goal.response_note.strip())
    if strategy:
        if strategy.short_note:
            parts.append(strategy.short_note.strip())
        elif strategy.outcome_note:
            parts.append(strategy.outcome_note.strip())
    combined = " | ".join(p for p in parts if p)
    return combined or None


def _build_event(
    *,
    goal: SessionGoalEntry,
    strategy: Optional[StrategyUseEvent],
    daily_log: DailyLog,
    session: Optional[TherapySession],
    materialized_at: str,
    db: Optional[Session] = None,
) -> dict[str, Any]:
    participation = goal.participation
    participation_score = goal.participation_score
    if strategy and strategy.participation_score is not None:
        participation_score = strategy.participation_score
    if strategy and strategy.participation:
        participation = strategy.participation

    participation_signal = derive_participation_signal(
        participation=participation,
        participation_score=participation_score,
    )
    participation_quality = derive_participation_quality(participation)
    strategy_feedback = (strategy.strategy_feedback.upper() if strategy and strategy.strategy_feedback else None)
    therapist_interpretation = derive_therapist_interpretation(strategy_feedback)

    field_provenance: dict[str, str] = {}
    if participation_signal:
        field_provenance["participation_signal"] = "system_derived"
    if participation_quality:
        field_provenance["participation_quality"] = "system_derived"
    if therapist_interpretation:
        field_provenance["therapist_interpretation"] = "system_derived"

    environment = normalize_environment(strategy.environment if strategy else None)
    activity = (strategy.activity_used if strategy and strategy.activity_used else None) or goal.activity_used

    goal_entry_id = goal.id
    strategy_id = strategy.id if strategy else None

    event: dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "contract_status": CONTRACT_STATUS,
        "contract_migration_notes": None,
        "identity": {
            "evidence_event_id": evidence_event_id(goal_entry_id, strategy_id),
            "case_id": goal.case_id or (session.case_id if session else None),
            "child_id": goal.child_id,
            "daily_log_id": goal.daily_log_id,
            "session_id": goal.session_id or (session.id if session else None),
            "goal_entry_id": goal_entry_id,
            "strategy_use_event_id": strategy_id,
            "goal_concept_id": derive_goal_concept_id(
                goal_card_id=goal.goal_card_id,
                goal_repository_item_id=goal.goal_repository_item_id,
                goal_title=goal.goal_label,
            ),
            "occurred_at": (goal.created_at or daily_log.submitted_at or datetime.now(timezone.utc)).isoformat(),
        },
        "goal_linkage": {
            "goal_id": goal.goal_card_id or goal.goal_repository_item_id,
            "goal_card_id": goal.goal_card_id,
            "goal_repository_item_id": goal.goal_repository_item_id,
            "goal_title": goal.goal_label,
            "domain_key": goal.domain_key,
            "goal_status_participation": goal.participation,
            "goal_status_independence": goal.independence_support_needed,
            "goal_status_achievement": goal.goal_achievement,
            "participation_score": goal.participation_score,
            "independence_score": goal.independence_score,
            "goal_achievement_score": goal.goal_achievement_score,
        },
        "strategy_linkage": {
            "strategy_id": strategy.strategy_id if strategy else None,
            "strategy_title": strategy.strategy_label if strategy else None,
            "strategy_use_status": "recorded" if strategy else None,
            "strategy_feedback": strategy_feedback,
            "is_custom_strategy": bool(strategy and strategy.custom_strategy_id),
            "adaptation_type": [],
            "adaptation_note": None,
        },
        "context": {
            "environment": environment,
            "activity": activity,
            "support_level": goal.support_level,
            "environment_fit": None,
            "barrier_type": [],
        },
        "support_and_response": {
            "participation_signal": participation_signal,
            "child_response": None,
            "regulation_signal": None,
            "child_agency_signal": None,
            "participation_quality": participation_quality,
            "child_preference_signal": None,
        },
        "therapist_view": {
            "therapist_interpretation": therapist_interpretation,
            "therapist_note": _therapist_note(goal, strategy),
        },
        "quality": {
            "evidence_strength": "weak",
            "evidence_strength_internal_only": True,
            "evidence_gaps": [],
        },
        "visibility_and_governance": {
            "parent_visible": False,
            "ai_learning_allowed": False,
            "sensitivity_level": "normal",
            "learning_eligibility": "eligible_after_review",
        },
        "provenance": {
            "source_type": "session_goal_entry_strategy_use_event",
            "source_record_ids": {
                "goal_entry_id": goal_entry_id,
                "strategy_use_event_id": strategy_id,
                "daily_log_id": goal.daily_log_id,
            },
            "entry_visibility": goal.visibility,
            "captured_by_user_id": goal.created_by_user_id,
            "captured_at": goal.created_at.isoformat() if goal.created_at else None,
            "materialized_at": materialized_at,
            "field_provenance": field_provenance,
        },
        "recommendation_feedback": {
            "was_brain_recommended": False,
            "recommendation_id": None,
            "therapist_action": None,
            "dismiss_reason": None,
        },
    }

    event["quality"]["evidence_strength"] = compute_evidence_strength(event)
    event["quality"]["evidence_gaps"] = compute_evidence_gaps(event)
    event["visibility_and_governance"]["learning_eligibility"] = compute_learning_eligibility(event)
    event["visibility_and_governance"]["parent_visible"] = compute_parent_visible(event)
    event["visibility_and_governance"]["ai_learning_allowed"] = compute_ai_learning_allowed(event)
    if event["quality"]["evidence_strength"]:
        event["provenance"]["field_provenance"]["evidence_strength"] = "system_computed"

    merged_ext = _merged_clinical_extension(goal, strategy)
    _apply_clinical_extension(event, merged_ext)
    event["recommendation_feedback"] = _resolve_recommendation_feedback(
        db,
        case_id=event["identity"]["case_id"],
        strategy=strategy,
        merged_ext=merged_ext,
    )

    return event


def _build_strategy_only_event(
    *,
    strategy: StrategyUseEvent,
    daily_log: DailyLog,
    session: Optional[TherapySession],
    materialized_at: str,
    db: Optional[Session] = None,
) -> dict[str, Any]:
    """Strategy row without linked goal — minimal contract."""
    participation_signal = derive_participation_signal(
        participation=strategy.participation,
        participation_score=strategy.participation_score,
    )
    participation_quality = derive_participation_quality(strategy.participation)
    strategy_feedback = strategy.strategy_feedback.upper() if strategy.strategy_feedback else None
    therapist_interpretation = derive_therapist_interpretation(strategy_feedback)

    field_provenance: dict[str, str] = {}
    if participation_signal:
        field_provenance["participation_signal"] = "system_derived"
    if participation_quality:
        field_provenance["participation_quality"] = "system_derived"
    if therapist_interpretation:
        field_provenance["therapist_interpretation"] = "system_derived"

    event: dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "contract_status": CONTRACT_STATUS,
        "contract_migration_notes": None,
        "identity": {
            "evidence_event_id": evidence_event_id(None, strategy.id),
            "case_id": strategy.case_id or (session.case_id if session else None),
            "child_id": strategy.child_id,
            "daily_log_id": strategy.daily_log_id,
            "session_id": strategy.session_id or (session.id if session else None),
            "goal_entry_id": None,
            "strategy_use_event_id": strategy.id,
            "goal_concept_id": derive_goal_concept_id(
                goal_card_id=strategy.goal_card_id,
                goal_repository_item_id=None,
                goal_title="",
            )
            if strategy.goal_card_id
            else None,
            "occurred_at": (strategy.created_at or daily_log.submitted_at or datetime.now(timezone.utc)).isoformat(),
        },
        "goal_linkage": {
            "goal_id": strategy.goal_card_id,
            "goal_card_id": strategy.goal_card_id,
            "goal_repository_item_id": None,
            "goal_title": None,
            "domain_key": None,
            "goal_status_participation": strategy.participation,
            "goal_status_independence": strategy.independence_support_needed,
            "goal_status_achievement": strategy.goal_achievement,
            "participation_score": strategy.participation_score,
            "independence_score": strategy.independence_score,
            "goal_achievement_score": strategy.goal_achievement_score,
        },
        "strategy_linkage": {
            "strategy_id": strategy.strategy_id,
            "strategy_title": strategy.strategy_label,
            "strategy_use_status": "recorded",
            "strategy_feedback": strategy_feedback,
            "is_custom_strategy": bool(strategy.custom_strategy_id),
            "adaptation_type": [],
            "adaptation_note": None,
        },
        "context": {
            "environment": normalize_environment(strategy.environment),
            "activity": strategy.activity_used,
            "support_level": None,
            "environment_fit": None,
            "barrier_type": [],
        },
        "support_and_response": {
            "participation_signal": participation_signal,
            "child_response": None,
            "regulation_signal": None,
            "child_agency_signal": None,
            "participation_quality": participation_quality,
            "child_preference_signal": None,
        },
        "therapist_view": {
            "therapist_interpretation": therapist_interpretation,
            "therapist_note": (strategy.short_note or strategy.outcome_note or "").strip() or None,
        },
        "quality": {
            "evidence_strength": "weak",
            "evidence_strength_internal_only": True,
            "evidence_gaps": ["Strategy recorded without linked goal entry."],
        },
        "visibility_and_governance": {
            "parent_visible": False,
            "ai_learning_allowed": False,
            "sensitivity_level": "normal",
            "learning_eligibility": "eligible_after_review",
        },
        "provenance": {
            "source_type": "session_goal_entry_strategy_use_event",
            "source_record_ids": {
                "goal_entry_id": None,
                "strategy_use_event_id": strategy.id,
                "daily_log_id": strategy.daily_log_id,
            },
            "entry_visibility": "INTERNAL_ONLY",
            "captured_by_user_id": strategy.created_by_user_id,
            "captured_at": strategy.created_at.isoformat() if strategy.created_at else None,
            "materialized_at": materialized_at,
            "field_provenance": field_provenance,
        },
        "recommendation_feedback": {
            "was_brain_recommended": False,
            "recommendation_id": None,
            "therapist_action": None,
            "dismiss_reason": None,
        },
    }

    event["quality"]["evidence_strength"] = compute_evidence_strength(event)
    event["quality"]["evidence_gaps"] = compute_evidence_gaps(event)
    event["visibility_and_governance"]["learning_eligibility"] = compute_learning_eligibility(event)
    event["visibility_and_governance"]["parent_visible"] = compute_parent_visible(event)
    event["visibility_and_governance"]["ai_learning_allowed"] = compute_ai_learning_allowed(event)
    if event["quality"]["evidence_strength"]:
        event["provenance"]["field_provenance"]["evidence_strength"] = "system_computed"
    merged_ext = _parse_row_extension(strategy)
    _apply_clinical_extension(event, merged_ext)
    event["recommendation_feedback"] = _resolve_recommendation_feedback(
        db,
        case_id=event["identity"]["case_id"],
        strategy=strategy,
        merged_ext=merged_ext,
    )
    return event


def rollup_adaptations_for_goal(events: list[dict[str, Any]], goal_concept_id: str) -> dict[str, Any]:
    """Layer-1 aggregation of repeated adaptations for IEP evidence strip."""
    filtered = [
        e
        for e in events
        if (e.get("identity") or {}).get("goal_concept_id") == goal_concept_id
    ]
    adaptation_counts: dict[str, int] = {}
    barrier_counts: dict[str, int] = {}
    for event in filtered:
        for adapt in (event.get("strategy_linkage") or {}).get("adaptation_type") or []:
            adaptation_counts[adapt] = adaptation_counts.get(adapt, 0) + 1
        for barrier in (event.get("context") or {}).get("barrier_type") or []:
            barrier_counts[barrier] = barrier_counts.get(barrier, 0) + 1
    repeated = {k: v for k, v in adaptation_counts.items() if v >= 3}
    return {
        "session_count": len(filtered),
        "adaptation_counts": adaptation_counts,
        "repeated_adaptations": repeated,
        "common_barriers": sorted(barrier_counts.items(), key=lambda x: -x[1])[:3],
    }


def materialize_from_log(db: Session, daily_log_id: int) -> list[dict[str, Any]]:
    """Materialize contract events from structured SessionGoalEntry + StrategyUseEvent rows."""
    log = db.get(DailyLog, daily_log_id)
    if not log:
        return []

    session = log.session or db.get(TherapySession, log.session_id)
    goals = list(
        db.scalars(select(SessionGoalEntry).where(SessionGoalEntry.daily_log_id == daily_log_id)).all()
    )
    strategies = list(
        db.scalars(select(StrategyUseEvent).where(StrategyUseEvent.daily_log_id == daily_log_id)).all()
    )

    materialized_at = _utc_now_iso()
    strat_by_goal: dict[int, list[StrategyUseEvent]] = {}
    loose_strategies: list[StrategyUseEvent] = []
    for s in strategies:
        if s.goal_entry_id:
            strat_by_goal.setdefault(s.goal_entry_id, []).append(s)
        else:
            loose_strategies.append(s)

    events: list[dict[str, Any]] = []
    linked_strategy_ids: set[int] = set()

    for goal in goals:
        linked = strat_by_goal.get(goal.id, [])
        if linked:
            for strategy in linked:
                linked_strategy_ids.add(strategy.id)
                events.append(
                    _build_event(
                        goal=goal,
                        strategy=strategy,
                        daily_log=log,
                        session=session,
                        materialized_at=materialized_at,
                        db=db,
                    )
                )
        else:
            events.append(
                _build_event(
                    goal=goal,
                    strategy=None,
                    daily_log=log,
                    session=session,
                    materialized_at=materialized_at,
                    db=db,
                )
            )

    for strategy in loose_strategies:
        if strategy.id not in linked_strategy_ids:
            events.append(
                _build_strategy_only_event(
                    strategy=strategy,
                    daily_log=log,
                    session=session,
                    materialized_at=materialized_at,
                    db=db,
                )
            )

    return events


def materialize_for_case_month(db: Session, case_id: int, month_yyyy_mm: str) -> list[dict[str, Any]]:
    logs = submitted_logs_for_case_month(db, case_id, month_yyyy_mm)
    events: list[dict[str, Any]] = []
    for log in logs:
        events.extend(materialize_from_log(db, log.id))
    return events


def rollup_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate stats for CM/brain summaries."""
    weak = sum(1 for e in events if (e.get("quality") or {}).get("evidence_strength") == "weak")
    unlinked = sum(
        1
        for e in events
        if (e.get("goal_linkage") or {}).get("goal_title")
        and not (e.get("strategy_linkage") or {}).get("strategy_title")
    )
    custom = sum(1 for e in events if (e.get("strategy_linkage") or {}).get("is_custom_strategy"))
    gaps: list[str] = []
    if not events:
        gaps.append("No materialized clinical evidence events for this period.")
    if weak:
        gaps.append(f"{weak} event(s) have weak structured evidence completeness.")
    if unlinked:
        gaps.append(f"{unlinked} goal event(s) without linked strategy or support.")

    return {
        "event_count": len(events),
        "weak_evidence_count": weak,
        "unlinked_goal_count": unlinked,
        "custom_strategy_count": custom,
        "gaps": gaps,
    }


def ai_draft_outputs_excluded_guardrail() -> dict[str, str]:
    """Documented guardrail: AI drafts are never materialized without human acceptance."""
    return {
        "policy": "ai_draft_outputs are not read by the materializer",
        "acceptance_required": "true",
        "pass1_behavior": "events originate only from session_goal_entries and strategy_use_events",
    }
