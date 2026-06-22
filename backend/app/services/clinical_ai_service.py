"""Clinical AI helpers — mock-first, no LLM spend by default."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clinical_domains import CORE_DOMAINS, CORE_ENVIRONMENTS
from app.models.goal_repository import GoalRepositoryItem, StrategyRepositoryItem
from app.services import strategy_suggestion_service as sug_svc


def suggest_alternative_strategies(
    db: Session,
    *,
    case_id: int,
    goal_card_id: int,
    domain_key: str | None = None,
    environment: str | None = None,
    exclude_strategy_ids: list[int] | None = None,
) -> list[dict]:
    return sug_svc.suggest_alternative_strategies(
        db,
        case_id=case_id,
        goal_card_id=goal_card_id,
        domain_key=domain_key,
        environment=environment,
        exclude_strategy_ids=exclude_strategy_ids or [],
    )


def rewrite_parent_summary(session_data: dict) -> str:
    notes = (session_data.get("parent_notes") or "").strip()
    if not notes:
        return "Today we worked on meaningful goals together. Ask your therapist if you'd like more detail."
    cleaned = re.sub(r"\s+", " ", notes)
    if len(cleaned) <= 280:
        return cleaned
    return cleaned[:277].rstrip() + "…"


def detect_duplicate_goal(db: Session, text: str, case_id: int) -> list[dict]:
    needle = text.strip().lower()
    if len(needle) < 5:
        return []
    rows = db.scalars(
        select(GoalRepositoryItem).where(GoalRepositoryItem.case_id == case_id).limit(50)
    ).all()
    hits = []
    for row in rows:
        label = (row.label or "").lower()
        if needle in label or label in needle:
            hits.append({"id": row.id, "label": row.label, "status": row.status})
    return hits[:5]


def detect_duplicate_strategy(db: Session, text: str, case_id: int) -> list[dict]:
    needle = text.strip().lower()
    if len(needle) < 3:
        return []
    rows = db.scalars(
        select(StrategyRepositoryItem).where(
            StrategyRepositoryItem.case_id == case_id
        ).limit(50)
    ).all()
    hits = []
    for row in rows:
        label = (row.label or "").lower()
        if needle in label or label in needle:
            hits.append({"id": row.id, "label": row.label, "status": row.status})
    return hits[:5]


_KEYWORD_DOMAIN = {
    "communication": ("speak", "talk", "language", "communicat"),
    "social_participation": ("social", "peer", "friend", "group"),
    "emotional_regulation": ("emotion", "frustrat", "calm", "regulat"),
    "sensory_regulation": ("sensory", "noise", "touch", "overwhelm"),
    "independence_daily_living": ("daily", "dress", "toilet", "self care", "independ"),
    "learning_readiness": ("learn", "focus", "attention", "task"),
    "play_engagement": ("play", "engage", "game", "toy"),
    "motor_movement_participation": ("motor", "movement", "walk", "balance", "ot"),
}


def classify_goal_domain(text: str) -> str | None:
    lower = text.lower()
    for domain_id, keywords in _KEYWORD_DOMAIN.items():
        if any(k in lower for k in keywords):
            return domain_id
    return CORE_DOMAINS[0]["id"] if CORE_DOMAINS else None


_ENV_KEYWORDS = {
    "home": ("home", "house", "family"),
    "school_classroom": ("school", "class", "classroom"),
    "playground": ("playground", "yard", "recess"),
    "peer_interaction": ("peer", "friend", "classmate"),
    "community_outing": ("community", "outing", "mall", "park"),
    "transitions": ("transition", "change", "switch"),
    "interests": ("interest", "hobby", "passion"),
    "meal_self_care_routine": ("meal", "lunch", "self care", "routine", "bathroom"),
}


def classify_strategy_environment(text: str) -> str | None:
    lower = text.lower()
    for env_id, keywords in _ENV_KEYWORDS.items():
        if any(k in lower for k in keywords):
            return env_id
    return CORE_ENVIRONMENTS[0]["id"] if CORE_ENVIRONMENTS else None
