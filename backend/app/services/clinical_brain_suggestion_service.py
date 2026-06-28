"""Clinical Brain v1 — goal/strategy suggestions and quality checks (no report creation)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.clinical_report import ClinicalReport
from app.models.user import User
from app.services import ai_gateway_service, clinical_brain_evidence_service
from app.services.reference_retrieval_service import retrieve_safety_rules


def suggest_goals_for_report(
    db: Session,
    *,
    user: User,
    report: ClinicalReport,
    domain_key: str | None = None,
) -> dict[str, Any]:
    evidence = clinical_brain_evidence_service.summarize_report_evidence(db, report)
    refs = retrieve_safety_rules(db, report.report_type, user.id)
    context = {
        "domain_key": domain_key,
        "evidence_summary": evidence,
        "linked_resource_ids": [r.get("chunk_id") for r in refs],
    }
    gen = ai_gateway_service.AIGatewayService.preview(
        db,
        user_id=user.id,
        case_id=report.case_id,
        action="iep_goal_suggest",
        context=context,
        target_type="clinical_report",
        target_id=report.id,
    )
    return {
        "report_id": report.id,
        "recommendation": gen.get("draft_text"),
        "reason": "Based on session evidence and approved reference doctrine.",
        "evidence_used": evidence.get("source_record_ids"),
        "linked_resource_ids": context["linked_resource_ids"],
        "linked_goal_ids": [],
        "linked_strategy_ids": [],
        "missing_information": evidence.get("evidence_gaps", []),
        "requires_clinical_review": True,
        "generation_log_id": gen.get("generation_log_id"),
    }


def check_neuroaffirming_language(text: str) -> dict[str, Any]:
    """Layer 1 language scan — no LLM."""
    from app.core.clinical_domains import (
        COMPLIANCE_GOAL_BLOCKLIST,
        NEUROAFFIRMATIVE_AVOID,
        SUGGESTED_REPLACEMENTS,
    )

    lower = (text or "").lower()
    flagged = [phrase for phrase in NEUROAFFIRMATIVE_AVOID if phrase in lower]
    compliance_hits = [p for p in COMPLIANCE_GOAL_BLOCKLIST if p in lower]
    all_hits = list(dict.fromkeys(flagged + compliance_hits))
    replacements = {p: SUGGESTED_REPLACEMENTS[p] for p in all_hits if p in SUGGESTED_REPLACEMENTS}
    severe = bool(compliance_hits) or len(flagged) >= 2
    moderate = bool(flagged) and not severe
    severity = "high" if severe else ("moderate" if moderate else "none")
    needs_review = bool(all_hits)
    return {
        "flagged_phrases": flagged,
        "compliance_goal_hits": compliance_hits,
        "suggested_replacements": replacements,
        "severity": severity,
        "safe_to_publish": not needs_review,
        "requires_clinical_review": needs_review,
        "recommendation": "Revise language to focus on participation, regulation, and support."
        if needs_review
        else None,
    }


def missing_evidence_flags(db: Session, report: ClinicalReport) -> dict[str, Any]:
    summary = clinical_brain_evidence_service.summarize_report_evidence(db, report)
    return {
        "report_id": report.id,
        "missing_information": summary.get("evidence_gaps", []),
        "requires_clinical_review": bool(summary.get("evidence_gaps")),
        "evidence_used": summary.get("source_record_ids"),
    }
