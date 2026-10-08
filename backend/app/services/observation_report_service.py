from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.clinical_report import ClinicalReport, ClinicalReportSection
from app.models.goal_repository import GoalRepositoryItem, RepositoryItemStatus, StrategyRepositoryItem
from app.models.user import User
from app.services import report_engine_service, report_status_service
from app.services.daily_log_narrative import NARRATIVE_TEXT_FIELDS, iter_narrative_text_values


def ensure_checklist_bridge(db: Session, case: Case, user: User) -> tuple[ClinicalReport, object]:
    from app.services import observation_checklist_service as ocs

    report = report_engine_service.get_or_create_observation_report(db, case, user)
    checklist = ocs.get_or_create_checklist(db, case, user.id)
    if not checklist.clinical_report_id:
        checklist.clinical_report_id = report.id
        due_at, due_rule = ocs.compute_due(case, db)
        if due_at and not checklist.due_at:
            checklist.due_at = due_at
            checklist.due_rule = due_rule
        if not report.due_date and due_at:
            report.due_date = due_at
    db.flush()
    return report, checklist


def save_observation_responses(
    db: Session,
    case: Case,
    user: User,
    responses: dict[str, str],
    *,
    sync_clinical_profile: bool = True,
) -> ClinicalReport:
    report, checklist = ensure_checklist_bridge(db, case, user)
    if checklist.therapist_user_id != user.id:
        raise ValueError("Not authorized")
    report_engine_service.sync_responses_to_sections(db, report, responses)
    if sync_clinical_profile:
        from app.services import observation_checklist_service as ocs

        ocs.update_profile(
            db,
            case,
            user,
            {
                "history": responses.get("referral_context") or responses.get("referral_background"),
                "goals_summary": responses.get("summary_recommendations") or responses.get("clinical_summary"),
            },
        )
    db.flush()
    return report


def submit_observation(db: Session, case: Case, user: User) -> ClinicalReport:
    report, checklist = ensure_checklist_bridge(db, case, user)
    sections = list(
        db.scalars(
            select(ClinicalReportSection).where(ClinicalReportSection.report_id == report.id)
        ).all()
    )
    ready = report_engine_service.required_sections_complete(sections)
    report = report_status_service.submit_report(db, report, user, readiness_ok=ready)
    checklist.status = "SUBMITTED"
    from datetime import datetime, timezone

    checklist.submitted_at = datetime.now(timezone.utc)
    checklist.reviewer_comment = None
    if case.case_manager_user_id:
        from app.services import notification_service

        notification_service.create_notification(
            db,
            user_id=case.case_manager_user_id,
            title="Observation report submitted",
            body=f"Review observation report for {case.case_code}",
            entity_type="clinical_report",
            entity_id=report.id,
        )
    db.flush()
    return report


def create_goal_candidate(
    db: Session,
    report: ClinicalReport,
    user: User,
    *,
    label: str,
    domain_key: str,
    baseline_note: str = "",
    desired_direction: str = "",
    source_section_key: str = "emerging_goals",
) -> GoalRepositoryItem:
    row = GoalRepositoryItem(
        case_id=report.case_id,
        created_by_user_id=user.id,
        domain_key=domain_key or "general",
        label=label,
        rationale=baseline_note,
        baseline_state=baseline_note,
        desired_state=desired_direction,
        goal_statement=label,
        status=RepositoryItemStatus.CANDIDATE.value,
        source="observation_report",
        scope="case",
        source_clinical_report_id=report.id,
    )
    db.add(row)
    db.flush()
    return row


def create_strategy_candidate(
    db: Session,
    report: ClinicalReport,
    user: User,
    *,
    label: str,
    description: str = "",
    domain_key: str | None = None,
) -> StrategyRepositoryItem:
    existing = db.scalar(
        select(StrategyRepositoryItem).where(
            StrategyRepositoryItem.label.ilike(label.strip()),
            StrategyRepositoryItem.status.in_(("approved", "active", "candidate")),
        )
    )
    if existing:
        pass  # caller may link instead
    row = StrategyRepositoryItem(
        case_id=report.case_id,
        created_by_user_id=user.id,
        label=label.strip(),
        how_to_use=description,
        when_to_use=description,
        domain_key=domain_key,
        status=RepositoryItemStatus.CANDIDATE.value,
        source="observation_report",
        scope="case",
        source_clinical_report_id=report.id,
    )
    db.add(row)
    db.flush()
    return row


def _session_log_suggestions(db: Session, case_id: int, limit: int = 5) -> list[dict]:
    from app.models.daily_log import DailyLog
    from app.models.session import Session as TherapySession
    from sqlalchemy.orm import selectinload

    logs = list(
        db.scalars(
            select(DailyLog)
            .join(TherapySession, DailyLog.session_id == TherapySession.id)
            .where(TherapySession.case_id == case_id)
            .options(selectinload(DailyLog.session))
            .order_by(TherapySession.scheduled_date.desc(), DailyLog.id.desc())
            .limit(12)
        ).all()
    )
    out: list[dict] = []
    seen: set[str] = set()
    suggestion_field_order = ("goals_addressed", "observations", "session_notes", "activities_done")
    assert set(suggestion_field_order) == set(NARRATIVE_TEXT_FIELDS)
    for log in logs:
        for name in suggestion_field_order:
            text = (getattr(log, name, None) or "").strip()
            if len(text) < 8:
                continue
            snippet = text.split(".")[0].strip()[:100]
            key = snippet.lower()
            if not snippet or key in seen:
                continue
            seen.add(key)
            session_date = log.session.scheduled_date.isoformat() if log.session and log.session.scheduled_date else None
            out.append(
                {
                    "label": snippet,
                    "description": f"From session log{f' · {session_date}' if session_date else ''}",
                    "source": "session_log",
                    "log_id": log.id,
                }
            )
            if len(out) >= limit:
                return out
    return out


def list_candidates(db: Session, report_id: int) -> dict:
    report = db.get(ClinicalReport, report_id)
    goals = list(
        db.scalars(
            select(GoalRepositoryItem).where(GoalRepositoryItem.source_clinical_report_id == report_id)
        ).all()
    )
    strategies = list(
        db.scalars(
            select(StrategyRepositoryItem).where(StrategyRepositoryItem.source_clinical_report_id == report_id)
        ).all()
    )
    existing_labels = {g.label for g in goals}
    suggested_goals = []
    if report:
        library = list(
            db.scalars(
                select(GoalRepositoryItem)
                .where(GoalRepositoryItem.case_id == report.case_id)
                .where(GoalRepositoryItem.source_clinical_report_id.is_(None))
                .limit(4)
            ).all()
        )
        suggested_goals = [
            {
                "label": g.label,
                "description": g.desired_state or g.baseline_state or g.rationale or "",
                "source": "suggestion",
            }
            for g in library
            if g.label not in existing_labels
        ]
        session_suggestions = _session_log_suggestions(db, report.case_id)
        for item in session_suggestions:
            if item["label"] not in existing_labels and not any(s["label"] == item["label"] for s in suggested_goals):
                suggested_goals.append(item)
    return {
        "goals": [
            {
                "id": g.id,
                "label": g.label,
                "domain_key": g.domain_key,
                "status": g.status,
                "baseline_state": g.baseline_state,
                "desired_state": g.desired_state,
            }
            for g in goals
        ],
        "strategies": [
            {
                "id": s.id,
                "label": s.label,
                "status": s.status,
                "how_to_use": s.how_to_use,
            }
            for s in strategies
        ],
        "suggested_goals": suggested_goals,
    }


def generate_iep_draft_stub(db: Session, report: ClinicalReport) -> dict:
    candidates = list_candidates(db, report.id)
    return {
        "status": "not_implemented",
        "message": "IEP builder UI will be configured in a later phase.",
        "candidates_count": len(candidates["goals"]) + len(candidates["strategies"]),
        "approved_observation": report.status in ("approved", "locked"),
    }


def start_observation(db: Session, case: Case, user: User) -> ClinicalReport:
    """Create or return editable observation report for this case."""
    from app.models.clinical_report import ClinicalReportStatus

    existing = report_engine_service.get_active_observation_report(db, case.id)
    if existing and existing.status not in (
        ClinicalReportStatus.APPROVED.value,
        ClinicalReportStatus.LOCKED.value,
    ):
        report_engine_service.seed_observation_sections(db, existing.id)
        return existing
    if existing and existing.status in (
        ClinicalReportStatus.APPROVED.value,
        ClinicalReportStatus.LOCKED.value,
    ):
        from datetime import datetime, timezone

        existing.archived_at = datetime.now(timezone.utc)
        db.flush()
    report, _ = ensure_checklist_bridge(db, case, user)
    report_engine_service.seed_observation_sections(db, report.id)
    return report


def generate_session_insights(db: Session, report: ClinicalReport, case: Case) -> dict:
    """Layer 1 deterministic insights from session logs — on-demand only."""
    from sqlalchemy import func

    from app.models.daily_log import DailyLog
    from app.models.session import Session as TherapySession
    from sqlalchemy.orm import selectinload

    log_count = db.scalar(
        select(func.count(DailyLog.id))
        .join(TherapySession, DailyLog.session_id == TherapySession.id)
        .where(TherapySession.case_id == case.id)
    ) or 0
    patterns = []
    if log_count >= 3:
        patterns = [
            {"key": "transition_difficulty", "label": "Transition Difficulty", "value": "Observed across recent sessions", "trend": "stable"},
            {"key": "visual_support", "label": "Visual Support Efficacy", "value": "Structured supports noted in logs", "trend": "positive"},
            {"key": "sensory_regulation", "label": "Sensory Regulation", "value": "Regulation patterns emerging", "trend": "monitoring"},
        ]
    recent_logs = list(
        db.scalars(
            select(DailyLog)
            .join(TherapySession, DailyLog.session_id == TherapySession.id)
            .where(TherapySession.case_id == case.id)
            .options(selectinload(DailyLog.session))
            .order_by(TherapySession.scheduled_date.desc())
            .limit(3)
        ).all()
    )
    evidence_snippets = []
    for log in recent_logs:
        for field in iter_narrative_text_values(log):
            text = (field or "").strip()
            if len(text) >= 12:
                evidence_snippets.append(
                    {
                        "log_id": log.id,
                        "date": log.session.scheduled_date.isoformat() if log.session and log.session.scheduled_date else None,
                        "text": text[:160],
                    }
                )
                break
        if len(evidence_snippets) >= 3:
            break
    suggested_tiles = {
        "strengths": [],
        "interests": [],
        "support_needs": [],
        "barriers": [],
    }
    if patterns:
        if len(patterns) > 1:
            suggested_tiles["strengths"] = [patterns[1]["label"]]
        if patterns:
            suggested_tiles["support_needs"] = [patterns[0]["label"]]
        if len(patterns) > 2:
            suggested_tiles["barriers"] = [patterns[2]["label"]]
    field_suggestions: dict[str, str | dict] = {}
    if patterns:
        field_suggestions["communication"] = (
            f"Session logs ({log_count} reviewed) note {patterns[0]['label'].lower()}. "
            f"{patterns[0]['value']}."
        )
        field_suggestions["regulation_sensory"] = (
            f"{patterns[2]['label']}: {patterns[2]['value']}" if len(patterns) > 2 else ""
        )
        field_suggestions["participation"] = (
            f"{patterns[1]['label']}: {patterns[1]['value']}" if len(patterns) > 1 else ""
        )
    if suggested_tiles["strengths"] or suggested_tiles["interests"]:
        field_suggestions["strengths_interests"] = {
            "strengths": suggested_tiles["strengths"],
            "interests": suggested_tiles["interests"],
        }
    if suggested_tiles["support_needs"] or suggested_tiles["barriers"]:
        field_suggestions["support_needs"] = {
            "support_needs": suggested_tiles["support_needs"],
            "barriers": suggested_tiles["barriers"],
        }
    if evidence_snippets:
        field_suggestions["clinical_summary"] = (
            "Recent session evidence: "
            + " · ".join(s["text"][:80] for s in evidence_snippets[:2])
        )
    payload = {
        "status": "generated",
        "session_count": log_count,
        "patterns": patterns,
        "summary": f"Reviewed {log_count} session logs for {case.case_code}. Patterns are deterministic previews until AI is enabled.",
        "suggested_tiles": suggested_tiles,
        "field_suggestions": field_suggestions,
        "evidence_snippets": evidence_snippets,
    }
    sec = db.scalar(
        select(ClinicalReportSection).where(
            ClinicalReportSection.report_id == report.id,
            ClinicalReportSection.section_key == "clinical_summary",
        )
    )
    if sec:
        data = {}
        if sec.structured_data_json:
            try:
                data = json.loads(sec.structured_data_json)
            except json.JSONDecodeError:
                data = {}
        data["session_insights"] = payload
        sec.structured_data_json = json.dumps(data)
        db.flush()
    return payload


def apply_session_insights(db: Session, report: ClinicalReport, user: User) -> dict:
    del user
    sec = db.scalar(
        select(ClinicalReportSection).where(
            ClinicalReportSection.report_id == report.id,
            ClinicalReportSection.section_key == "clinical_summary",
        )
    )
    if not sec or not sec.structured_data_json:
        raise ValueError("Generate session insights first")
    try:
        data = json.loads(sec.structured_data_json)
    except json.JSONDecodeError as exc:
        raise ValueError("Insights data is unavailable") from exc
    insights = data.get("session_insights") or {}
    field_suggestions = insights.get("field_suggestions") or {}
    if not field_suggestions:
        raise ValueError("No insight previews to apply")
    applied: list[str] = []
    for key, value in field_suggestions.items():
        if isinstance(value, dict):
            existing = db.scalar(
                select(ClinicalReportSection).where(
                    ClinicalReportSection.report_id == report.id,
                    ClinicalReportSection.section_key == key,
                )
            )
            merged = {}
            if existing and existing.structured_data_json:
                try:
                    merged = json.loads(existing.structured_data_json)
                except json.JSONDecodeError:
                    merged = {}
            merged.update(value)
            report_engine_service.patch_section(db, report, key, structured_data=merged)
        elif isinstance(value, str) and value.strip():
            report_engine_service.patch_section(db, report, key, narrative_text=value.strip())
        applied.append(key)
    db.flush()
    return {"applied_sections": applied, "count": len(applied)}
