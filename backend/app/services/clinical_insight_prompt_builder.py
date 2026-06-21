"""Build compact AI prompts from structured summaries."""

from __future__ import annotations

import json
from typing import Any

from app.services.ai_prompt_registry import PROMPT_VERSION

SAFETY_RULES = """
- No diagnosis generation.
- No final clinical decisions.
- Use neuro-affirmative language.
- Prefer: appeared helpful, mixed evidence, needs review, not enough evidence.
- Avoid: failed, non-compliant, manipulative, attention-seeking.
- Internal notes must not appear in parent_safe_draft output.
"""

OUTPUT_SCHEMA = {
    "snapshot_summary": "string",
    "goal_recommendations": "array",
    "strategy_signals": "array",
    "support_accommodations": "array",
    "what_may_not_be_working": "array",
    "evidence_gaps": "array",
    "parent_safe_draft": "string",
    "limitations": "array",
    "requires_review": True,
    "parent_safe": False,
}


def build_insight_prompt(
    summary: dict[str, Any],
    insight_type: str,
    role: str,
    retrieved_references: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    refs = retrieved_references or []
    ref_text = "\n".join(f"- [{r.get('chunk_title') or 'ref'}] {r.get('chunk_text', '')[:400]}" for r in refs[:5])

    system = f"""You are a clinical documentation assistant for InsighteCase.
Role: {role}
Task: Generate insight type '{insight_type}' from structured summary only.
{SAFETY_RULES}
Return valid JSON matching schema: {json.dumps(OUTPUT_SCHEMA)}
"""

    user = f"""Structured summary (compact):
{json.dumps(summary, default=str)[:6000]}

Reference chunks (if any):
{ref_text or 'None'}

Insight type: {insight_type}
"""

    return {
        "system": system,
        "user": user,
        "prompt_version": PROMPT_VERSION,
        "insight_type": insight_type,
    }
