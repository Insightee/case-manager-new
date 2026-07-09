from __future__ import annotations

import json
import re
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.child import Child
from app.models.clinical_report import (
    ClinicalReport,
    ClinicalReportSection,
    ClinicalReportStatus,
    ClinicalReportType,
    SectionCompletionStatus,
    SectionVisibility,
)
from app.models.user import User
from app.report_engine_constants import (
    IEP_REPORT_SECTIONS,
    LEGACY_CHECKLIST_KEY_MAP,
    MONTHLY_REPORT_SECTIONS,
    OBSERVATION_REPORT_SECTIONS,
    REQUIRED_IEP_SECTION_KEYS,
    REQUIRED_MONTHLY_SECTION_KEYS,
    REQUIRED_OBSERVATION_SECTION_KEYS,
    REPORT_TYPE_HOOKS,
)
from app.services import report_status_service


def _section_visibility(meta: dict) -> str:
    vis = meta.get("visibility")
    if vis == "internal_only":
        return SectionVisibility.INTERNAL_ONLY.value
    if vis == "parent_visible":
        return SectionVisibility.PARENT_VISIBLE.value
    return SectionVisibility.CLINICAL_TEAM.value


def seed_iep_sections(db: Session, report_id: int) -> None:
    existing = db.scalars(
        select(ClinicalReportSection.section_key).where(ClinicalReportSection.report_id == report_id)
    ).all()
    have = set(existing)
    for i, meta in enumerate(IEP_REPORT_SECTIONS):
        key = str(meta["key"])
        if key in have:
            continue
        db.add(
            ClinicalReportSection(
                report_id=report_id,
                section_key=key,
                section_title=str(meta["label"]),
                section_order=i,
                visibility=_section_visibility(meta),
                completion_status=SectionCompletionStatus.NOT_STARTED.value,
            )
        )
    db.flush()


def seed_observation_sections(db: Session, report_id: int) -> None:
    existing = db.scalars(
        select(ClinicalReportSection.section_key).where(ClinicalReportSection.report_id == report_id)
    ).all()
    have = set(existing)
    for i, meta in enumerate(OBSERVATION_REPORT_SECTIONS):
        key = str(meta["key"])
        if key in have:
            continue
        db.add(
            ClinicalReportSection(
                report_id=report_id,
                section_key=key,
                section_title=str(meta["label"]),
                section_order=i,
                visibility=_section_visibility(meta),
                completion_status=SectionCompletionStatus.NOT_STARTED.value,
            )
        )
    db.flush()


def seed_monthly_sections(db: Session, report_id: int) -> None:
    existing = db.scalars(
        select(ClinicalReportSection.section_key).where(ClinicalReportSection.report_id == report_id)
    ).all()
    have = set(existing)
    for i, meta in enumerate(MONTHLY_REPORT_SECTIONS):
        key = str(meta["key"])
        if key in have:
            continue
        db.add(
            ClinicalReportSection(
                report_id=report_id,
                section_key=key,
                section_title=str(meta["label"]),
                section_order=i,
                visibility=_section_visibility(meta),
                completion_status=SectionCompletionStatus.NOT_STARTED.value,
            )
        )
    db.flush()


def section_completion_status(narrative: str | None, internal: str | None, structured: dict | None = None) -> str:
    text = (narrative or "").strip()
    struct = structured or {}
    has_struct = bool(struct.get("strengths") or struct.get("interests") or struct.get("support_needs")
                      or struct.get("barriers") or struct.get("environments"))
    if not text and not has_struct:
        return SectionCompletionStatus.NOT_STARTED.value
    if text and len(text) < 20 and not has_struct:
        return SectionCompletionStatus.IN_PROGRESS.value
    if text and len(text) >= 20:
        return SectionCompletionStatus.COMPLETED.value
    if has_struct:
        return SectionCompletionStatus.COMPLETED.value
    return SectionCompletionStatus.IN_PROGRESS.value


def completion_pct(sections: list[ClinicalReportSection]) -> int:
    if not sections:
        return 0
    done = sum(1 for s in sections if s.completion_status == SectionCompletionStatus.COMPLETED.value)
    return int(round(100 * done / len(sections)))


def required_sections_complete(sections: list[ClinicalReportSection]) -> bool:
    by_key = {s.section_key: s for s in sections}
    for key in REQUIRED_OBSERVATION_SECTION_KEYS:
        sec = by_key.get(key)
        if not sec or sec.completion_status != SectionCompletionStatus.COMPLETED.value:
            return False
    return True


def missing_required_keys(sections: list[ClinicalReportSection]) -> list[str]:
    by_key = {s.section_key: s for s in sections}
    missing = []
    for key in REQUIRED_OBSERVATION_SECTION_KEYS:
        sec = by_key.get(key)
        if not sec or sec.completion_status != SectionCompletionStatus.COMPLETED.value:
            meta = next((m for m in OBSERVATION_REPORT_SECTIONS if m["key"] == key), None)
            missing.append(str(meta["label"]) if meta else key)
    return missing


def required_monthly_sections_complete(sections: list[ClinicalReportSection]) -> bool:
    by_key = {s.section_key: s for s in sections}
    for key in REQUIRED_MONTHLY_SECTION_KEYS:
        sec = by_key.get(key)
        if not sec or sec.completion_status != SectionCompletionStatus.COMPLETED.value:
            return False
    return True


def missing_monthly_required_keys(sections: list[ClinicalReportSection]) -> list[str]:
    by_key = {s.section_key: s for s in sections}
    missing = []
    for key in REQUIRED_MONTHLY_SECTION_KEYS:
        sec = by_key.get(key)
        if not sec or sec.completion_status != SectionCompletionStatus.COMPLETED.value:
            meta = next((m for m in MONTHLY_REPORT_SECTIONS if m["key"] == key), None)
            missing.append(str(meta["label"]) if meta else key)
    return missing


def _normalize_month_key(month: str) -> str:
    """Canonical YYYY-MM for metadata and lookups."""
    from app.services.report_log_query import parse_report_month

    ym = parse_report_month(month)
    if ym:
        return f"{ym[0]:04d}-{ym[1]:02d}"
    return month.strip()


def _report_month_from_metadata(report: ClinicalReport) -> str | None:
    meta = json.loads(report.metadata_json) if report.metadata_json else {}
    return meta.get("month")


def get_monthly_report_for_case_month(db: Session, case_id: int, month: str) -> ClinicalReport | None:
    month_key = _normalize_month_key(month)
    rows = list(
        db.scalars(
            select(ClinicalReport).where(
                ClinicalReport.case_id == case_id,
                ClinicalReport.report_type == ClinicalReportType.MONTHLY.value,
                ClinicalReport.archived_at.is_(None),
            )
        ).all()
    )
    for row in rows:
        if _report_month_from_metadata(row) == month_key:
            return row
    return None


def get_or_create_monthly_report(db: Session, case: Case, user: User, month: str) -> ClinicalReport:
    month_key = _normalize_month_key(month)
    existing = get_monthly_report_for_case_month(db, case.id, month_key)
    if existing:
        seed_monthly_sections(db, existing.id)
        return existing
    child_name = case.child.full_name if case.child else "Client"
    row = ClinicalReport(
        case_id=case.id,
        child_id=case.child_id,
        report_type=ClinicalReportType.MONTHLY.value,
        title=f"Monthly Report — {month_key} — {child_name}",
        status=ClinicalReportStatus.DRAFT.value,
        created_by_id=user.id,
        assigned_therapist_id=user.id,
        case_manager_id=case.case_manager_user_id,
        metadata_json=json.dumps({"month": month_key}),
    )
    db.add(row)
    db.flush()
    seed_monthly_sections(db, row.id)
    report_status_service.log_review_event(db, row, user, "created")
    return row


def populate_monthly_from_evidence(db: Session, report: ClinicalReport) -> dict:
    """Deterministic populate from session logs and structured evidence (no AI)."""
    import html as html_mod

    from app.models.clinical_evidence import IepGoalCard, SessionGoalEntry, StrategyUseEvent
    from app.services import report_compile_service
    from app.services.clinical_evidence_service import entry_schema_version_from_row
    from app.services.report_log_query import submitted_logs_for_case_month

    if report.report_type != ClinicalReportType.MONTHLY.value:
        raise ValueError("Not a monthly clinical report")
    month_key = _report_month_from_metadata(report) or ""
    logs = submitted_logs_for_case_month(db, report.case_id, month_key)
    seed_monthly_sections(db, report.id)

    def _esc(text: str | None) -> str:
        return html_mod.escape((text or "").strip())

    session_html = report_compile_service.compile_body_html_from_logs(logs)
    goal_lines = []
    for log in logs:
        entries = db.scalars(
            select(SessionGoalEntry).where(SessionGoalEntry.daily_log_id == log.id)
        ).all()
        for e in entries:
            if entry_schema_version_from_row(e) == 2:
                parts = [
                    f"P{e.participation_score if e.participation_score is not None else '—'}",
                    f"I{e.independence_score if e.independence_score is not None else '—'}",
                    f"G{e.goal_achievement_score if e.goal_achievement_score is not None else '—'}",
                ]
                note = e.measurement_note or e.response_note or e.activity_used or "Scored in session"
                goal_lines.append(
                    f"<li><strong>{_esc(e.goal_label)}</strong> ({'/'.join(parts)}) — {_esc(note)}</li>"
                )
            else:
                goal_lines.append(f"<li>{_esc(e.goal_label)} — {_esc(e.response_note or 'Noted in session')}</li>")
    goal_html = f"<ul>{''.join(goal_lines)}</ul>" if goal_lines else "<p><em>No structured goal entries.</em></p>"

    strat_lines = []
    for log in logs:
        for s in db.scalars(
            select(StrategyUseEvent).where(StrategyUseEvent.daily_log_id == log.id)
        ).all():
            feedback = f" ({s.strategy_feedback})" if s.strategy_feedback else ""
            strat_lines.append(
                f"<li>{_esc(s.strategy_label)}{feedback} — {_esc(s.short_note or s.outcome_note or '')}</li>"
            )
    strat_html = f"<ul>{''.join(strat_lines)}</ul>" if strat_lines else "<p><em>No strategy use recorded.</em></p>"

    active_goals = db.scalars(
        select(IepGoalCard).where(
            IepGoalCard.case_id == report.case_id,
            IepGoalCard.status.in_(("active", "approved")),
        )
    ).all()
    if active_goals and not goal_lines:
        goal_html = "<ul>" + "".join(f"<li>{_esc(g.label)}</li>" for g in active_goals) + "</ul>"

    child_name = ""
    if report.child_id:
        child = db.get(Child, report.child_id)
        child_name = child.full_name if child else ""

    sections_data = {
        "child_summary": f"<p>Monthly summary for {_esc(child_name) or 'client'} — {month_key}.</p>",
        "sessions_summary": session_html,
        "goals_progress": goal_html,
        "strategies_used": strat_html,
        "strengths_observed": "<p><em>Add strengths observed this month.</em></p>",
        "support_needs": "<p><em>Add support needs as needed.</em></p>",
        "barriers_or_context": "<p><em>Add barriers or context as needed.</em></p>",
        "next_month_focus": f"<p>{_esc(report_compile_service.collect_follow_ups(logs)) or '—'}</p>",
        "therapist_notes": "<p><em>Therapist notes (clinical team).</em></p>",
        "internal_notes": "<p><em>Internal CM notes only.</em></p>",
        "parent_summary": "<p><em>Draft parent-facing summary — review before publish.</em></p>",
    }

    for key, html in sections_data.items():
        try:
            patch_section(db, report, key, narrative_text=html)
        except ValueError:
            continue

    if report.status == ClinicalReportStatus.DRAFT.value:
        report.status = ClinicalReportStatus.IN_PROGRESS.value
    db.flush()
    return {"report_id": report.id, "sections_populated": list(sections_data.keys()), "log_count": len(logs)}


def get_or_create_observation_report(db: Session, case: Case, user: User) -> ClinicalReport:
    from app.services.observation_checklist_service import compute_due

    row = db.scalar(
        select(ClinicalReport).where(
            ClinicalReport.case_id == case.id,
            ClinicalReport.report_type == ClinicalReportType.OBSERVATION.value,
            ClinicalReport.archived_at.is_(None),
        )
    )
    if row:
        return row
    due_at, _ = compute_due(case, db)
    child_name = case.child.full_name if case.child else "Client"
    row = ClinicalReport(
        case_id=case.id,
        child_id=case.child_id,
        report_type=ClinicalReportType.OBSERVATION.value,
        title=f"Observation Report — {child_name}",
        status=ClinicalReportStatus.DRAFT.value,
        created_by_id=user.id,
        assigned_therapist_id=user.id,
        case_manager_id=case.case_manager_user_id,
        due_date=due_at,
    )
    db.add(row)
    db.flush()
    seed_observation_sections(db, row.id)
    report_status_service.log_review_event(db, row, user, "created")
    return row


def list_case_reports(db: Session, case_id: int) -> list[ClinicalReport]:
    return list(
        db.scalars(
            select(ClinicalReport)
            .where(ClinicalReport.case_id == case_id, ClinicalReport.archived_at.is_(None))
            .order_by(ClinicalReport.updated_at.desc())
        ).all()
    )


def get_report(db: Session, report_id: int) -> ClinicalReport | None:
    return db.get(ClinicalReport, report_id)


def patch_section(
    db: Session,
    report: ClinicalReport,
    section_key: str,
    *,
    narrative_text: str | None = None,
    internal_notes: str | None = None,
    structured_data: dict | None = None,
) -> ClinicalReportSection:
    sec = db.scalar(
        select(ClinicalReportSection).where(
            ClinicalReportSection.report_id == report.id,
            ClinicalReportSection.section_key == section_key,
        )
    )
    if not sec:
        raise ValueError("Section not found")
    if narrative_text is not None:
        sec.narrative_text = narrative_text
    if internal_notes is not None:
        sec.internal_notes = internal_notes
    if structured_data is not None:
        sec.structured_data_json = json.dumps(structured_data)
    parsed_struct = json.loads(sec.structured_data_json) if sec.structured_data_json else {}
    sec.completion_status = section_completion_status(sec.narrative_text, sec.internal_notes, parsed_struct)
    if report.status == ClinicalReportStatus.DRAFT.value and sec.completion_status != SectionCompletionStatus.NOT_STARTED.value:
        report.status = ClinicalReportStatus.IN_PROGRESS.value
    db.flush()
    return sec


def map_legacy_responses(responses: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in responses.items():
        target = LEGACY_CHECKLIST_KEY_MAP.get(k, k)
        if v and v.strip():
            out[target] = v.strip()
    return out


def sync_responses_to_sections(db: Session, report: ClinicalReport, responses: dict[str, str]) -> None:
    mapped = map_legacy_responses(responses)
    seed_observation_sections(db, report.id)
    for key, text in mapped.items():
        if not text.strip():
            continue
        try:
            patch_section(db, report, key, narrative_text=text)
        except ValueError:
            continue


def sections_to_legacy_responses(sections: list[ClinicalReportSection]) -> dict[str, str]:
    by_key = {s.section_key: (s.narrative_text or "") for s in sections}
    reverse = {v: k for k, v in LEGACY_CHECKLIST_KEY_MAP.items()}
    out: dict[str, str] = {}
    for eng_key, text in by_key.items():
        legacy = reverse.get(eng_key, eng_key)
        if text.strip():
            out[legacy] = text
    return out


def required_iep_sections_complete(db: Session, report: ClinicalReport) -> bool:
    from app.services import iep_report_service

    result = iep_report_service.validate_iep_submit(db, report)
    return result.get("ready", False)


def missing_iep_required(db: Session, report: ClinicalReport) -> list[str]:
    from app.services import iep_report_service

    result = iep_report_service.validate_iep_submit(db, report)
    return result.get("errors", [])


def _section_catalog(report_type: str) -> list[dict]:
    if report_type == ClinicalReportType.IEP.value:
        return IEP_REPORT_SECTIONS
    if report_type == ClinicalReportType.MONTHLY.value:
        return MONTHLY_REPORT_SECTIONS
    return OBSERVATION_REPORT_SECTIONS


def serialize_section(sec: ClinicalReportSection, *, report_type: str = "observation") -> dict:
    catalog = _section_catalog(report_type)
    meta = next((m for m in catalog if m["key"] == sec.section_key), {})
    return {
        "key": sec.section_key,
        "label": sec.section_title,
        "prompt": meta.get("prompt", ""),
        "required": bool(meta.get("required")),
        "narrative_text": sec.narrative_text or "",
        "internal_notes": sec.internal_notes or "",
        "completion_status": sec.completion_status,
        "visibility": sec.visibility,
        "structured_data": json.loads(sec.structured_data_json) if sec.structured_data_json else {},
    }


def serialize_report_workspace(db: Session, report: ClinicalReport, case: Case) -> dict:
    if report.report_type == ClinicalReportType.IEP.value:
        from app.services import iep_approval_service

        iep_approval_service.apply_iep_auto_approvals(db)
    sections = list(
        db.scalars(
            select(ClinicalReportSection)
            .where(ClinicalReportSection.report_id == report.id)
            .order_by(ClinicalReportSection.section_order)
        ).all()
    )
    pct = completion_pct(sections)
    if report.report_type == ClinicalReportType.IEP.value:
        ready = required_iep_sections_complete(db, report)
        missing = missing_iep_required(db, report)
        catalog = IEP_REPORT_SECTIONS
    elif report.report_type == ClinicalReportType.MONTHLY.value:
        ready = required_monthly_sections_complete(sections)
        missing = missing_monthly_required_keys(sections)
        catalog = MONTHLY_REPORT_SECTIONS
    else:
        ready = required_sections_complete(sections)
        missing = missing_required_keys(sections)
        catalog = OBSERVATION_REPORT_SECTIONS
    today = date.today()
    due = report.due_date
    child_name = case.child.full_name if case.child else None
    payload = {
        "report_id": report.id,
        "case_id": report.case_id,
        "case_code": case.case_code,
        "child_name": child_name,
        "report_type": report.report_type,
        "title": report.title,
        "status": report.status,
        "due_at": due.isoformat() if due else None,
        "is_overdue": bool(due and due < today and report.status in (
            ClinicalReportStatus.DRAFT.value,
            ClinicalReportStatus.IN_PROGRESS.value,
            ClinicalReportStatus.RETURNED_FOR_CHANGES.value,
        )),
        "completion_pct": pct,
        "submit_ready": ready,
        "missing_required": missing,
        "sections": [serialize_section(s, report_type=report.report_type) for s in sections],
        "section_catalog": catalog,
        "submitted_at": report.submitted_at.isoformat() if report.submitted_at else None,
        "approved_at": report.approved_at.isoformat() if report.approved_at else None,
        "locked_at": report.locked_at.isoformat() if report.locked_at else None,
        "updated_at": report.updated_at.isoformat() if report.updated_at else None,
        "can_edit": report.status in (
            ClinicalReportStatus.DRAFT.value,
            ClinicalReportStatus.IN_PROGRESS.value,
            ClinicalReportStatus.RETURNED_FOR_CHANGES.value,
            ClinicalReportStatus.APPROVED.value,
        ),
        "can_submit": ready and report.status in (
            ClinicalReportStatus.DRAFT.value,
            ClinicalReportStatus.IN_PROGRESS.value,
            ClinicalReportStatus.RETURNED_FOR_CHANGES.value,
        ),
        "type_hooks": REPORT_TYPE_HOOKS,
    }
    if report.report_type == ClinicalReportType.MONTHLY.value:
        payload["month"] = _report_month_from_metadata(report)
    if report.report_type == ClinicalReportType.IEP.value:
        from app.services import iep_approval_service
        from app.services.iep_input_aggregation_service import aggregate_case_inputs

        payload["iep_approval"] = iep_approval_service.serialize_iep_approval(report)
        payload["review_thread"] = iep_approval_service.list_review_thread(db, report.id)
        payload["aggregated_inputs"] = aggregate_case_inputs(db, report.case_id)
    return payload


def get_active_iep_report(db: Session, case_id: int) -> ClinicalReport | None:
    return db.scalar(
        select(ClinicalReport).where(
            ClinicalReport.case_id == case_id,
            ClinicalReport.report_type == ClinicalReportType.IEP.value,
            ClinicalReport.archived_at.is_(None),
        )
    )


def iep_summary(db: Session, case: Case, user: User) -> dict:
    from app.services import iep_report_service

    report = get_active_iep_report(db, case.id)
    obs = get_active_observation_report(db, case.id)
    available = iep_report_service.list_available_goals_for_iep(db, case.id)

    if not report:
        return {
            "has_report": False,
            "report_id": None,
            "status": None,
            "status_label": "Not started",
            "can_start_new": True,
            "can_edit": False,
            "can_submit": False,
            "can_preview": False,
            "completion_pct": 0,
            "observation_status": obs.status if obs else None,
            "observation_approved": obs.status in (ClinicalReportStatus.APPROVED.value, ClinicalReportStatus.LOCKED.value) if obs else False,
            "available_goal_candidates": len(available.get("observation_candidates", [])) + len(available.get("repository_goals", [])),
            "available_strategy_candidates": len(available.get("case_goals", [])),
            "has_active_approved_iep": False,
            "pending_changes_count": 0,
        }

    sections = list(
        db.scalars(select(ClinicalReportSection).where(ClinicalReportSection.report_id == report.id)).all()
    )
    pct = completion_pct(sections)
    validation = iep_report_service.validate_iep_submit(db, report)
    pending = iep_report_service.list_pending_changes(db, report)
    editable = report.status in (
        ClinicalReportStatus.DRAFT.value,
        ClinicalReportStatus.IN_PROGRESS.value,
        ClinicalReportStatus.RETURNED_FOR_CHANGES.value,
        ClinicalReportStatus.APPROVED.value,
    )
    status_labels = {
        ClinicalReportStatus.DRAFT.value: "Draft",
        ClinicalReportStatus.IN_PROGRESS.value: "Draft",
        ClinicalReportStatus.SUBMITTED_FOR_REVIEW.value: "Pending CM approval",
        ClinicalReportStatus.RETURNED_FOR_CHANGES.value: "Revision needed",
        ClinicalReportStatus.APPROVED.value: "Active plan",
        ClinicalReportStatus.LOCKED.value: "Approved",
    }
    roles = {r.name for r in getattr(user, "roles", []) or []}
    is_cm = bool(roles & {"ADMIN", "SUPER_ADMIN", "CASE_MANAGER"}) or report.case_manager_id == user.id
    return {
        "has_report": True,
        "report_id": report.id,
        "status": report.status,
        "status_label": status_labels.get(report.status, report.status),
        "can_start_new": report.status in (ClinicalReportStatus.APPROVED.value, ClinicalReportStatus.LOCKED.value),
        "can_edit": editable and (report.assigned_therapist_id == user.id or is_cm),
        "can_submit": validation.get("ready") and editable and (report.assigned_therapist_id == user.id or is_cm),
        "can_preview": True,
        "completion_pct": pct,
        "observation_status": obs.status if obs else None,
        "observation_approved": obs.status in (ClinicalReportStatus.APPROVED.value, ClinicalReportStatus.LOCKED.value) if obs else False,
        "available_goal_candidates": len(available.get("observation_candidates", [])) + len(available.get("repository_goals", [])),
        "available_strategy_candidates": len(available.get("case_goals", [])),
        "has_active_approved_iep": report.status in (ClinicalReportStatus.APPROVED.value, ClinicalReportStatus.LOCKED.value),
        "pending_changes_count": len(pending),
        "submit_warnings": validation.get("warnings", []),
        "missing_required": validation.get("errors", []),
    }


def get_active_observation_report(db: Session, case_id: int) -> ClinicalReport | None:
    return db.scalar(
        select(ClinicalReport).where(
            ClinicalReport.case_id == case_id,
            ClinicalReport.report_type == ClinicalReportType.OBSERVATION.value,
            ClinicalReport.archived_at.is_(None),
        )
    )


_OBS_BULLET_SPLIT = re.compile(r"[,;\n]+")


def _split_observation_bullets(text: str | None, limit: int = 8) -> list[str]:
    if not text:
        return []
    parts = [p.strip() for p in _OBS_BULLET_SPLIT.split(str(text)) if p.strip()]
    return parts[:limit]


def _observation_structured(sec: ClinicalReportSection | None) -> dict:
    if not sec or not sec.structured_data_json:
        return {}
    try:
        return json.loads(sec.structured_data_json)
    except json.JSONDecodeError:
        return {}


def extract_observation_profile_signals(db: Session, case_id: int) -> dict:
    """Strengths, interests, and clinical pointers from the active observation report workspace."""
    report = get_active_observation_report(db, case_id)
    empty = {
        "strengths": [],
        "interests": [],
        "support_needs": [],
        "parent_priorities": [],
        "pointers": [],
        "summary_narrative": None,
        "has_observation": False,
    }
    if not report:
        return empty

    sections = list(
        db.scalars(select(ClinicalReportSection).where(ClinicalReportSection.report_id == report.id)).all()
    )
    by_key = {s.section_key: s for s in sections}

    si = _observation_structured(by_key.get("strengths_interests"))
    strengths = [str(x) for x in (si.get("strengths") or []) if x]
    if not strengths:
        strengths = _split_observation_bullets(
            by_key["strengths_interests"].narrative_text if by_key.get("strengths_interests") else None
        )
    interests = [str(x) for x in (si.get("interests") or []) if x]
    if not interests:
        interests = _split_observation_bullets(si.get("interests_text") or si.get("interests"))

    support_sec = by_key.get("support_needs")
    support_needs = _split_observation_bullets(support_sec.narrative_text if support_sec else None)

    parent_sec = by_key.get("parent_inputs")
    parent_priorities = _split_observation_bullets(parent_sec.narrative_text if parent_sec else None)

    child_snap = by_key.get("child_snapshot")
    summary_narrative = (child_snap.narrative_text or "").strip() if child_snap else None
    if not summary_narrative:
        ref = by_key.get("referral_background")
        summary_narrative = (ref.narrative_text or "").strip() if ref else None

    pointers: list[str] = []
    for key, label in (
        ("participation", "Participation"),
        ("communication", "Communication"),
        ("regulation_sensory", "Regulation & sensory"),
        ("learning_access", "Learning access"),
        ("environment_notes", "Environment"),
    ):
        sec = by_key.get(key)
        if not sec:
            continue
        text = (sec.narrative_text or "").strip()
        if not text:
            continue
        short = text if len(text) <= 120 else f"{text[:117]}…"
        pointers.append(f"{label}: {short}")

    return {
        "strengths": strengths[:8],
        "interests": interests[:8],
        "support_needs": support_needs[:8],
        "parent_priorities": parent_priorities[:6],
        "pointers": pointers[:5],
        "summary_narrative": summary_narrative,
        "has_observation": True,
    }


def observation_summary(db: Session, case: Case, user: User) -> dict:
    report = get_active_observation_report(db, case.id)
    checklist_comment = None
    if report:
        from app.models.clinical import ObservationChecklist

        checklist = db.scalar(select(ObservationChecklist).where(ObservationChecklist.case_id == case.id))
        if checklist and checklist.reviewer_comment:
            checklist_comment = checklist.reviewer_comment

    if not report:
        return {
            "has_report": False,
            "report_id": None,
            "status": None,
            "status_label": "Not started",
            "can_start_new": True,
            "can_edit": False,
            "can_submit": False,
            "can_preview": False,
            "completion_pct": 0,
            "submitted_at": None,
            "approved_at": None,
            "reviewer_comment": None,
            "due_at": None,
            "is_overdue": False,
        }

    sections = list(
        db.scalars(
            select(ClinicalReportSection).where(ClinicalReportSection.report_id == report.id)
        ).all()
    )
    pct = completion_pct(sections)
    ready = required_sections_complete(sections)
    today = date.today()
    due = report.due_date
    editable = report.status in (
        ClinicalReportStatus.DRAFT.value,
        ClinicalReportStatus.IN_PROGRESS.value,
        ClinicalReportStatus.RETURNED_FOR_CHANGES.value,
    )
    status_labels = {
        ClinicalReportStatus.DRAFT.value: "Draft",
        ClinicalReportStatus.IN_PROGRESS.value: "Draft",
        ClinicalReportStatus.SUBMITTED_FOR_REVIEW.value: "Pending CM approval",
        ClinicalReportStatus.RETURNED_FOR_CHANGES.value: "Revision needed",
        ClinicalReportStatus.APPROVED.value: "Approved",
        ClinicalReportStatus.LOCKED.value: "Approved",
    }
    return {
        "has_report": True,
        "report_id": report.id,
        "status": report.status,
        "status_label": status_labels.get(report.status, report.status),
        "can_start_new": report.status in (
            ClinicalReportStatus.APPROVED.value,
            ClinicalReportStatus.LOCKED.value,
        ),
        "can_edit": editable and report.assigned_therapist_id == user.id,
        "can_submit": ready and editable and report.assigned_therapist_id == user.id,
        "can_preview": True,
        "completion_pct": pct,
        "submitted_at": report.submitted_at.isoformat() if report.submitted_at else None,
        "approved_at": report.approved_at.isoformat() if report.approved_at else None,
        "reviewer_comment": checklist_comment if report.status == ClinicalReportStatus.RETURNED_FOR_CHANGES.value else None,
        "due_at": due.isoformat() if due else None,
        "is_overdue": bool(due and due < today and editable),
        "missing_required": missing_required_keys(sections),
    }


def serialize_parent_safe_iep(db: Session, report: ClinicalReport, case: Case) -> dict:
    ws = serialize_report_workspace(db, report, case)
    safe_sections = []
    for sec in ws["sections"]:
        if sec["key"] == "internal_cm_notes":
            continue
        if sec.get("visibility") == SectionVisibility.INTERNAL_ONLY.value:
            continue
        structured = sec.get("structured_data") or {}
        if sec["key"] == "goals_plan":
            goals = [
                g for g in structured.get("goals", [])
                if g.get("lifecycle_status") in ("active", "approved", "achieved")
                and g.get("status") != "pending_review"
            ]
            for g in goals:
                g.pop("cm_notes", None)
                g.pop("therapist_notes", None)
            structured = {**structured, "goals": goals, "pending_changes": []}
        if sec["key"] == "review_parent_plan":
            structured = {k: v for k, v in structured.items() if k != "internal_notes"}
        safe_sections.append({
            "key": sec["key"],
            "label": sec["label"],
            "narrative_text": sec.get("narrative_text") or "",
            "structured_data": structured,
        })
    return {
        "report_id": report.id,
        "case_id": case.id,
        "case_code": case.case_code,
        "child_name": case.child.full_name if case.child else "",
        "status": report.status,
        "title": report.title,
        "sections": safe_sections,
        "completion_pct": ws["completion_pct"],
        "submitted_at": ws["submitted_at"],
        "approved_at": ws["approved_at"],
        "preview_note": "Parent-safe preview — internal notes and pending changes excluded.",
        "mode": "parent",
    }


def serialize_parent_safe_observation(db: Session, report: ClinicalReport, case: Case) -> dict:
    ws = serialize_report_workspace(db, report, case)
    safe_sections = []
    for sec in ws["sections"]:
        if sec["key"] == "internal_notes":
            continue
        if sec.get("visibility") == SectionVisibility.INTERNAL_ONLY.value:
            continue
        safe_sections.append({
            "key": sec["key"],
            "label": sec["label"],
            "narrative_text": sec.get("narrative_text") or "",
            "structured_data": sec.get("structured_data") or {},
        })
    return {
        "report_id": report.id,
        "case_id": case.id,
        "case_code": case.case_code,
        "child_name": case.child.full_name if case.child else "",
        "status": report.status,
        "title": report.title,
        "sections": safe_sections,
        "completion_pct": ws["completion_pct"],
        "submitted_at": ws["submitted_at"],
        "approved_at": ws["approved_at"],
        "preview_note": "Parent-safe preview — internal notes excluded.",
    }


def monthly_summary(db: Session, case: Case, user: User, month: str) -> dict:
    month_key = _normalize_month_key(month)
    report = get_monthly_report_for_case_month(db, case.id, month_key)
    if not report:
        return {
            "has_report": False,
            "report_id": None,
            "month": month_key,
            "status": None,
            "status_label": "Not started",
            "can_start_new": True,
            "can_edit": False,
            "can_submit": False,
            "can_preview": False,
            "can_populate": False,
            "completion_pct": 0,
            "submitted_at": None,
            "approved_at": None,
            "locked_at": None,
        }

    sections = list(
        db.scalars(select(ClinicalReportSection).where(ClinicalReportSection.report_id == report.id)).all()
    )
    pct = completion_pct(sections)
    ready = required_monthly_sections_complete(sections)
    editable = report.status in (
        ClinicalReportStatus.DRAFT.value,
        ClinicalReportStatus.IN_PROGRESS.value,
        ClinicalReportStatus.RETURNED_FOR_CHANGES.value,
    )
    status_labels = {
        ClinicalReportStatus.DRAFT.value: "Draft",
        ClinicalReportStatus.IN_PROGRESS.value: "Draft",
        ClinicalReportStatus.SUBMITTED_FOR_REVIEW.value: "Submitted for CM review",
        ClinicalReportStatus.RETURNED_FOR_CHANGES.value: "Returned with comments",
        ClinicalReportStatus.APPROVED.value: "Approved",
        ClinicalReportStatus.LOCKED.value: "Visible to parent",
    }
    roles = {r.name for r in getattr(user, "roles", []) or []}
    is_cm = bool(roles & {"ADMIN", "SUPER_ADMIN", "CASE_MANAGER"}) or report.case_manager_id == user.id
    return {
        "has_report": True,
        "report_id": report.id,
        "month": month_key,
        "status": report.status,
        "status_label": status_labels.get(report.status, report.status),
        "can_start_new": False,
        "can_edit": editable and (report.assigned_therapist_id == user.id or is_cm),
        "can_submit": ready and editable and (report.assigned_therapist_id == user.id or is_cm),
        "can_preview": True,
        "can_populate": editable and (report.assigned_therapist_id == user.id or is_cm),
        "completion_pct": pct,
        "submitted_at": report.submitted_at.isoformat() if report.submitted_at else None,
        "approved_at": report.approved_at.isoformat() if report.approved_at else None,
        "locked_at": report.locked_at.isoformat() if report.locked_at else None,
        "missing_required": missing_monthly_required_keys(sections),
        "parent_visible_at": report.parent_visible_at.isoformat() if report.parent_visible_at else None,
    }


def parent_can_see_clinical_report(report: ClinicalReport) -> bool:
    """Whether a clinical report may be exposed to parents."""
    return report.status in (
        ClinicalReportStatus.APPROVED.value,
        ClinicalReportStatus.LOCKED.value,
    ) and bool(report.parent_visible_at or report.status == ClinicalReportStatus.LOCKED.value)


def serialize_parent_safe_monthly(db: Session, report: ClinicalReport, case: Case) -> dict:
    if not parent_can_see_clinical_report(report):
        raise ValueError("Report is not parent-visible")
    ws = serialize_report_workspace(db, report, case)
    safe_sections = []
    for sec in ws["sections"]:
        if sec["key"] in ("internal_notes", "therapist_notes"):
            continue
        if sec.get("visibility") == SectionVisibility.INTERNAL_ONLY.value:
            continue
        if sec.get("visibility") != SectionVisibility.PARENT_VISIBLE.value and sec["key"] != "parent_summary":
            # Include parent_summary always; other sections only if parent_visible or general clinical team content
            if sec["key"] not in (
                "child_summary",
                "sessions_summary",
                "goals_progress",
                "strategies_used",
                "strengths_observed",
                "support_needs",
                "barriers_or_context",
                "next_month_focus",
                "parent_summary",
            ):
                continue
        safe_sections.append({
            "key": sec["key"],
            "label": sec["label"],
            "narrative_text": sec.get("narrative_text") or "",
            "structured_data": sec.get("structured_data") or {},
        })
    return {
        "report_id": report.id,
        "case_id": case.id,
        "case_code": case.case_code,
        "child_name": case.child.full_name if case.child else "",
        "month": _report_month_from_metadata(report),
        "status": report.status,
        "title": report.title,
        "sections": safe_sections,
        "completion_pct": ws["completion_pct"],
        "submitted_at": ws["submitted_at"],
        "approved_at": ws["approved_at"],
        "preview_note": "Parent-safe monthly report — internal and draft content excluded.",
        "source": "clinical_reports",
    }


def case_dashboard(db: Session, case_id: int) -> dict:
    reports = list_case_reports(db, case_id)
    by_type = {r.report_type: r for r in reports}
    items = []
    for rtype, hook in REPORT_TYPE_HOOKS.items():
        row = by_type.get(rtype)
        items.append({
            "report_type": rtype,
            "implemented": hook.get("implemented", False),
            "status": row.status if row else None,
            "report_id": row.id if row else None,
            "completion_pct": completion_pct(
                list(db.scalars(select(ClinicalReportSection).where(ClinicalReportSection.report_id == row.id)).all())
            ) if row else 0,
        })
    return {"case_id": case_id, "reports": items}
