"""Parent-safe goal summaries — no internal review or evidence fields."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.clinical_evidence import IepGoalCard
from app.models.goal_repository import GoalRepositoryItem, RepositoryItemStatus
from app.services import clinical_brain_suggestion_service as brain_svc
from app.services.clinical_brain_metadata import parse_metadata

PARENT_GOAL_KEYS = frozenset(
    {
        "id",
        "goal_title_parent",
        "focus_area",
        "parent_friendly_description",
        "parent_friendly_explanation",
        "parent_explanation",
        "strength_or_interest_link",
        "everyday_participation_reason",
        "current_supports",
        "strategies_parent_safe",
        "what_seems_to_help",
        "what_helps",
        "progress_signals_parent_safe",
        "what_we_are_noticing",
        "what_we_notice",
        "next_focus",
        "parent_input_prompt",
        "home_school_support",
        "last_shared_at",
        "last_shared_date",
        "last_reviewed_at",
        "status",
        "show_parent_comment_box",
    }
)


def _iso_date(dt: datetime | None) -> str | None:
    if not dt:
        return None
    return dt.date().isoformat()


def _safe_text(text: str | None) -> str | None:
    if not text:
        return None
    check = brain_svc.check_neuroaffirming_language(text)
    if not check.get("safe_to_publish", True):
        return None
    return text


def _enrich_parent_fields(base: dict, meta: dict | None = None) -> dict:
    meta = meta or {}
    base["goal_title_parent"] = base.get("focus_area")
    base["parent_friendly_description"] = base.get("parent_friendly_explanation")
    base["strength_or_interest_link"] = _safe_text(meta.get("strength_or_interest_link"))
    base["everyday_participation_reason"] = _safe_text(
        meta.get("everyday_participation_reason") or base.get("parent_friendly_explanation")
    )
    base["current_supports"] = _safe_text(meta.get("current_supports") or base.get("what_helps"))
    base["strategies_parent_safe"] = meta.get("strategies_parent_safe") or []
    base["progress_signals_parent_safe"] = meta.get("progress_signals_parent_safe") or []
    base["next_focus"] = _safe_text(meta.get("next_focus"))
    base["parent_input_prompt"] = "Your input helps the team understand how support is working across home, school, and daily routines."
    base["last_reviewed_at"] = base.get("last_shared_at")
    base["status"] = meta.get("parent_status") or "active"
    base["show_parent_comment_box"] = True
    return {k: v for k, v in base.items() if k in PARENT_GOAL_KEYS}


def _from_iep_card(card: IepGoalCard) -> dict:
    base = {
        "id": f"iep-{card.id}",
        "focus_area": _safe_text(card.label),
        "parent_friendly_explanation": _safe_text(card.why_it_matters or card.goal_statement),
        "parent_explanation": _safe_text(card.why_it_matters or card.goal_statement),
        "what_seems_to_help": None,
        "what_helps": None,
        "what_we_are_noticing": _safe_text(card.baseline),
        "what_we_notice": _safe_text(card.baseline),
        "home_school_support": _safe_text(card.goal_statement),
        "last_shared_at": _iso_date(card.updated_at),
        "last_shared_date": _iso_date(card.updated_at),
    }
    return _enrich_parent_fields(base)


def _from_repository_row(row: GoalRepositoryItem) -> dict | None:
    meta = parse_metadata(row.metadata_json)
    if row.case_id is not None and not meta.get("parent_safe", True):
        return None
    explanation = meta.get("parent_friendly_explanation") or row.desired_state or row.rationale
    explanation = _safe_text(explanation)
    if not explanation:
        return None
    base = {
        "id": f"repo-{row.id}",
        "focus_area": _safe_text(row.label),
        "parent_friendly_explanation": explanation,
        "parent_explanation": explanation,
        "what_seems_to_help": _safe_text(meta.get("what_seems_to_help")),
        "what_helps": _safe_text(meta.get("what_seems_to_help")),
        "what_we_are_noticing": _safe_text(meta.get("what_we_are_noticing") or row.baseline_state),
        "what_we_notice": _safe_text(meta.get("what_we_are_noticing") or row.baseline_state),
        "home_school_support": _safe_text(meta.get("home_school_support") or row.desired_state),
        "last_shared_at": _iso_date(row.approved_at or row.updated_at),
        "last_shared_date": _iso_date(row.approved_at or row.updated_at),
    }
    return _enrich_parent_fields(base, meta)


def list_parent_safe_goals(db: Session, case_id: int) -> list[dict]:
    items: list[dict] = []
    seen_labels: set[str] = set()

    cards = db.scalars(
        select(IepGoalCard)
        .where(IepGoalCard.case_id == case_id, IepGoalCard.status == "active")
        .order_by(IepGoalCard.sort_order, IepGoalCard.id)
    ).all()
    for card in cards:
        dto = _from_iep_card(card)
        key = (dto.get("focus_area") or "").strip().lower()
        if key and key not in seen_labels:
            seen_labels.add(key)
            items.append(dto)

    repo_rows = db.scalars(
        select(GoalRepositoryItem).where(
            GoalRepositoryItem.case_id == case_id,
            GoalRepositoryItem.status.in_(
                (RepositoryItemStatus.ACTIVE.value, RepositoryItemStatus.APPROVED.value)
            ),
        )
    ).all()
    for row in repo_rows:
        dto = _from_repository_row(row)
        if not dto:
            continue
        key = (dto.get("focus_area") or "").strip().lower()
        if key in seen_labels:
            continue
        seen_labels.add(key)
        items.append(dto)

    org_linked = db.scalars(
        select(GoalRepositoryItem).where(
            GoalRepositoryItem.case_id.is_(None),
            GoalRepositoryItem.status.in_(
                (RepositoryItemStatus.APPROVED.value, RepositoryItemStatus.ACTIVE.value)
            ),
        )
    ).all()
    for row in org_linked:
        meta = parse_metadata(row.metadata_json)
        if not meta.get("parent_safe"):
            continue
        dto = _from_repository_row(row)
        if not dto:
            continue
        key = (dto.get("focus_area") or "").strip().lower()
        if key in seen_labels:
            continue
        seen_labels.add(key)
        dto["last_shared_at"] = dto["last_shared_at"] or datetime.now(timezone.utc).date().isoformat()
        dto["last_shared_date"] = dto["last_shared_date"] or dto["last_shared_at"]
        items.append(dto)

    return items
