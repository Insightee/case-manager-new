"""Clinical Brain v1 — evidence summaries linked to clinical_reports (not a report engine)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.clinical_evidence_contract import CONTRACT_VERSION
from app.models.clinical_report import ClinicalReport, ClinicalReportEvidence, EvidenceSourceType, SectionVisibility
from app.services import clinical_evidence_event_service as cee_svc
from app.services import report_engine_service
from app.services.report_log_query import submitted_logs_for_case_month


def summarize_report_evidence(db: Session, report: ClinicalReport) -> dict[str, Any]:
    """Deterministic evidence summary from materialized ClinicalEvidenceEventContract objects."""
    if report.report_type == "monthly":
        month = report_engine_service._report_month_from_metadata(report) or ""
        events = cee_svc.materialize_for_case_month(db, report.case_id, month)
        logs = submitted_logs_for_case_month(db, report.case_id, month)
    else:
        from sqlalchemy import select

        from app.models.daily_log import DailyLog
        from app.models.session import Session as TherapySession

        logs = list(
            db.scalars(
                select(DailyLog)
                .join(TherapySession)
                .where(
                    TherapySession.case_id == report.case_id,
                    DailyLog.submitted_at.isnot(None),
                )
                .limit(50)
            ).all()
        )
        events = []
        for log in logs:
            events.extend(cee_svc.materialize_from_log(db, log.id))

    rollup = cee_svc.rollup_events(events)
    gaps = list(rollup.get("gaps") or [])
    if not logs:
        gaps.insert(0, "No submitted session logs for this period.")

    goal_entry_ids = {
        e.get("identity", {}).get("goal_entry_id")
        for e in events
        if e.get("identity", {}).get("goal_entry_id")
    }
    strategy_event_ids = {
        e.get("identity", {}).get("strategy_use_event_id")
        for e in events
        if e.get("identity", {}).get("strategy_use_event_id")
    }

    return {
        "report_id": report.id,
        "report_type": report.report_type,
        "contract_version": CONTRACT_VERSION,
        "session_log_count": len(logs),
        "materialized_event_count": rollup.get("event_count", 0),
        "weak_evidence_count": rollup.get("weak_evidence_count", 0),
        "unlinked_goal_count": rollup.get("unlinked_goal_count", 0),
        "custom_strategy_count": rollup.get("custom_strategy_count", 0),
        "goal_entry_count": len(goal_entry_ids),
        "strategy_event_count": len(strategy_event_ids),
        "evidence_gaps": gaps,
        "requires_clinical_review": True,
        "source_record_ids": {
            "daily_log_ids": [log.id for log in logs[:20]],
            "goal_entry_ids": sorted(goal_entry_ids)[:20],
            "strategy_event_ids": sorted(strategy_event_ids)[:20],
            "evidence_event_ids": [
                e.get("identity", {}).get("evidence_event_id") for e in events[:20]
            ],
        },
        "ai_draft_policy": cee_svc.ai_draft_outputs_excluded_guardrail(),
    }


def attach_evidence_summary_to_report(db: Session, report: ClinicalReport) -> ClinicalReportEvidence:
    """Persist evidence summary as report evidence row (audit trail, not a new report)."""
    summary = summarize_report_evidence(db, report)
    row = ClinicalReportEvidence(
        report_id=report.id,
        case_id=report.case_id,
        source_type=EvidenceSourceType.SESSION_LOG.value,
        source_id=None,
        section_key=None,
        evidence_label="clinical_brain_evidence_summary",
        visibility=SectionVisibility.INTERNAL_ONLY.value,
    )
    db.add(row)
    db.flush()
    meta = json.loads(report.metadata_json) if report.metadata_json else {}
    meta["last_evidence_summary"] = summary
    report.metadata_json = json.dumps(meta)
    db.flush()
    return row
