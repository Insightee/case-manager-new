"""Progress report engine — scoped evidence, status rules, refresh policy, parent bridge."""

from __future__ import annotations

import html as html_mod
import json
from datetime import date, datetime, time, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.clinical_report import (
    ClinicalReport,
    ClinicalReportSection,
    ClinicalReportStatus,
    ClinicalReportType,
    SectionVisibility,
)
from app.models.user import User
from app.report_engine_constants import PROGRESS_REPORT_SECTIONS, REQUIRED_PROGRESS_SECTION_KEYS
from app.services import report_status_service
from app.services.progress_evidence_scope_service import (
    EvidenceScope,
    aggregate_goal_metrics,
    build_evidence_summary_for_goal,
    list_scoped_approved_logs,
    list_scoped_monthly_reports,
    parse_scope_from_metadata,
    resolve_pinned_iep_snapshot,
)
from app.services.progress_status_rules import (
    build_suggested_summary,
    effective_goal_status,
    goal_ready_for_submit,
    normalize_final_status,
    suggest_goal_status,
    suggest_strategy_status,
)

PROGRESS_INTERVAL_DAYS = 182

ACTIVE_PROGRESS_STATUSES = frozenset({
    ClinicalReportStatus.DRAFT.value,
    ClinicalReportStatus.IN_PROGRESS.value,
    ClinicalReportStatus.RETURNED_FOR_CHANGES.value,
    ClinicalReportStatus.SUBMITTED_FOR_REVIEW.value,
})

CONTENT_ORIGIN_SYSTEM = "SYSTEM_GENERATED"
CONTENT_ORIGIN_THERAPIST = "THERAPIST_EDITED"
CONTENT_ORIGIN_CM = "CM_EDITED"

PARENT_SAFE_SECTION_KEYS = frozenset({
    "period_overview",
    "goals_progress",
    "strengths_and_development",
    "strategies_and_supports",
    "challenges_and_support_needs",
    "family_school_input",
    "next_period_plan",
    "parent_summary",
})

GOAL_INTERNAL_KEYS = frozenset({
    "suggested_status",
    "suggested_summary",
    "therapist_rationale",
    "evidence_summary",
    "status_confirmed",
})


def _json_loads(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def _json_dumps(data: dict) -> str:
    return json.dumps(data)


def _esc(text: str | None) -> str:
    return html_mod.escape((text or "").strip())


def get_progress_metadata(report: ClinicalReport) -> dict:
    return _json_loads(report.metadata_json)


def set_progress_metadata(db: Session, report: ClinicalReport, updates: dict) -> dict:
    meta = get_progress_metadata(report)
    meta.update(updates)
    report.metadata_json = _json_dumps(meta)
    db.flush()
    return meta


def report_period_from_metadata(report: ClinicalReport) -> dict[str, str | None]:
    meta = get_progress_metadata(report)
    return {
        "start": meta.get("review_period_start") or meta.get("period_start"),
        "end": meta.get("review_period_end") or meta.get("period_end"),
    }


def get_workflow_progress_report(db: Session, case_id: int) -> ClinicalReport | None:
    return db.scalar(
        select(ClinicalReport)
        .where(
            ClinicalReport.case_id == case_id,
            ClinicalReport.report_type == ClinicalReportType.PROGRESS.value,
            ClinicalReport.status.in_(ACTIVE_PROGRESS_STATUSES),
            ClinicalReport.archived_at.is_(None),
        )
        .order_by(ClinicalReport.id.desc())
    )


def get_latest_progress_report(db: Session, case_id: int) -> ClinicalReport | None:
    return db.scalar(
        select(ClinicalReport)
        .where(
            ClinicalReport.case_id == case_id,
            ClinicalReport.report_type == ClinicalReportType.PROGRESS.value,
            ClinicalReport.archived_at.is_(None),
        )
        .order_by(ClinicalReport.id.desc())
    )


def get_active_progress_report(db: Session, case_id: int) -> ClinicalReport | None:
    """Prefer in-workflow report; fall back to latest locked/approved for hub display."""
    workflow = get_workflow_progress_report(db, case_id)
    if workflow:
        return workflow
    return get_latest_progress_report(db, case_id)


def progress_period_bounds(db: Session, case: Case) -> tuple[date, date]:
    from datetime import timedelta

    end = date.today()
    last_approved = db.scalar(
        select(ClinicalReport)
        .where(
            ClinicalReport.case_id == case.id,
            ClinicalReport.report_type == ClinicalReportType.PROGRESS.value,
            ClinicalReport.status.in_((ClinicalReportStatus.APPROVED.value, ClinicalReportStatus.LOCKED.value)),
        )
        .order_by(ClinicalReport.approved_at.desc())
    )
    if last_approved:
        meta = get_progress_metadata(last_approved)
        prior_end = meta.get("review_period_end") or meta.get("period_end")
        if prior_end:
            try:
                return date.fromisoformat(prior_end) + timedelta(days=1), end
            except ValueError:
                pass
    start = case.created_at.date() if case.created_at else end - timedelta(days=PROGRESS_INTERVAL_DAYS)
    return start, end


def _initial_metadata(db: Session, case: Case, *, supersedes: int | None = None) -> dict:
    period_start, period_end = progress_period_bounds(db, case)
    cutoff = datetime.combine(period_end, time(23, 59, 59), tzinfo=timezone.utc)
    return {
        "review_period_start": period_start.isoformat(),
        "review_period_end": period_end.isoformat(),
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "evidence_cutoff_at": cutoff.isoformat(),
        "source_iep_report_id": None,
        "source_iep_version_id": None,
        "supersedes_report_id": supersedes,
    }


def get_or_create_progress_report(db: Session, case: Case, user: User) -> ClinicalReport:
    existing = get_workflow_progress_report(db, case.id)
    if existing:
        from app.services.report_engine_service import seed_progress_sections

        seed_progress_sections(db, existing.id)
        return existing
    period_start, period_end = progress_period_bounds(db, case)
    child_name = case.child.full_name if case.child else "Client"
    meta = _initial_metadata(db, case)
    row = ClinicalReport(
        case_id=case.id,
        child_id=case.child_id,
        report_type=ClinicalReportType.PROGRESS.value,
        title=f"Progress Report — {child_name} ({period_start.isoformat()} to {period_end.isoformat()})",
        status=ClinicalReportStatus.DRAFT.value,
        created_by_id=user.id,
        assigned_therapist_id=user.id,
        case_manager_id=case.case_manager_user_id,
        metadata_json=_json_dumps(meta),
    )
    db.add(row)
    db.flush()
    from app.services.report_engine_service import seed_progress_sections

    seed_progress_sections(db, row.id)
    report_status_service.log_review_event(db, row, user, "created")
    return row


def start_next_cycle(db: Session, case: Case, user: User) -> ClinicalReport:
    latest = get_latest_progress_report(db, case.id)
    if latest and latest.status not in (ClinicalReportStatus.APPROVED.value, ClinicalReportStatus.LOCKED.value):
        raise ValueError("Complete and approve the current progress report before starting a new cycle")
    if get_workflow_progress_report(db, case.id):
        raise ValueError("An active progress report draft already exists")
    period_start, period_end = progress_period_bounds(db, case)
    child_name = case.child.full_name if case.child else "Client"
    meta = _initial_metadata(db, case)
    row = ClinicalReport(
        case_id=case.id,
        child_id=case.child_id,
        report_type=ClinicalReportType.PROGRESS.value,
        title=f"Progress Report — {child_name} ({period_start.isoformat()} to {period_end.isoformat()})",
        status=ClinicalReportStatus.DRAFT.value,
        created_by_id=user.id,
        assigned_therapist_id=user.id,
        case_manager_id=case.case_manager_user_id,
        metadata_json=_json_dumps(meta),
    )
    db.add(row)
    db.flush()
    from app.services.report_engine_service import seed_progress_sections

    seed_progress_sections(db, row.id)
    report_status_service.log_review_event(db, row, user, "created", metadata={"cycle": "next"})
    return row


def start_correction_cycle(db: Session, case: Case, user: User, *, locked_report_id: int) -> ClinicalReport:
    locked = db.get(ClinicalReport, locked_report_id)
    if not locked or locked.case_id != case.id or locked.report_type != ClinicalReportType.PROGRESS.value:
        raise ValueError("Locked progress report not found")
    if locked.status not in (ClinicalReportStatus.APPROVED.value, ClinicalReportStatus.LOCKED.value):
        raise ValueError("Corrections can only be started from an approved progress report")
    if get_workflow_progress_report(db, case.id):
        raise ValueError("An active progress report draft already exists")
    meta = _initial_metadata(db, case, supersedes=locked.id)
    meta["review_period_start"] = get_progress_metadata(locked).get("review_period_start") or meta["review_period_start"]
    meta["review_period_end"] = get_progress_metadata(locked).get("review_period_end") or meta["review_period_end"]
    meta["period_start"] = meta["review_period_start"]
    meta["period_end"] = meta["review_period_end"]
    meta["source_iep_report_id"] = get_progress_metadata(locked).get("source_iep_report_id")
    meta["source_iep_version_id"] = get_progress_metadata(locked).get("source_iep_version_id")
    meta["evidence_cutoff_at"] = get_progress_metadata(locked).get("evidence_cutoff_at") or meta["evidence_cutoff_at"]
    child_name = case.child.full_name if case.child else "Client"
    row = ClinicalReport(
        case_id=case.id,
        child_id=case.child_id,
        report_type=ClinicalReportType.PROGRESS.value,
        title=f"Progress Report (Correction) — {child_name}",
        status=ClinicalReportStatus.DRAFT.value,
        created_by_id=user.id,
        assigned_therapist_id=user.id,
        case_manager_id=case.case_manager_user_id,
        metadata_json=_json_dumps(meta),
    )
    db.add(row)
    db.flush()
    from app.services.report_engine_service import seed_progress_sections

    seed_progress_sections(db, row.id)
    report_status_service.log_review_event(
        db, row, user, "created", metadata={"cycle": "correction", "supersedes_report_id": locked.id}
    )
    return row


def can_populate_or_refresh(report: ClinicalReport) -> bool:
    return report.status in (
        ClinicalReportStatus.DRAFT.value,
        ClinicalReportStatus.IN_PROGRESS.value,
        ClinicalReportStatus.RETURNED_FOR_CHANGES.value,
    )


def _section_struct_with_meta(structured: dict | None, *, origin: str) -> dict:
    data = dict(structured or {})
    meta = dict(data.get("_meta") or {})
    meta["content_origin"] = origin
    meta["last_populated_at"] = datetime.now(timezone.utc).isoformat()
    data["_meta"] = meta
    return data


def _get_section_origin(sec: ClinicalReportSection | None) -> str:
    if not sec or not sec.structured_data_json:
        return CONTENT_ORIGIN_SYSTEM
    data = _json_loads(sec.structured_data_json)
    return str((data.get("_meta") or {}).get("content_origin") or CONTENT_ORIGIN_SYSTEM)


def _merge_goal_preserving_edits(existing: dict | None, fresh: dict) -> dict:
    prior = existing or {}
    merged = {**fresh}
    for key in ("final_status", "final_summary", "therapist_rationale", "status_confirmed"):
        if prior.get(key) is not None:
            merged[key] = prior[key]
    return merged


def _build_population_payload(
    db: Session,
    report: ClinicalReport,
    scope: EvidenceScope,
) -> dict[str, Any]:
    scoped_logs = list_scoped_approved_logs(db, report.case_id, scope)
    monthly_reports = list_scoped_monthly_reports(db, report.case_id, scope)
    monthly_ids = [m.id for m in monthly_reports]
    goal_metrics, strategy_metrics = aggregate_goal_metrics(db, scope, scoped_logs, scope.iep_goals)

    goal_reviews = []
    for metrics in goal_metrics:
        summary = build_suggested_summary(metrics)
        evidence_summary = build_evidence_summary_for_goal(metrics, monthly_ids)
        goal_reviews.append({
            "goal_id": metrics.get("goal_id"),
            "label": metrics.get("label"),
            "domain_key": metrics.get("domain_key"),
            "suggested_status": metrics.get("suggested_status") or suggest_goal_status(metrics),
            "final_status": None,
            "suggested_summary": summary,
            "final_summary": None,
            "therapist_rationale": None,
            "status_confirmed": False,
            "status": metrics.get("suggested_status"),
            "sessions_addressed": metrics.get("sessions_addressed") or 0,
            "strategies_used": metrics.get("strategies_used") or [],
            "environments": metrics.get("environments") or [],
            "evidence_summary": evidence_summary,
        })

    goal_lines = "".join(
        f"<li><strong>{_esc(g['label'])}</strong> — {_esc(effective_goal_status(g))} "
        f"({g['sessions_addressed']} session(s) addressed)</li>"
        for g in goal_reviews
    )
    goal_progress_narrative = (
        f"<ul>{goal_lines}</ul>" if goal_lines else "<p><em>No active goals with evidence yet.</em></p>"
    )

    strat_lines = "".join(
        f"<li><strong>{_esc(s['label'])}</strong> — {_esc(s.get('suggested_status') or suggest_strategy_status(s))}</li>"
        for s in strategy_metrics
    )
    strategies_html = f"<ul>{strat_lines}</ul>" if strat_lines else "<p><em>No strategy use recorded yet.</em></p>"

    overview_parts = [
        f"Review period: {scope.review_period_start.isoformat()} to {scope.review_period_end.isoformat()}.",
        f"{len(monthly_reports)} approved monthly report(s) and {len(scoped_logs)} approved session log(s) in this period.",
    ]
    overview_html = f"<p>{_esc(' '.join(overview_parts))}</p>"

    return {
        "sections_data": {
            "period_overview": (overview_html, _section_struct_with_meta(None, origin=CONTENT_ORIGIN_SYSTEM)),
            "goals_progress": (
                goal_progress_narrative,
                _section_struct_with_meta({"goals": goal_reviews}, origin=CONTENT_ORIGIN_SYSTEM),
            ),
            "strengths_and_development": (
                "<p><em>Add strengths and development observed this period.</em></p>",
                _section_struct_with_meta(None, origin=CONTENT_ORIGIN_SYSTEM),
            ),
            "strategies_and_supports": (
                strategies_html,
                _section_struct_with_meta({"strategies": strategy_metrics}, origin=CONTENT_ORIGIN_SYSTEM),
            ),
            "challenges_and_support_needs": (
                "<p><em>Add challenges or support needs as needed.</em></p>",
                _section_struct_with_meta(None, origin=CONTENT_ORIGIN_SYSTEM),
            ),
            "family_school_input": (
                "<p><em>No parent or school input recorded for this period.</em></p>",
                _section_struct_with_meta(None, origin=CONTENT_ORIGIN_SYSTEM),
            ),
            "next_period_plan": (
                "<p><em>Add the plan for the next period.</em></p>",
                _section_struct_with_meta(None, origin=CONTENT_ORIGIN_SYSTEM),
            ),
            "therapist_reflection": (
                "<p><em>Therapist reflection (internal only).</em></p>",
                _section_struct_with_meta(None, origin=CONTENT_ORIGIN_SYSTEM),
            ),
            "parent_summary": (
                "<p><em>Draft parent-facing summary — review before publish.</em></p>",
                _section_struct_with_meta(None, origin=CONTENT_ORIGIN_SYSTEM),
            ),
        },
        "scoped_log_count": len(scoped_logs),
        "scoped_monthly_ids": monthly_ids,
        "source_iep_version_id": scope.source_iep_version_id,
        "goal_count": len(goal_reviews),
    }


def populate_progress_from_evidence(db: Session, report: ClinicalReport) -> dict:
    from app.services.report_engine_service import patch_section, seed_progress_sections

    if report.report_type != ClinicalReportType.PROGRESS.value:
        raise ValueError("Not a progress clinical report")
    if not can_populate_or_refresh(report):
        raise ValueError("Cannot populate evidence while report is under review or locked")
    seed_progress_sections(db, report.id)

    scope = parse_scope_from_metadata(report)
    scope = resolve_pinned_iep_snapshot(db, report.case_id, existing=scope)
    if not get_progress_metadata(report).get("evidence_cutoff_at"):
        set_progress_metadata(db, report, {
            "evidence_cutoff_at": scope.evidence_cutoff_at.isoformat(),
            "source_iep_report_id": scope.source_iep_report_id,
            "source_iep_version_id": scope.source_iep_version_id,
        })
    else:
        set_progress_metadata(db, report, {
            "source_iep_report_id": scope.source_iep_report_id,
            "source_iep_version_id": scope.source_iep_version_id,
        })

    payload = _build_population_payload(db, report, scope)
    for key, (html, structured) in payload["sections_data"].items():
        try:
            patch_section(db, report, key, narrative_text=html, structured_data=structured)
        except ValueError:
            continue

    if report.status == ClinicalReportStatus.DRAFT.value:
        report.status = ClinicalReportStatus.IN_PROGRESS.value
    db.flush()
    return {
        "report_id": report.id,
        "sections_populated": list(payload["sections_data"].keys()),
        "goal_count": payload["goal_count"],
        "monthly_report_count": len(payload["scoped_monthly_ids"]),
        "session_count": payload["scoped_log_count"],
        "scoped_log_count": payload["scoped_log_count"],
        "scoped_monthly_ids": payload["scoped_monthly_ids"],
        "source_iep_version_id": payload["source_iep_version_id"],
    }


def refresh_progress_evidence(db: Session, report: ClinicalReport) -> dict:
    from app.services.report_engine_service import patch_section, seed_progress_sections

    if report.report_type != ClinicalReportType.PROGRESS.value:
        raise ValueError("Not a progress clinical report")
    if not can_populate_or_refresh(report):
        raise ValueError("Cannot refresh evidence while report is under review or locked")
    seed_progress_sections(db, report.id)

    scope = parse_scope_from_metadata(report)
    pinned_meta = get_progress_metadata(report)
    if pinned_meta.get("source_iep_report_id"):
        scope.source_iep_report_id = pinned_meta.get("source_iep_report_id")
        scope.source_iep_version_id = pinned_meta.get("source_iep_version_id")
    scope = resolve_pinned_iep_snapshot(db, report.case_id, existing=scope)

    payload = _build_population_payload(db, report, scope)
    refresh_preview: list[dict] = []

    for key, (new_html, new_structured) in payload["sections_data"].items():
        sec = db.scalar(
            select(ClinicalReportSection).where(
                ClinicalReportSection.report_id == report.id,
                ClinicalReportSection.section_key == key,
            )
        )
        origin = _get_section_origin(sec)
        old_html = sec.narrative_text if sec else None
        old_struct = _json_loads(sec.structured_data_json) if sec and sec.structured_data_json else {}

        if origin in (CONTENT_ORIGIN_THERAPIST, CONTENT_ORIGIN_CM):
            refresh_preview.append({
                "section_key": key,
                "before": old_html,
                "after": old_html,
                "skipped_reason": f"Section origin is {origin}",
            })
            continue

        if key == "goals_progress" and new_structured:
            existing_goals = {str(g.get("goal_id") or g.get("label")): g for g in (old_struct.get("goals") or [])}
            merged_goals = []
            for g in new_structured.get("goals") or []:
                gid = str(g.get("goal_id") or g.get("label"))
                merged_goals.append(_merge_goal_preserving_edits(existing_goals.get(gid), g))
            new_structured = _section_struct_with_meta({"goals": merged_goals}, origin=CONTENT_ORIGIN_SYSTEM)

        try:
            patch_section(db, report, key, narrative_text=new_html, structured_data=new_structured)
            refresh_preview.append({
                "section_key": key,
                "before": old_html,
                "after": new_html,
                "skipped_reason": None,
            })
        except ValueError:
            refresh_preview.append({
                "section_key": key,
                "before": old_html,
                "after": old_html,
                "skipped_reason": "Section not found",
            })

    db.flush()
    return {
        "report_id": report.id,
        "refresh_preview": refresh_preview,
        "scoped_log_count": payload["scoped_log_count"],
        "scoped_monthly_ids": payload["scoped_monthly_ids"],
        "source_iep_version_id": payload["source_iep_version_id"],
    }


def patch_progress_section(
    db: Session,
    report: ClinicalReport,
    section_key: str,
    user: User,
    *,
    narrative_text: str | None = None,
    structured_data: dict | None = None,
    origin: str = CONTENT_ORIGIN_THERAPIST,
) -> ClinicalReportSection:
    from app.services.report_engine_service import patch_section

    if report.report_type != ClinicalReportType.PROGRESS.value:
        raise ValueError("Not a progress report")
    if not report_status_service.can_therapist_edit(report, user):
        raise ValueError("Cannot edit this report")
    if structured_data is not None:
        data = dict(structured_data)
        meta = dict(data.get("_meta") or {})
        meta["content_origin"] = origin
        meta["last_edited_by_id"] = user.id
        meta["last_edited_at"] = datetime.now(timezone.utc).isoformat()
        data["_meta"] = meta
        structured_data = data
    elif narrative_text is not None:
        sec = db.scalar(
            select(ClinicalReportSection).where(
                ClinicalReportSection.report_id == report.id,
                ClinicalReportSection.section_key == section_key,
            )
        )
        existing = _json_loads(sec.structured_data_json) if sec and sec.structured_data_json else {}
        meta = dict(existing.get("_meta") or {})
        meta["content_origin"] = origin
        meta["last_edited_by_id"] = user.id
        meta["last_edited_at"] = datetime.now(timezone.utc).isoformat()
        existing["_meta"] = meta
        structured_data = existing
    return patch_section(db, report, section_key, narrative_text=narrative_text, structured_data=structured_data)


def patch_progress_goal(
    db: Session,
    report: ClinicalReport,
    goal_id: str | int,
    user: User,
    *,
    final_status: str | None = None,
    final_summary: str | None = None,
    therapist_rationale: str | None = None,
    status_confirmed: bool | None = None,
) -> dict:
    sec = db.scalar(
        select(ClinicalReportSection).where(
            ClinicalReportSection.report_id == report.id,
            ClinicalReportSection.section_key == "goals_progress",
        )
    )
    if not sec:
        raise ValueError("Goals progress section not found")
    data = _json_loads(sec.structured_data_json)
    goals = data.get("goals") or []
    target = None
    for g in goals:
        if str(g.get("goal_id")) == str(goal_id):
            target = g
            break
    if not target:
        raise ValueError("Goal not found on this progress report")
    if final_status is not None:
        target["final_status"] = normalize_final_status(final_status)
    if final_summary is not None:
        target["final_summary"] = final_summary.strip()
    if therapist_rationale is not None:
        target["therapist_rationale"] = therapist_rationale.strip()
    if status_confirmed is not None:
        target["status_confirmed"] = bool(status_confirmed)
    data["goals"] = goals
    patch_progress_section(db, report, "goals_progress", user, structured_data=data)
    return target


def validate_progress_submit(db: Session, report: ClinicalReport) -> dict:
    from app.services.report_engine_service import missing_progress_required_keys, required_progress_sections_complete

    sections = list(db.scalars(select(ClinicalReportSection).where(ClinicalReportSection.report_id == report.id)).all())
    ready = required_progress_sections_complete(sections)
    missing = missing_progress_required_keys(sections)
    goals_sec = next((s for s in sections if s.section_key == "goals_progress"), None)
    goals = (_json_loads(goals_sec.structured_data_json).get("goals") if goals_sec else []) or []
    pending_goals = [g.get("label") for g in goals if not goal_ready_for_submit(g)]
    return {
        "ready": ready and not pending_goals,
        "missing_sections": missing,
        "pending_goal_confirmations": pending_goals,
    }


def get_goal_evidence_detail(db: Session, report: ClinicalReport, goal_id: str | int) -> dict:
    sec = db.scalar(
        select(ClinicalReportSection).where(
            ClinicalReportSection.report_id == report.id,
            ClinicalReportSection.section_key == "goals_progress",
        )
    )
    if not sec:
        raise ValueError("Goals progress section not found")
    data = _json_loads(sec.structured_data_json)
    for g in data.get("goals") or []:
        if str(g.get("goal_id")) == str(goal_id):
            summary = g.get("evidence_summary") or {}
            return {
                "goal_id": g.get("goal_id"),
                "label": g.get("label"),
                "evidence_summary": summary,
                "sessions": [
                    {"date": d}
                    for d in (summary.get("session_dates") or [])
                ],
            }
    raise ValueError("Goal not found on this progress report")


def progress_summary(db: Session, case: Case, user: User) -> dict:
    from app.services.report_engine_service import (
        completion_pct,
        missing_progress_required_keys,
        required_progress_sections_complete,
    )

    report = get_workflow_progress_report(db, case.id)
    if not report:
        start, end = progress_period_bounds(db, case)
        latest = get_latest_progress_report(db, case.id)
        can_start = not latest or latest.status in (
            ClinicalReportStatus.APPROVED.value,
            ClinicalReportStatus.LOCKED.value,
        )
        return {
            "has_report": False,
            "report_id": None,
            "status": None,
            "status_label": "Not started",
            "can_start_new": can_start,
            "can_edit": False,
            "can_submit": False,
            "can_preview": bool(latest),
            "can_populate": False,
            "can_refresh": False,
            "completion_pct": 0,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "latest_report_id": latest.id if latest else None,
        }
    sections = list(db.scalars(select(ClinicalReportSection).where(ClinicalReportSection.report_id == report.id)).all())
    pct = completion_pct(sections)
    ready = required_progress_sections_complete(sections)
    validation = validate_progress_submit(db, report)
    editable = report.status in (
        ClinicalReportStatus.DRAFT.value,
        ClinicalReportStatus.IN_PROGRESS.value,
        ClinicalReportStatus.RETURNED_FOR_CHANGES.value,
    )
    status_labels = {
        ClinicalReportStatus.DRAFT.value: "Draft",
        ClinicalReportStatus.IN_PROGRESS.value: "Draft",
        ClinicalReportStatus.SUBMITTED_FOR_REVIEW.value: "Submitted",
        ClinicalReportStatus.RETURNED_FOR_CHANGES.value: "Changes requested",
        ClinicalReportStatus.APPROVED.value: "Approved",
        ClinicalReportStatus.LOCKED.value: "Shared" if report.parent_visible_at else "Approved",
    }
    roles = {r.name for r in getattr(user, "roles", []) or []}
    is_cm = bool(roles & {"ADMIN", "SUPER_ADMIN", "CASE_MANAGER"}) or report.case_manager_id == user.id
    period = report_period_from_metadata(report)
    return {
        "has_report": True,
        "report_id": report.id,
        "status": report.status,
        "status_label": status_labels.get(report.status, report.status),
        "can_start_new": False,
        "can_edit": editable and (report.assigned_therapist_id == user.id or is_cm),
        "can_submit": validation["ready"] and editable and (report.assigned_therapist_id == user.id or is_cm),
        "can_preview": True,
        "can_populate": editable and can_populate_or_refresh(report) and (report.assigned_therapist_id == user.id or is_cm),
        "can_refresh": editable and can_populate_or_refresh(report) and (report.assigned_therapist_id == user.id or is_cm),
        "completion_pct": pct,
        "period_start": period["start"],
        "period_end": period["end"],
        "submitted_at": report.submitted_at.isoformat() if report.submitted_at else None,
        "approved_at": report.approved_at.isoformat() if report.approved_at else None,
        "missing_required": missing_progress_required_keys(sections),
        "pending_goal_confirmations": validation.get("pending_goal_confirmations") or [],
        "parent_visible_at": report.parent_visible_at.isoformat() if report.parent_visible_at else None,
    }


def _parent_safe_goal(goal: dict) -> dict:
    return {
        "goal_id": goal.get("goal_id"),
        "label": goal.get("label"),
        "domain_key": goal.get("domain_key"),
        "status": effective_goal_status(goal),
        "summary": goal.get("final_summary") or goal.get("suggested_summary") or "",
        "sessions_addressed": goal.get("sessions_addressed") or 0,
        "strategies_used": goal.get("strategies_used") or [],
        "environments": goal.get("environments") or [],
    }


def serialize_parent_safe_progress(db: Session, report: ClinicalReport, case: Case) -> dict:
    from app.services.report_engine_service import parent_can_see_clinical_report, serialize_report_workspace

    if not parent_can_see_clinical_report(report):
        raise ValueError("Report is not parent-visible")
    ws = serialize_report_workspace(db, report, case)
    safe_sections = []
    for sec in ws["sections"]:
        if sec["key"] not in PARENT_SAFE_SECTION_KEYS:
            continue
        structured = sec.get("structured_data") or {}
        if sec["key"] == "goals_progress":
            structured = {"goals": [_parent_safe_goal(g) for g in (structured.get("goals") or [])]}
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
        "period": report_period_from_metadata(report),
        "status": report.status,
        "title": report.title,
        "sections": safe_sections,
        "completion_pct": ws["completion_pct"],
        "submitted_at": ws["submitted_at"],
        "approved_at": ws["approved_at"],
        "preview_note": "Parent-safe progress report — internal notes and draft content excluded.",
        "source": "clinical_reports",
    }


def progress_snapshot_metadata(report: ClinicalReport) -> dict:
    meta = get_progress_metadata(report)
    return {
        "review_period_start": meta.get("review_period_start") or meta.get("period_start"),
        "review_period_end": meta.get("review_period_end") or meta.get("period_end"),
        "evidence_cutoff_at": meta.get("evidence_cutoff_at"),
        "source_iep_report_id": meta.get("source_iep_report_id"),
        "source_iep_version_id": meta.get("source_iep_version_id"),
        "supersedes_report_id": meta.get("supersedes_report_id"),
    }
