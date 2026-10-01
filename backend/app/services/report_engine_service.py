from __future__ import annotations

import html as html_lib
import json
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
from app.core.permissions import RoleName
from app.report_engine_constants import (
    IEP_REPORT_SECTIONS,
    LEGACY_CHECKLIST_KEY_MAP,
    OBSERVATION_REPORT_SECTIONS,
    REQUIRED_IEP_SECTION_KEYS,
    REQUIRED_OBSERVATION_SECTION_KEYS,
    REPORT_TYPE_HOOKS,
)
from app.services import report_status_service

PARENT_VISIBLE_STATUSES = frozenset(
    {
        ClinicalReportStatus.SUBMITTED_FOR_REVIEW.value,
        ClinicalReportStatus.APPROVED.value,
        ClinicalReportStatus.LOCKED.value,
    }
)


def user_is_parent(user: User) -> bool:
    return RoleName.PARENT.value in (user.role_names or [])


def parent_may_view_report(report: ClinicalReport | None) -> bool:
    return bool(
        report
        and report.parent_visible_at
        and report.status in PARENT_VISIBLE_STATUSES
    )


def parent_share_flags(report: ClinicalReport | None, user: User) -> dict:
    shared = bool(report and report.parent_visible_at)
    can_share = bool(
        report
        and not user_is_parent(user)
        and report.status in PARENT_VISIBLE_STATUSES
        and not shared
    )
    return {
        "shared_with_parent": shared,
        "can_share_with_parent": can_share,
    }


def _section_visibility(meta: dict) -> str:
    if meta.get("visibility") == "internal_only":
        return SectionVisibility.INTERNAL_ONLY.value
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
        if report.report_type == ClinicalReportType.IEP.value and section_key == "review_parent_plan":
            existing = json.loads(sec.structured_data_json) if sec.structured_data_json else {}
            if existing.get("review_date_locked") and structured_data.get("review_date") != existing.get("review_date"):
                raise ValueError("Review date for next IEP is locked after case manager approval.")
            if existing.get("review_date_locked"):
                structured_data = {**structured_data, "review_date_locked": True}
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
        "can_submit": report.status in (
            ClinicalReportStatus.DRAFT.value,
            ClinicalReportStatus.IN_PROGRESS.value,
            ClinicalReportStatus.RETURNED_FOR_CHANGES.value,
        ),
        "type_hooks": REPORT_TYPE_HOOKS,
        "shared_with_parent": bool(report.parent_visible_at),
    }
    if report.report_type == ClinicalReportType.IEP.value:
        from app.services import iep_approval_service

        payload["iep_approval"] = iep_approval_service.serialize_iep_approval(report)
        payload["review_thread"] = iep_approval_service.list_review_thread(db, report.id)
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
            "can_start_new": not user_is_parent(user),
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
            **parent_share_flags(None, user),
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
    is_cm = bool(roles & {"ADMIN", "SUPER_ADMIN", "CASE_MANAGER", "SUPERVISOR"}) or report.case_manager_id == user.id
    is_parent = user_is_parent(user)
    from app.services.iep_reminder_service import iep_period_label, list_iep_versions_for_case

    payload = {
        "has_report": True,
        "report_id": report.id,
        "status": report.status,
        "status_label": status_labels.get(report.status, report.status),
        "period_label": iep_period_label(report),
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "iep_versions": list_iep_versions_for_case(db, case.id),
        "can_start_new": report.status in (ClinicalReportStatus.APPROVED.value, ClinicalReportStatus.LOCKED.value),
        "can_edit": editable and (report.assigned_therapist_id == user.id or is_cm),
        "can_submit": editable and (report.assigned_therapist_id == user.id or is_cm),
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
        **parent_share_flags(report, user),
    }
    if is_parent:
        payload["can_start_new"] = False
        payload["can_edit"] = False
        payload["can_submit"] = False
        payload["can_preview"] = parent_may_view_report(report)
        payload["pending_changes_count"] = 0
        payload["available_goal_candidates"] = 0
        if not payload["can_preview"]:
            payload["has_report"] = False
            payload["report_id"] = None
            payload["status"] = None
            payload["status_label"] = "Not started"
            payload["has_active_approved_iep"] = False
            payload["completion_pct"] = 0
    return payload


def get_active_observation_report(db: Session, case_id: int) -> ClinicalReport | None:
    return db.scalar(
        select(ClinicalReport).where(
            ClinicalReport.case_id == case_id,
            ClinicalReport.report_type == ClinicalReportType.OBSERVATION.value,
            ClinicalReport.archived_at.is_(None),
        )
    )


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
            "can_start_new": not user_is_parent(user),
            "can_edit": False,
            "can_submit": False,
            "can_preview": False,
            "completion_pct": 0,
            "submitted_at": None,
            "approved_at": None,
            "reviewer_comment": None,
            "due_at": None,
            "is_overdue": False,
            **parent_share_flags(None, user),
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
    roles = {r.name for r in getattr(user, "roles", []) or []}
    is_cm = bool(roles & {"ADMIN", "SUPER_ADMIN", "CASE_MANAGER", "SUPERVISOR"}) or report.case_manager_id == user.id
    payload = {
        "has_report": True,
        "report_id": report.id,
        "status": report.status,
        "status_label": status_labels.get(report.status, report.status),
        "can_start_new": report.status in (
            ClinicalReportStatus.APPROVED.value,
            ClinicalReportStatus.LOCKED.value,
        ),
        "can_edit": editable and (report.assigned_therapist_id == user.id or is_cm),
        "can_submit": ready and editable and report.assigned_therapist_id == user.id,
        "can_preview": True,
        "completion_pct": pct,
        "submitted_at": report.submitted_at.isoformat() if report.submitted_at else None,
        "approved_at": report.approved_at.isoformat() if report.approved_at else None,
        "reviewer_comment": checklist_comment if report.status == ClinicalReportStatus.RETURNED_FOR_CHANGES.value else None,
        "due_at": due.isoformat() if due else None,
        "is_overdue": bool(due and due < today and editable),
        "missing_required": missing_required_keys(sections),
        **parent_share_flags(report, user),
    }
    if user_is_parent(user):
        payload["can_start_new"] = False
        payload["can_edit"] = False
        payload["can_submit"] = False
        payload["can_preview"] = parent_may_view_report(report)
        payload["reviewer_comment"] = None
        if not payload["can_preview"]:
            payload["has_report"] = False
            payload["report_id"] = None
            payload["status"] = None
            payload["status_label"] = "Not started"
            payload["completion_pct"] = 0
            payload["submitted_at"] = None
            payload["approved_at"] = None
            payload["due_at"] = None
            payload["is_overdue"] = False
    return payload


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
            structured = {
                k: v
                for k, v in structured.items()
                if k
                not in (
                    "internal_notes",
                    "therapist_input",
                    "cm_internal_notes",
                    "parent_input_draft",
                )
            }
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
        "iep_approval": ws.get("iep_approval"),
        "review_thread": ws.get("review_thread") or [],
        "can_edit": False,
        "preview_note": "Family preview — internal notes and pending changes excluded.",
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


def _esc_html(value: object) -> str:
    return html_lib.escape(str(value or "")).replace("\n", "<br/>")


def _iep_section_narrative(sec: dict) -> str:
    text = sec.get("narrative_text") or ""
    if isinstance(text, str) and text.startswith("{"):
        try:
            parsed = json.loads(text)
            text = "\n\n".join(v for v in parsed.values() if isinstance(v, str))
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    return text


def iep_workspace_to_html(payload: dict) -> str:
    parts = [f"<h1>{_esc_html(payload.get('title') or 'IEP Support Plan')}</h1>"]
    child = payload.get("child_name") or ""
    code = payload.get("case_code") or ""
    if child or code:
        parts.append(f"<p>{_esc_html(child)} · {_esc_html(code)}</p>")
    for sec in payload.get("sections") or []:
        label = sec.get("label") or sec.get("key") or "Section"
        parts.append(f"<h2>{_esc_html(label)}</h2>")
        narrative = _iep_section_narrative(sec)
        if narrative.strip():
            parts.append(f"<p>{_esc_html(narrative)}</p>")
        structured = sec.get("structured_data") or {}
        goals = structured.get("goals") if isinstance(structured, dict) else None
        if isinstance(goals, list):
            for i, goal in enumerate(goals, start=1):
                if not isinstance(goal, dict):
                    continue
                heading = goal.get("parent_facing_wording") or goal.get("title") or goal.get("goal_statement") or f"Goal {i}"
                parts.append(f"<h3>{_esc_html(heading)}</h3>")
                statement = goal.get("goal_statement") or ""
                if statement and statement != heading:
                    parts.append(f"<p>{_esc_html(statement)}</p>")
                baseline = goal.get("baseline_current_state") or ""
                desired = goal.get("desired_state") or ""
                if baseline:
                    parts.append(f"<p>Baseline: {_esc_html(baseline)}</p>")
                if desired:
                    parts.append(f"<p>Desired: {_esc_html(desired)}</p>")
        domains = structured.get("domains") if isinstance(structured, dict) else None
        if isinstance(domains, list) and domains:
            labels = ", ".join(str(d) for d in domains if d)
            if labels:
                parts.append(f"<p>Domains: {_esc_html(labels)}</p>")
    return "".join(parts) or "<p>IEP support plan</p>"


def iep_pdf_bytes(db: Session, report: ClinicalReport, case: Case, *, parent_safe: bool) -> tuple[bytes, str]:
    from app.services.report_pdf_service import build_report_pdf_bytes

    payload = (
        serialize_parent_safe_iep(db, report, case)
        if parent_safe
        else serialize_report_workspace(db, report, case)
    )
    child_name = payload.get("child_name") or (case.child.full_name if case.child else "")
    case_code = payload.get("case_code") or case.case_code or ""
    pdf = build_report_pdf_bytes(
        title=payload.get("title") or "IEP Support Plan",
        child_name=child_name,
        case_code=case_code,
        category="IEP",
        month_label=(payload.get("status") or "").replace("_", " "),
        body_html=iep_workspace_to_html(payload),
        plan_next_month=None,
    )
    filename = f"IEP_{case_code or report.id}.pdf"
    return pdf, filename


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
