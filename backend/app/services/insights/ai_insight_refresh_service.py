"""On-demand "Refresh Insights" — Layer 2/3 AI polish on top of the always-available rule engine.

AI is never required to render the tab; this only rewrites wording for a compact set of
already-computed insight objects (Layer 2 of the spec). Clinical facts (status, source counts,
linked ids) are never produced or altered by AI — only `polishedSummary` text is AI-generated,
and it is returned alongside (never instead of) the rule-based `insights[]` cards.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.clinical_snapshot import ClinicalSnapshot
from app.models.user import User
from app.services import ai_gateway_service as ai_svc
from app.services import clinical_snapshot_service as snap_svc
from app.services.insights import weekly_insight_usage_limiter as limiter
from app.services.insights.case_insight_aggregator import build_case_insight_payload, compute_input_hash

INSIGHT_REFRESH_TYPE = "case_insight_refresh"
CAP_EXCEEDED_MESSAGE = (
    "You've used your 2 AI refreshes for this week. Insights will still update from session logs "
    "and structured data."
)
NO_NEW_DATA_MESSAGE = "Insights are already up to date from the latest available data."
MAX_INSIGHTS_SENT_TO_AI = 20


def _find_existing_refresh(db: Session, *, case_id: int, input_hash: str) -> ClinicalSnapshot | None:
    return db.scalars(
        select(ClinicalSnapshot)
        .where(
            ClinicalSnapshot.case_id == case_id,
            ClinicalSnapshot.insight_type == INSIGHT_REFRESH_TYPE,
            ClinicalSnapshot.input_hash == input_hash,
        )
        .order_by(ClinicalSnapshot.id.desc())
        .limit(1)
    ).first()


def _compact_ai_context(payload: dict[str, Any]) -> dict[str, Any]:
    """Layer 2: compact structured summary only — never the full case history."""
    goals = payload["activeIEP"]["goals"]
    return {
        "child_summary": payload["child"]["summaryParagraph"],
        "active_goals": [
            {"label": g["label"], "status": g["status"], "sessions_addressed": g["sessionsAddressed"]}
            for g in goals
        ],
        "recent_session_patterns": payload["recentSessions"]["patterns"],
        "collaborative_inputs": [
            {"source": c["source"], "input": c["input"][:200]} for c in payload["collaborativeInputs"][:8]
        ],
        "insight_objects": [
            {"id": i["id"], "type": i["type"], "title": i["title"], "summary": i["summary"], "status": i.get("status")}
            for i in payload["insights"][:MAX_INSIGHTS_SENT_TO_AI]
        ],
    }


def refresh_insights(db: Session, *, case_id: int, user: User) -> dict[str, Any]:
    payload = build_case_insight_payload(db, case_id)
    input_hash = compute_input_hash(payload)

    existing = _find_existing_refresh(db, case_id=case_id, input_hash=input_hash)
    if existing:
        result = snap_svc.snapshot_to_dict(existing)
        result["message"] = NO_NEW_DATA_MESSAGE
        result["capExceeded"] = False
        result["polishedSummary"] = result.get("ai_output_text")
        return result

    usage = limiter.get_usage(db, case_id=case_id, user_id=user.id)
    if usage["remaining"] <= 0:
        return {
            "message": CAP_EXCEEDED_MESSAGE,
            "capExceeded": True,
            "usage": usage,
            "polishedSummary": None,
        }

    context = _compact_ai_context(payload)
    gen = ai_svc.AIGatewayService.generate_clinical_snapshot(
        db,
        user_id=user.id,
        case_id=case_id,
        summary=context,
        insight_type=INSIGHT_REFRESH_TYPE,
        role=user.role_names[0] if user.role_names else "therapist",
    )

    month = datetime.now(timezone.utc).strftime("%Y-%m")
    snap = snap_svc.create_snapshot(
        db,
        case_id=case_id,
        month=month,
        user=user,
        insight_type=INSIGHT_REFRESH_TYPE,
        deterministic_summary=context,
        ai_output=gen["output"],
        input_hash=input_hash,
        provider=gen["provider"],
        model=gen["model"],
        generation_log_id=gen.get("generation_log_id"),
        token_input=gen.get("token_input_count"),
        token_output=gen.get("token_output_count"),
        estimated_cost=gen.get("estimated_cost"),
    )
    result = snap_svc.snapshot_to_dict(snap)
    result["message"] = "Insights refreshed."
    result["capExceeded"] = False
    result["polishedSummary"] = result.get("ai_output_text")
    result["usage"] = limiter.get_usage(db, case_id=case_id, user_id=user.id)
    return result
