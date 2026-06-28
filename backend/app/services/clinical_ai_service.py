"""High-level clinical AI tasks — provider-neutral gateway wrapper."""

from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services import ai_gateway_service, clinical_brain_suggestion_service as brain_svc
from app.services.monthly_evidence_compiler_service import get_latest_snapshot


def _ai_disabled() -> bool:
    return not getattr(settings, "AI_ENABLED", False)


def _disabled_payload(task: str) -> dict[str, Any]:
    return {
        "status": "skipped",
        "message": "AI helpers are not enabled in this environment. You can continue without them.",
        "task_type": task,
    }


def improve_session_note(db: Session, user, *, raw_note: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    if _ai_disabled():
        return _disabled_payload("improve_session_note")
    payload = {"note": raw_note, "context": context or {}}
    gen = ai_gateway_service.AIGatewayService.preview(
        db,
        user_id=user.id,
        action="improve_note",
        payload=payload,
        case_id=(context or {}).get("case_id"),
    )
    return {
        "status": "success",
        "improved_note": gen.get("text") or gen.get("draft_text") or raw_note,
        "safety_flags": gen.get("safety_flags") or [],
        "missing_context_suggestions": gen.get("missing_context_suggestions") or [],
        "generation_log_id": gen.get("generation_log_id"),
    }


def draft_monthly_report_section(
    db: Session,
    user,
    *,
    report_id: int,
    section_type: str,
    parent_safe: bool = False,
) -> dict[str, Any]:
    if _ai_disabled():
        return _disabled_payload("draft_monthly_report_section")
    from app.models.clinical_report import ClinicalReport
    from app.services.report_engine_service import _report_month_from_metadata

    report = db.get(ClinicalReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    month = _report_month_from_metadata(report) or ""
    snap = get_latest_snapshot(db, report.case_id, month) if month else None
    if not snap:
        raise HTTPException(
            status_code=400,
            detail="Compile evidence first — monthly drafts need a structured evidence snapshot.",
        )
    gen = ai_gateway_service.AIGatewayService.preview(
        db,
        user_id=user.id,
        action="monthly_section_draft",
        payload={"section_type": section_type, "evidence": snap, "parent_safe": parent_safe},
        case_id=report.case_id,
    )
    strength = "evidence_limited"
    if len(snap.get("goals") or []) >= 2:
        strength = "evidence_moderate"
    if not snap.get("quality_flags"):
        strength = "evidence_strong"
    return {
        "status": "success",
        "draft_text": gen.get("text") or "",
        "source_ids": [g.get("source_log_ids") for g in snap.get("goals") or []],
        "safety_flags": gen.get("safety_flags") or [],
        "confidence_label": strength,
        "generation_log_id": gen.get("generation_log_id"),
    }


def suggest_iep_goal_wording(db: Session, user, *, payload: dict[str, Any]) -> dict[str, Any]:
    if _ai_disabled():
        return _disabled_payload("suggest_iep_goal_wording")
    gen = ai_gateway_service.AIGatewayService.preview(
        db,
        user_id=user.id,
        action="iep_goal_wording",
        payload=payload,
        case_id=payload.get("case_id"),
    )
    return {
        "status": "success",
        "candidate_wording": gen.get("text") or "",
        "indicators": gen.get("indicators") or [],
        "parent_friendly_explanation": gen.get("parent_friendly_explanation"),
        "cautions": gen.get("cautions") or [],
        "generation_log_id": gen.get("generation_log_id"),
    }


def recommend_strategies(db: Session, user, *, case_id: int, goal_context: dict[str, Any]) -> dict[str, Any]:
    from app.services import strategy_pool_matching_service as match_svc

    pool = match_svc.match_strategy_pool(
        db,
        case_id,
        domain=goal_context.get("domain"),
        support_need=goal_context.get("support_need"),
        environment=goal_context.get("environment"),
        limit=8,
    )
    if _ai_disabled():
        return {
            "status": "success",
            "recommended_strategies": [
                {
                    "strategy_id": row["id"],
                    "strategy_name": row.get("label"),
                    "why_this_may_fit": row.get("match_reason") or "Matches goal domain and support need.",
                    "source_strategy_ids": [row["id"]],
                }
                for row in pool
            ],
            "ai_ranked": False,
        }
    gen = ai_gateway_service.AIGatewayService.preview(
        db,
        user_id=user.id,
        action="strategy_recommendations",
        payload={"case_id": case_id, "pool": pool, "goal": goal_context},
        case_id=case_id,
    )
    return {
        "status": "success",
        "recommended_strategies": gen.get("recommended_strategies") or pool,
        "ai_ranked": True,
        "generation_log_id": gen.get("generation_log_id"),
    }


def check_parent_safe_language(text: str) -> dict[str, Any]:
    result = brain_svc.check_neuroaffirming_language(text)
    return {
        "is_parent_safe": result.get("safe_to_publish", True),
        "concerns": result.get("flagged_phrases") or [],
        "suggested_rewrite": result.get("suggested_replacements") or {},
    }
