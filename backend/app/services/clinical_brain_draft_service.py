"""Clinical Brain v1 — draft section content attached to clinical_reports sections."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_generation import AiDraftOutput
from app.models.clinical_report import ClinicalReport, ClinicalReportSection
from app.models.user import User
from app.services import ai_gateway_service, report_engine_service


def attach_draft_to_section(
    db: Session,
    *,
    report: ClinicalReport,
    section_key: str,
    draft_text: str,
    user: User,
    action: str,
    generation_log_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Store AI draft as section narrative + ai_draft_outputs audit (does not approve or publish)."""
    report_engine_service.seed_monthly_sections(db, report.id) if report.report_type == "monthly" else None
    if report.report_type == "observation":
        report_engine_service.seed_observation_sections(db, report.id)
    if report.report_type == "iep":
        report_engine_service.seed_iep_sections(db, report.id)

    sec = db.scalar(
        select(ClinicalReportSection).where(
            ClinicalReportSection.report_id == report.id,
            ClinicalReportSection.section_key == section_key,
        )
    )
    if not sec:
        raise ValueError(f"Section {section_key} not found")

    meta = metadata or {}
    meta.update({
        "requires_clinical_review": True,
        "parent_safe": False,
        "action": action,
        "recommendation": draft_text[:500],
        "reason": meta.get("reason", "AI-generated draft — therapist must review."),
        "evidence_used": meta.get("evidence_used", []),
        "linked_resource_ids": meta.get("linked_resource_ids", []),
        "linked_goal_ids": meta.get("linked_goal_ids", []),
        "linked_strategy_ids": meta.get("linked_strategy_ids", []),
        "missing_information": meta.get("missing_information", []),
    })

    structured = json.loads(sec.structured_data_json) if sec.structured_data_json else {}
    structured["clinical_brain_draft"] = meta
    report_engine_service.patch_section(
        db, report, section_key,
        narrative_text=draft_text,
        structured_data=structured,
    )

    if generation_log_id:
        db.add(
            AiDraftOutput(
                generation_log_id=generation_log_id,
                target_type="clinical_report_section",
                target_id=sec.id,
                draft_text=draft_text,
                accepted=False,
            )
        )
        db.flush()

    return {
        "report_id": report.id,
        "section_key": section_key,
        "section_id": sec.id,
        "draft_text": draft_text,
        "requires_clinical_review": True,
        "metadata": meta,
    }


def generate_section_draft_via_gateway(
    db: Session,
    *,
    user: User,
    report: ClinicalReport,
    section_key: str,
    action: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Explicit-click AI draft — routes through ai_gateway_service only."""
    gen = ai_gateway_service.AIGatewayService.preview(
        db,
        user_id=user.id,
        case_id=report.case_id,
        action=action,
        context={**context, "section_key": section_key, "report_type": report.report_type},
        target_type="clinical_report_section",
        target_id=report.id,
    )
    draft_text = gen.get("draft_text") or ""
    return attach_draft_to_section(
        db,
        report=report,
        section_key=section_key,
        draft_text=draft_text,
        user=user,
        action=action,
        generation_log_id=gen.get("generation_log_id"),
        metadata=context,
    )
