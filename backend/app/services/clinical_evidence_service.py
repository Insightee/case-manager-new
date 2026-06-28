from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clinical_evidence_contract import normalize_clinical_extension
from app.core.clinical_measurement_criteria import (
    GOAL_ACHIEVEMENT_VALUES,
    INDEPENDENCE_VALUES,
    PARTICIPATION_VALUES,
    legacy_score_to_enum,
    validate_measurement_value,
)
from app.core.clinical_scoring import validate_score, validate_strategy_feedback
from app.models.case import Case
from app.models.clinical_evidence import (
    GoalEvidenceEvent,
    SessionGoalEntry,
    StrategyUseEvent,
)
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.services.strategy_repository_stats_service import record_strategy_use
from app.models.session import Session as TherapySession


def entry_schema_version_from_row(entry: SessionGoalEntry) -> int:
    """Legacy rows keep schema_version 1; scored rows are version 2."""
    if (
        entry.participation_score is not None
        or entry.independence_score is not None
        or entry.goal_achievement_score is not None
        or entry.participation
        or entry.independence_support_needed
        or entry.goal_achievement
    ):
        return 2
    return 1


def strategy_schema_version_from_row(event: StrategyUseEvent) -> int:
    if event.strategy_feedback or event.participation_score is not None:
        return 2
    return 1


def _json_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw if x]
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(x) for x in parsed if x]
        except json.JSONDecodeError:
            pass
    return []


def _enum_index(values: tuple[str, ...], value: str | None) -> int | None:
    if not value or value not in values:
        return None
    return values.index(value)


def _resolve_goal_measurement(item: dict) -> dict[str, Any]:
    """Prefer canonical enum strings; fall back to legacy 0–4 scores."""
    participation = item.get("participation")
    independence = item.get("independence_support_needed")
    achievement = item.get("goal_achievement")

    p_score = validate_score(item.get("participation_score"), field="participation_score")
    i_score = validate_score(item.get("independence_score"), field="independence_score")
    g_score = validate_score(item.get("goal_achievement_score"), field="goal_achievement_score")

    if not validate_measurement_value("participation", participation):
        participation = legacy_score_to_enum("participation", p_score)
    if not validate_measurement_value("independence_support_needed", independence):
        independence = legacy_score_to_enum("independence_support_needed", i_score)
    if not validate_measurement_value("goal_achievement", achievement):
        achievement = legacy_score_to_enum("goal_achievement", g_score)

    if p_score is None and participation:
        p_score = _enum_index(PARTICIPATION_VALUES, participation)
    if i_score is None and independence:
        i_score = _enum_index(INDEPENDENCE_VALUES, independence)
    if g_score is None and achievement:
        g_score = _enum_index(GOAL_ACHIEVEMENT_VALUES, achievement)

    return {
        "participation": participation,
        "independence_support_needed": independence,
        "goal_achievement": achievement,
        "participation_score": p_score,
        "independence_score": i_score,
        "goal_achievement_score": g_score,
    }


def _parse_extension_json(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return normalize_clinical_extension(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return normalize_clinical_extension(parsed)
        except json.JSONDecodeError:
            pass
    return {}


def _dump_extension_json(item: dict) -> Optional[str]:
    ext = normalize_clinical_extension(item.get("clinical_extension"))
    return json.dumps(ext) if ext else None


def _dump_json_list(values: Any) -> Optional[str]:
    items = _json_list(values)
    return json.dumps(items) if items else None


def _goal_to_dict(g: SessionGoalEntry) -> dict[str, Any]:
    return {
        "id": g.id,
        "schema_version": entry_schema_version_from_row(g),
        "goal_card_id": g.goal_card_id,
        "goal_label": g.goal_label,
        "domain_key": g.domain_key,
        "core_domains": _json_list(getattr(g, "core_domains_json", None)),
        "core_environments": _json_list(getattr(g, "core_environments_json", None)),
        "support_level": g.support_level,
        "response_note": g.response_note,
        "measurement_note": g.measurement_note,
        "visibility": g.visibility,
        "participation_score": g.participation_score,
        "independence_score": g.independence_score,
        "goal_achievement_score": g.goal_achievement_score,
        "participation": g.participation,
        "independence_support_needed": g.independence_support_needed,
        "goal_achievement": g.goal_achievement,
        "activity_used": g.activity_used,
        "goal_repository_item_id": g.goal_repository_item_id,
        "evidence_count": g.evidence_count or 0,
        "clinical_extension": _parse_extension_json(getattr(g, "clinical_extension_json", None)),
        "strategies": [],
    }


def _strategy_to_dict(s: StrategyUseEvent) -> dict[str, Any]:
    return {
        "id": s.id,
        "schema_version": strategy_schema_version_from_row(s),
        "strategy_id": s.strategy_id,
        "strategy_label": s.strategy_label,
        "outcome_note": s.outcome_note,
        "short_note": s.short_note,
        "goal_card_id": s.goal_card_id,
        "goal_entry_id": s.goal_entry_id,
        "environment": s.environment,
        "activity_used": s.activity_used,
        "participation_score": s.participation_score,
        "independence_score": s.independence_score,
        "goal_achievement_score": s.goal_achievement_score,
        "strategy_feedback": s.strategy_feedback,
        "custom_strategy_id": s.custom_strategy_id,
        "clinical_extension": _parse_extension_json(getattr(s, "clinical_extension_json", None)),
    }


def entries_for_log(db: Session, daily_log_id: int) -> dict:
    goals = db.scalars(select(SessionGoalEntry).where(SessionGoalEntry.daily_log_id == daily_log_id)).all()
    strategies = db.scalars(select(StrategyUseEvent).where(StrategyUseEvent.daily_log_id == daily_log_id)).all()
    goal_dicts = [_goal_to_dict(g) for g in goals]
    strat_by_goal: dict[int, list[dict]] = {}
    loose_strats: list[dict] = []
    for s in strategies:
        sd = _strategy_to_dict(s)
        if s.goal_entry_id:
            strat_by_goal.setdefault(s.goal_entry_id, []).append(sd)
        else:
            loose_strats.append(sd)
    for gd in goal_dicts:
        gd["strategies"] = strat_by_goal.get(gd["id"], [])
    all_strat_dicts = loose_strats + [s for gd in goal_dicts for s in gd["strategies"]]
    has_v2 = any(g["schema_version"] == 2 for g in goal_dicts) or any(
        s["schema_version"] == 2 for s in all_strat_dicts
    )
    return {
        "schema_version": 2 if has_v2 else 1,
        "goals": goal_dicts,
        "strategies": loose_strats,
    }


def _payload_is_v2(goals: list[dict], strategies: list[dict]) -> bool:
    for item in goals:
        if item.get("schema_version") == 2:
            return True
        if any(
            item.get(k) is not None
            for k in (
                "participation_score",
                "independence_score",
                "goal_achievement_score",
                "participation",
                "independence_support_needed",
                "goal_achievement",
            )
        ):
            return True
    for item in strategies:
        if item.get("schema_version") == 2:
            return True
        if item.get("strategy_feedback"):
            return True
    return False


def _resolve_context(db: Session, daily_log: DailyLog, case_id: int) -> tuple[TherapySession, Case, int | None]:
    session = daily_log.session or db.get(TherapySession, daily_log.session_id)
    if not session:
        raise HTTPException(status_code=400, detail="Session not found for log")
    case = db.get(Case, case_id)
    child_id = case.child_id if case else None
    return session, case, child_id


def assert_log_evidence_editable(log: DailyLog) -> None:
    if log.approval_status == LogApprovalStatus.APPROVED:
        raise HTTPException(status_code=403, detail="Approved logs cannot change structured evidence")


def _goal_has_session_work(item: dict) -> bool:
    """Goal row has therapist-documented updates for this session."""
    primary = (item.get("strategies") or [None])[0] if item.get("strategies") else None
    has_scores = any(item.get(k) is not None for k in ("participation_score", "independence_score", "goal_achievement_score"))
    if has_scores:
        return True
    if primary:
        steps = primary.get("strategy_steps") or []
        if (primary.get("strategy_label") or "").strip():
            return True
        if primary.get("strategy_feedback"):
            return True
        if (primary.get("short_note") or "").strip():
            return True
        if any(steps):
            return True
    note = (item.get("measurement_note") or item.get("response_note") or "").strip()
    ext = item.get("clinical_extension") or {}
    if isinstance(ext, dict) and any(
        ext.get(k)
        for k in (
            "child_response",
            "therapist_interpretation",
            "participation_quality",
            "environment_fit",
            "barrier_type",
            "adaptation_type",
        )
    ):
        return True
    return bool(note)


def save_session_evidence(
    db: Session,
    *,
    daily_log: DailyLog,
    case_id: int,
    goals: list[dict],
    strategies: list[dict],
    created_by_user_id: Optional[int] = None,
    commit: bool = True,
) -> dict:
    """Persist session evidence. Supports legacy (v1) and scored (v2) payloads.

    Existing logs without scores remain valid on read. New v2 saves write 0–4 scores.
    """
    assert_log_evidence_editable(daily_log)
    session, _case, child_id = _resolve_context(db, daily_log, case_id)
    use_v2 = _payload_is_v2(goals, strategies)

    existing_goals = db.scalars(
        select(SessionGoalEntry).where(SessionGoalEntry.daily_log_id == daily_log.id)
    ).all()
    for g in existing_goals:
        db.delete(g)
    existing_strats = db.scalars(
        select(StrategyUseEvent).where(StrategyUseEvent.daily_log_id == daily_log.id)
    ).all()
    for s in existing_strats:
        db.delete(s)
    db.flush()

    goal_labels: list[str] = []
    goal_entry_ids: dict[int, int] = {}
    nested_strategies: list[dict] = []

    for idx, item in enumerate(goals):
        if not _goal_has_session_work(item):
            continue
        label = (item.get("goal_label") or "").strip()
        if not label:
            continue
        goal_labels.append(label)

        measurement = _resolve_goal_measurement(item)

        entry = SessionGoalEntry(
            daily_log_id=daily_log.id,
            goal_card_id=item.get("goal_card_id"),
            goal_label=label,
            domain_key=item.get("domain_key"),
            support_level=item.get("support_level") if not use_v2 else None,
            response_note=item.get("response_note") or item.get("measurement_note"),
            measurement_note=item.get("measurement_note") or item.get("response_note"),
            visibility=item.get("visibility") or "INTERNAL_ONLY",
            session_id=session.id,
            case_id=case_id,
            child_id=child_id,
            created_by_user_id=created_by_user_id,
            participation_score=measurement["participation_score"],
            independence_score=measurement["independence_score"],
            goal_achievement_score=measurement["goal_achievement_score"],
            participation=measurement["participation"],
            independence_support_needed=measurement["independence_support_needed"],
            goal_achievement=measurement["goal_achievement"],
            activity_used=item.get("activity_used"),
            core_domains_json=_dump_json_list(item.get("core_domains")),
            core_environments_json=_dump_json_list(item.get("core_environments")),
            goal_repository_item_id=item.get("goal_repository_item_id"),
            evidence_count=int(item.get("evidence_count") or 0),
            clinical_extension_json=_dump_extension_json(item),
        )
        db.add(entry)
        db.flush()
        goal_entry_ids[idx] = entry.id

        summary = label
        if use_v2 and measurement["participation_score"] is not None:
            summary += (
                f" (P{measurement['participation_score']}/I{measurement['independence_score'] or '—'}"
                f"/G{measurement['goal_achievement_score'] or '—'})"
            )
        elif item.get("response_note"):
            summary += f" — {item.get('response_note')}"

        db.add(
            GoalEvidenceEvent(
                case_id=case_id,
                domain_key=item.get("domain_key"),
                source_type="daily_log",
                source_id=daily_log.id,
                summary=summary,
                visibility=item.get("visibility") or "INTERNAL_ONLY",
            )
        )

        for strat in item.get("strategies") or []:
            nested_strategies.append({**strat, "goal_entry_index": idx, "goal_card_id": item.get("goal_card_id")})

    all_strategies = list(strategies) + nested_strategies
    for item in all_strategies:
        label = (item.get("strategy_label") or "").strip()
        if not label:
            continue
        goal_entry_id = None
        if item.get("goal_entry_id"):
            goal_entry_id = item.get("goal_entry_id")
        elif item.get("goal_entry_index") is not None:
            goal_entry_id = goal_entry_ids.get(item["goal_entry_index"])

        feedback = validate_strategy_feedback(item.get("strategy_feedback"))
        strat_measurement = _resolve_goal_measurement(item)
        ext = item.get("clinical_extension") or {}
        if item.get("support_level") and not strat_measurement.get("independence_support_needed"):
            strat_measurement["independence_support_needed"] = item.get("support_level")
        elif ext.get("support_needed"):
            strat_measurement["independence_support_needed"] = ext.get("support_needed")
        used_as = ext.get("strategy_status") or ""
        used_as_adapted = used_as in ("adapted_today", "adapted")
        goal_domain = item.get("domain_key")
        db.add(
            StrategyUseEvent(
                daily_log_id=daily_log.id,
                strategy_id=item.get("strategy_id"),
                strategy_label=label,
                outcome_note=item.get("outcome_note") or item.get("short_note"),
                short_note=item.get("short_note") or item.get("outcome_note"),
                session_id=session.id,
                case_id=case_id,
                child_id=child_id,
                goal_card_id=item.get("goal_card_id"),
                goal_entry_id=goal_entry_id,
                created_by_user_id=created_by_user_id,
                environment=item.get("environment") or getattr(session, "mode", None),
                activity_used=item.get("activity_used"),
                participation_score=strat_measurement["participation_score"],
                independence_score=strat_measurement["independence_score"],
                goal_achievement_score=strat_measurement["goal_achievement_score"],
                participation=strat_measurement["participation"],
                independence_support_needed=strat_measurement["independence_support_needed"],
                goal_achievement=strat_measurement["goal_achievement"],
                strategy_feedback=feedback,
                custom_strategy_id=item.get("custom_strategy_id"),
                clinical_extension_json=_dump_extension_json(item),
            )
        )
        record_strategy_use(
            db,
            strategy_repository_item_id=item.get("strategy_id"),
            goal_domain=goal_domain,
            support_need=ext.get("support_need"),
            environment_context=item.get("environment") or getattr(session, "mode", None),
            support_level_tier=strat_measurement.get("independence_support_needed"),
            strategy_feedback=feedback,
            used_as_adapted=used_as_adapted,
        )

    if goal_labels:
        dual = daily_log.goals_addressed or ""
        merged = dual.strip()
        append = "; ".join(goal_labels)
        daily_log.goals_addressed = f"{merged}\n{append}".strip() if merged else append

    if commit:
        db.commit()
    else:
        db.flush()
    return entries_for_log(db, daily_log.id)
