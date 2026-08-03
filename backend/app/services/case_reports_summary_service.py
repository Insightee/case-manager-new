"""Case-level report timeline summary — Layer 1 aggregator for the Reports tab (no AI)."""

from __future__ import annotations

import calendar
import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

def _add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.permissions import get_active_assignment
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.case_document import CaseDocument, CaseDocumentStatus
from app.models.case_manager_meeting import CaseManagerMeeting, MeetingStatus
from app.models.clinical import ObservationChecklist, ObservationChecklistStatus
from app.models.clinical_report import ClinicalReport, ClinicalReportStatus, ClinicalReportType
from app.models.iep_plan import IepPlan, IepPlanStatus
from app.models.report import MonthlyReport, ReportCategory, ReportStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.user import User
from app.services import iep_plan_service as iep_svc
from app.services import report_artifact_read_service as artifact_read
from app.services import report_engine_service as report_engine_svc

HOMECARE_SESSION_THRESHOLD = 5
SHADOW_DUE_DAYS = 30
MONTHLY_DUE_DAY = 28
IEP_DUE_DAYS_AFTER_OBS = 14
PROGRESS_INTERVAL_MONTHS = 6
ATTENTION_CAP = 5

ATTENTION_PRIORITY = {
    "overdue": 0,
    "needs_changes": 1,
    "therapist_approval_pending": 2,
    "due_soon": 3,
    "not_started": 4,
    "pending_cm_approval": 5,
    "upcoming_review": 6,
}

CLINICAL_STATUS_LABELS = {
    ClinicalReportStatus.DRAFT.value: "Draft",
    ClinicalReportStatus.IN_PROGRESS.value: "Draft",
    ClinicalReportStatus.SUBMITTED_FOR_REVIEW.value: "Pending CM approval",
    ClinicalReportStatus.RETURNED_FOR_CHANGES.value: "Needs changes",
    ClinicalReportStatus.APPROVED.value: "Approved",
    ClinicalReportStatus.LOCKED.value: "Approved",
    ClinicalReportStatus.ARCHIVED.value: "Archived",
}

LEGACY_STATUS_LABELS = {
    ReportStatus.DRAFT.value: "Draft",
    ReportStatus.UNDER_REVIEW.value: "Pending CM approval",
    ReportStatus.APPROVED.value: "Approved",
    ReportStatus.REJECTED.value: "Needs changes",
    ReportStatus.PUBLISHED.value: "Approved",
}


def _today() -> date:
    return date.today()


def _iso(d: date | datetime | None) -> str | None:
    if d is None:
        return None
    if isinstance(d, datetime):
        return d.date().isoformat()
    return d.isoformat()


def _month_label_from_date(d: date) -> str:
    return d.strftime("%B %Y")


def _month_key_from_date(d: date) -> str:
    return d.strftime("%Y-%m")


def _is_shadow(case: Case) -> bool:
    module = (case.product_module or "").lower()
    service = (case.service_type or "").lower()
    return module == "shadow_support" or "shadow" in service


def _assignment_for_case(db: Session, case_id: int, user: User) -> CaseAssignment | None:
    row = get_active_assignment(db, case_id, user.id)
    if row:
        return row
    return db.scalar(
        select(CaseAssignment)
        .where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
        .order_by(CaseAssignment.start_date.asc())
        .limit(1)
    )


def _therapist_start(assignment: CaseAssignment | None, case: Case) -> date:
    if assignment:
        return assignment.start_date
    if case.created_at:
        return case.created_at.date()
    return _today()


def compute_observation_due(db: Session, case: Case, assignment: CaseAssignment | None) -> date | None:
    start = _therapist_start(assignment, case)
    if _is_shadow(case):
        return start + timedelta(days=SHADOW_DUE_DAYS)
    therapist_id = assignment.therapist_user_id if assignment else None
    stmt = select(func.count(TherapySession.id)).where(
        TherapySession.case_id == case.id,
        TherapySession.status == SessionStatus.COMPLETED,
    )
    if therapist_id:
        stmt = stmt.where(TherapySession.therapist_user_id == therapist_id)
    completed = int(db.scalar(stmt) or 0)
    if completed >= HOMECARE_SESSION_THRESHOLD:
        return _today()
    return None


def monthly_due_date(year: int, month: int) -> date:
    last_day = calendar.monthrange(year, month)[1]
    day = min(MONTHLY_DUE_DAY, last_day)
    return date(year, month, day)


def _current_month_key() -> str:
    return _today().strftime("%Y-%m")


def _current_month_label() -> str:
    return _month_label_from_date(_today())


def _target_observation(case_id: int, report_id: int | None = None, view: str = "builder") -> str:
    base = f"/therapist/cases/{case_id}?tab=reports&section=observation&view={view}"
    return base


def _target_iep(case_id: int, view: str = "builder") -> str:
    return f"/therapist/cases/{case_id}?tab=reports&section=iep&view={view}"


def _target_monthly_engine(case_id: int, month: str) -> str:
    return f"/therapist/cases/{case_id}?tab=reports&section=monthly&month={month.replace(' ', '%20')}"


def _target_monthly_legacy(case_id: int, report_id: int) -> str:
    return f"/therapist/cases/{case_id}/reports/monthly/{report_id}"


def _target_progress_engine(case_id: int) -> str:
    return f"/therapist/cases/{case_id}?tab=reports&section=progress"


def _target_progress_legacy(report_id: int) -> str:
    return f"/therapist/reports/edit/{report_id}"


def _target_meetings(case_id: int) -> str:
    return f"/therapist/meetings?case_id={case_id}"


def _clinical_editable(status: str) -> bool:
    return status in (
        ClinicalReportStatus.DRAFT.value,
        ClinicalReportStatus.IN_PROGRESS.value,
        ClinicalReportStatus.RETURNED_FOR_CHANGES.value,
    )


def _legacy_editable(status: ReportStatus) -> bool:
    return status in (ReportStatus.DRAFT, ReportStatus.REJECTED)


def _due_soon_flag(due: date | None, *, approved: bool = False) -> str | None:
    if approved or not due:
        return None
    today = _today()
    if due < today:
        return "overdue"
    if (due - today).days <= 7:
        return "due_soon"
    return None


def _parse_iep_review_from_report(report: ClinicalReport) -> date | None:
    from sqlalchemy.orm import object_session

    db = object_session(report)
    if not db:
        return None
    from app.models.clinical_report import ClinicalReportSection

    header = db.scalar(
        select(ClinicalReportSection).where(
            ClinicalReportSection.report_id == report.id,
            ClinicalReportSection.section_key == "patient_profile",
        )
    )
    if not header or not header.structured_data_json:
        return None
    try:
        data = json.loads(header.structured_data_json)
        rd = (data.get("header") or data).get("review_date") or data.get("review_date")
        if not rd:
            return None
        if isinstance(rd, str) and len(rd) >= 10:
            return date.fromisoformat(rd[:10])
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    return None


def _user_display(db: Session, user_id: int | None) -> str | None:
    if not user_id:
        return None
    u = db.get(User, user_id)
    return u.full_name if u else None


def _observation_state(db: Session, case: Case, user: User, assignment: CaseAssignment | None) -> dict[str, Any]:
    report = report_engine_svc.get_active_observation_report(db, case.id)
    due = compute_observation_due(db, case, assignment)
    if report and report.due_date:
        due = report.due_date
    approved = report and report.status in (
        ClinicalReportStatus.APPROVED.value,
        ClinicalReportStatus.LOCKED.value,
    )
    status = report.status if report else "not_due"
    status_label = CLINICAL_STATUS_LABELS.get(report.status, "Not started") if report else "Not due"
    if not report and due:
        flag = _due_soon_flag(due)
        if flag == "overdue":
            status, status_label = "overdue", "Overdue"
        elif flag == "due_soon":
            status, status_label = "due_soon", "Due soon"
        elif due > _today():
            status, status_label = "not_due", "Not due"
    checklist = db.scalar(select(ObservationChecklist).where(ObservationChecklist.case_id == case.id))
    if checklist and checklist.status == ObservationChecklistStatus.APPROVED.value:
        status_label = "Approved"
        status = "approved"
    return {
        "type": "observation_report",
        "title": "Observation Report",
        "report_id": report.id if report else None,
        "status": status,
        "status_label": status_label,
        "due_date": _iso(due),
        "last_updated": _iso(report.updated_at if report else (checklist.updated_at if checklist else None)),
        "next_due_label": "Completed" if approved else (_iso(due) or "Not due"),
        "target_url": _target_observation(case.id, report.id if report else None),
        "cta_label": "View" if approved else ("Continue" if report and _clinical_editable(report.status) else "Start"),
        "priority": _due_soon_flag(due, approved=bool(approved)) or ("not_started" if not report else None),
    }


def _iep_state(db: Session, case: Case) -> dict[str, Any]:
    report = report_engine_svc.get_active_iep_report(db, case.id)
    plan = iep_svc.get_latest_plan(db, case.id)
    obs = report_engine_svc.get_active_observation_report(db, case.id)
    obs_submitted = obs and obs.submitted_at
    review_due = _parse_iep_review_from_report(report) if report else None
    due = None
    if obs_submitted and not report:
        due = obs.submitted_at.date() + timedelta(days=IEP_DUE_DAYS_AFTER_OBS)
    if report:
        status = report.status
        status_label = CLINICAL_STATUS_LABELS.get(status, status)
        if status in (ClinicalReportStatus.APPROVED.value, ClinicalReportStatus.LOCKED.value):
            status_label = "Active"
    elif plan and plan.status in (IepPlanStatus.APPROVED.value, IepPlanStatus.PARENT_ACKNOWLEDGED.value):
        status, status_label = "approved", "Active"
    elif not obs_submitted:
        status, status_label = "waiting", "Waiting for observation report"
    elif due and due < _today():
        status, status_label = "overdue", "Overdue"
    else:
        status, status_label = "not_started", "Not started"
    review_flag = _due_soon_flag(review_due, approved=status in ("approved", ClinicalReportStatus.APPROVED.value))
    return {
        "type": "iep",
        "title": "IEP",
        "report_id": report.id if report else None,
        "status": status,
        "status_label": status_label,
        "due_date": _iso(due),
        "last_updated": _iso(report.updated_at if report else (plan.updated_at if plan else None)),
        "next_due_label": _iso(review_due) if review_due else ("Completed" if status == "approved" else _iso(due)),
        "review_due": _iso(review_due),
        "target_url": _target_iep(case.id),
        "cta_label": "Open" if report or plan else "Start",
        "priority": review_flag or (("overdue" if due and due < _today() else "due_soon") if due and not report else None),
    }


def _monthly_state_for_month(
    db: Session,
    case: Case,
    month_label: str,
    *,
    engine_report: ClinicalReport | None,
    legacy_report: MonthlyReport | None,
    uploaded_doc: CaseDocument | None = None,
) -> dict[str, Any]:
    ym = report_engine_svc._normalize_month_key(month_label)  # noqa: SLF001
    parts = ym.split("-")
    year, month = int(parts[0]), int(parts[1])
    due = monthly_due_date(year, month)
    if engine_report:
        status = engine_report.status
        status_label = CLINICAL_STATUS_LABELS.get(status, status)
        approved = status in (ClinicalReportStatus.APPROVED.value, ClinicalReportStatus.LOCKED.value)
        target = _target_monthly_engine(case.id, month_label)
        rid = engine_report.id
        updated = engine_report.updated_at
    elif uploaded_doc:
        st = uploaded_doc.status
        status = st.lower()
        status_label = artifact_read.DOCUMENT_STATUS_LABELS.get(st, st)
        approved = st in (CaseDocumentStatus.APPROVED.value, CaseDocumentStatus.CLIENT_REVIEW.value)
        target = f"/therapist/cases/{case.id}?tab=documents&document={uploaded_doc.id}"
        rid = uploaded_doc.id
        updated = uploaded_doc.updated_at
    elif legacy_report:
        st = legacy_report.status.value if hasattr(legacy_report.status, "value") else str(legacy_report.status)
        status = st.lower()
        status_label = LEGACY_STATUS_LABELS.get(st, st)
        approved = legacy_report.status in (ReportStatus.APPROVED, ReportStatus.PUBLISHED)
        target = _target_monthly_legacy(case.id, legacy_report.id)
        rid = legacy_report.id
        updated = legacy_report.updated_at
    else:
        flag = _due_soon_flag(due)
        status = flag or "not_started"
        status_label = {"overdue": "Overdue", "due_soon": "Due soon"}.get(status, "Not started")
        return {
            "type": "monthly_report",
            "title": f"Monthly Report — {month_label}",
            "month": month_label,
            "report_id": None,
            "status": status,
            "status_label": status_label,
            "due_date": _iso(due),
            "target_url": _target_monthly_engine(case.id, month_label),
            "cta_label": "Start",
            "priority": flag or "not_started",
        }
    flag = _due_soon_flag(due, approved=approved)
    priority = None
    if status == ClinicalReportStatus.RETURNED_FOR_CHANGES.value or status == "rejected":
        priority = "needs_changes"
    elif status in (ClinicalReportStatus.SUBMITTED_FOR_REVIEW.value, "under_review"):
        priority = "pending_cm_approval"
    elif flag:
        priority = flag
    return {
        "type": "monthly_report",
        "title": f"Monthly Report — {month_label}",
        "month": month_label,
        "report_id": rid,
        "status": status,
        "status_label": status_label,
        "due_date": _iso(due),
        "last_updated": _iso(updated),
        "target_url": target,
        "cta_label": "Continue" if _clinical_editable(status) or (legacy_report and _legacy_editable(legacy_report.status)) else "View",
        "priority": priority,
    }


def _progress_state(db: Session, case: Case, assignment: CaseAssignment | None) -> dict[str, Any]:
    engine_report = report_engine_svc.get_active_progress_report(db, case.id)
    if engine_report:
        status = engine_report.status
        status_label = CLINICAL_STATUS_LABELS.get(status, status)
        approved = status in (ClinicalReportStatus.APPROVED.value, ClinicalReportStatus.LOCKED.value)
        period = report_engine_svc.report_period_from_metadata(engine_report)
        due = None
        if period.get("end"):
            try:
                due = date.fromisoformat(period["end"])
            except ValueError:
                due = None
        flag = _due_soon_flag(due, approved=approved)
        priority = None
        if status == ClinicalReportStatus.RETURNED_FOR_CHANGES.value:
            priority = "needs_changes"
        elif status == ClinicalReportStatus.SUBMITTED_FOR_REVIEW.value:
            priority = "pending_cm_approval"
        elif flag:
            priority = flag
        return {
            "type": "progress_report",
            "title": "Progress Report",
            "report_id": engine_report.id,
            "status": status,
            "status_label": status_label,
            "due_date": _iso(due),
            "last_updated": _iso(engine_report.updated_at),
            "next_due_label": "Completed" if approved else (_iso(due) or "Not due"),
            "target_url": _target_progress_engine(case.id),
            "cta_label": "Continue" if _clinical_editable(status) else "View",
            "priority": priority,
        }

    # Legacy fallback — older progress reports created before the clinical_reports engine.
    progress_rows = db.scalars(
        select(MonthlyReport)
        .where(
            MonthlyReport.case_id == case.id,
            MonthlyReport.category == ReportCategory.PROGRESS.value,
            MonthlyReport.status.in_((ReportStatus.APPROVED, ReportStatus.PUBLISHED)),
        )
        .order_by(MonthlyReport.updated_at.desc())
    ).all()
    start = _therapist_start(assignment, case)
    if progress_rows:
        last = progress_rows[0]
        anchor = last.report_date or (last.updated_at.date() if last.updated_at else start)
        due = _add_months(anchor, PROGRESS_INTERVAL_MONTHS)
    else:
        due = _add_months(start, PROGRESS_INTERVAL_MONTHS)
    draft = db.scalar(
        select(MonthlyReport)
        .where(
            MonthlyReport.case_id == case.id,
            MonthlyReport.category == ReportCategory.PROGRESS.value,
            MonthlyReport.status.in_((ReportStatus.DRAFT, ReportStatus.UNDER_REVIEW, ReportStatus.REJECTED)),
        )
        .order_by(MonthlyReport.id.desc())
        .limit(1)
    )
    flag = _due_soon_flag(due)
    if draft:
        st = draft.status.value if hasattr(draft.status, "value") else str(draft.status)
        return {
            "type": "progress_report",
            "title": "Progress Report",
            "report_id": draft.id,
            "status": st.lower(),
            "status_label": LEGACY_STATUS_LABELS.get(st, st),
            "due_date": _iso(due),
            "last_updated": _iso(draft.updated_at),
            "next_due_label": _iso(due),
            "target_url": _target_progress_legacy(draft.id),
            "cta_label": "Continue" if _legacy_editable(draft.status) else "View",
            "priority": "needs_changes" if draft.status == ReportStatus.REJECTED else flag,
        }
    if due > _today() and not flag:
        status_label = "Not due"
        status = "not_due"
    elif flag == "overdue":
        status, status_label = "overdue", "Overdue"
    elif flag == "due_soon":
        status, status_label = "due_soon", "Due soon"
    else:
        status, status_label = "not_started", "Not started"
    return {
        "type": "progress_report",
        "title": "Progress Report",
        "report_id": None,
        "status": status,
        "status_label": status_label,
        "due_date": _iso(due),
        "next_due_label": _iso(due),
        "target_url": _target_progress_engine(case.id),
        "cta_label": "Start" if status in ("overdue", "due_soon", "not_started") else "View timeline",
        "priority": flag,
    }


def _cm_meeting_state(db: Session, case: Case, assignment: CaseAssignment | None) -> dict[str, Any]:
    meetings = list(
        db.scalars(
            select(CaseManagerMeeting)
            .where(CaseManagerMeeting.case_id == case.id)
            .order_by(CaseManagerMeeting.scheduled_date.desc())
        ).all()
    )
    completed = [
        m
        for m in meetings
        if m.status == MeetingStatus.COMPLETED and (m.notes_summary or m.notes_follow_up or m.notes_concerns)
    ]
    start = _therapist_start(assignment, case)
    first_due = start + timedelta(days=SHADOW_DUE_DAYS)
    next_due = first_due
    if completed:
        latest = completed[0]
        if latest.notes_next_meeting_required:
            next_due = latest.scheduled_date + timedelta(days=30)
        else:
            next_due = None
    if not completed and first_due < _today():
        status, status_label = "overdue", "1st review overdue"
        priority = "overdue"
    elif not completed:
        flag = _due_soon_flag(first_due)
        status = flag or "review_due"
        status_label = "1st review due" if flag else "Due soon"
        priority = flag or "due_soon"
    else:
        flag = _due_soon_flag(next_due) if next_due else None
        status = "completed" if not flag else flag
        status_label = "Completed" if not flag else ("Review due" if flag == "due_soon" else "Overdue")
        priority = flag
    return {
        "type": "cm_meeting_note",
        "title": "CM Meeting Notes",
        "status": status,
        "status_label": status_label,
        "last_updated": _iso(completed[0].completed_at if completed else None),
        "last_note": _iso(completed[0].scheduled_date if completed else None),
        "next_due_label": _iso(next_due or first_due),
        "due_date": _iso(next_due or first_due),
        "target_url": _target_meetings(case.id),
        "cta_label": "Add note" if not completed else "View",
        "priority": priority,
        "notes_count": len(completed),
    }


def _history_item_from_monthly_engine(db: Session, case: Case, report: ClinicalReport) -> dict[str, Any]:
    month_label = report_engine_svc._report_month_from_metadata(report) or _month_label_from_date(  # noqa: SLF001
        report.updated_at.date() if report.updated_at else _today()
    )
    evidence: dict[str, Any] = {}
    try:
        from app.services import monthly_evidence_compiler_service as compiler

        month_key = report_engine_svc._normalize_month_key(month_label)  # noqa: SLF001
        snap = compiler.compile_monthly_evidence_snapshot(db, case.id, month_key, report.id)
        sessions = snap.get("sessions") or {}
        if sessions.get("completed_count") is not None:
            evidence["session_logs_used"] = sessions.get("completed_count")
            evidence["session_logs_expected"] = sessions.get("expected_count")
            if sessions.get("missing_log_count"):
                evidence["missing_logs"] = sessions["missing_log_count"]
    except Exception:
        pass
    editable = _clinical_editable(report.status)
    return {
        "id": str(report.id),
        "type": "monthly_report",
        "title": f"Monthly Report — {month_label}",
        "status": report.status,
        "status_label": CLINICAL_STATUS_LABELS.get(report.status, report.status),
        "period_label": month_label,
        "last_updated": _iso(report.updated_at),
        "created_by": _user_display(db, report.assigned_therapist_id or report.created_by_id),
        "evidence": evidence or None,
        "cta_label": "Continue" if editable else "View",
        "target_url": _target_monthly_engine(case.id, month_label),
        "sort_date": report.updated_at or datetime.now(timezone.utc),
        "month_key": report_engine_svc._normalize_month_key(month_label),  # noqa: SLF001
    }


def _history_item_from_monthly_legacy(db: Session, case: Case, report: MonthlyReport) -> dict[str, Any]:
    st = report.status.value if hasattr(report.status, "value") else str(report.status)
    sort_d = report.updated_at or report.created_at or datetime.now(timezone.utc)
    month_key = sort_d.strftime("%Y-%m")
    return {
        "id": f"legacy-monthly-{report.id}",
        "type": "monthly_report",
        "title": f"Monthly Report — {report.month}",
        "status": st.lower(),
        "status_label": LEGACY_STATUS_LABELS.get(st, st),
        "period_label": report.month,
        "last_updated": _iso(report.updated_at),
        "created_by": _user_display(db, report.therapist_user_id),
        "summary": (report.summary or "")[:200] or None,
        "cta_label": "Continue" if _legacy_editable(report.status) else "View",
        "target_url": _target_monthly_legacy(case.id, report.id),
        "sort_date": sort_d,
        "month_key": month_key,
    }


def _group_history(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for item in sorted(items, key=lambda x: x.get("sort_date") or datetime.min.replace(tzinfo=timezone.utc), reverse=True):
        mk = item.get("month_key") or _month_key_from_date(_today())
        buckets.setdefault(mk, []).append(item)
    out = []
    for mk in sorted(buckets.keys(), reverse=True):
        d = date.fromisoformat(f"{mk}-01")
        out.append({
            "month": mk,
            "label": _month_label_from_date(d),
            "items": [{k: v for k, v in it.items() if k not in ("sort_date", "month_key")} for it in buckets[mk]],
        })
    return out


def build_case_reports_summary(db: Session, case: Case, user: User) -> dict[str, Any]:
    assignment = _assignment_for_case(db, case.id, user)
    child_name = case.child.full_name if case.child else ""
    service = (case.product_module or case.service_type or "").lower()

    obs = _observation_state(db, case, user, assignment)
    iep = _iep_state(db, case)
    current_month = _current_month_label()
    engine_monthly = report_engine_svc.get_monthly_report_for_case_month(db, case.id, current_month)
    legacy_monthly = db.scalar(
        select(MonthlyReport).where(
            MonthlyReport.case_id == case.id,
            MonthlyReport.month == current_month,
            MonthlyReport.category != ReportCategory.PROGRESS.value,
        )
    )
    uploaded_monthly = artifact_read.monthly_document_for_month(db, case.id, current_month)
    monthly_current = _monthly_state_for_month(
        db,
        case,
        current_month,
        engine_report=engine_monthly,
        legacy_report=legacy_monthly,
        uploaded_doc=uploaded_monthly,
    )
    progress = _progress_state(db, case, assignment)
    cm = _cm_meeting_state(db, case, assignment)

    # Stitch order: Observation → IEP → Monthly → Progress → CM Notes
    current_status = [
        {k: v for k, v in obs.items() if k != "priority"},
        {k: v for k, v in iep.items() if k != "priority"},
        {k: v for k, v in monthly_current.items() if k != "priority"},
        {k: v for k, v in progress.items() if k != "priority"},
        {k: v for k, v in cm.items() if k != "priority"},
    ]

    attention_candidates: list[dict[str, Any]] = []
    for src in (monthly_current, obs, iep, progress, cm):
        pr = src.get("priority")
        if not pr:
            continue
        attention_candidates.append({
            "id": f"{src['type']}-{src.get('report_id') or current_month}",
            "type": src["type"],
            "title": src.get("title") or src["type"],
            "status": src.get("status"),
            "status_label": src.get("status_label"),
            "due_date": src.get("due_date"),
            "priority": pr,
            "cta_label": src.get("cta_label", "Open"),
            "target_url": src.get("target_url"),
            "summary": src.get("summary"),
        })

    for leg in db.scalars(
        select(MonthlyReport).where(
            MonthlyReport.case_id == case.id,
            MonthlyReport.status == ReportStatus.REJECTED,
            MonthlyReport.category != ReportCategory.PROGRESS.value,
        )
    ).all():
        if leg.month == current_month:
            continue
        attention_candidates.append({
            "id": f"monthly-{leg.id}",
            "type": "monthly_report",
            "title": f"Monthly Report — {leg.month}",
            "status": "needs_changes",
            "status_label": "Needs changes",
            "due_date": None,
            "priority": "needs_changes",
            "cta_label": "Review feedback",
            "target_url": _target_monthly_legacy(case.id, leg.id),
            "summary": (leg.reviewer_comment or "")[:200] or None,
        })

    attention_candidates.sort(key=lambda x: ATTENTION_PRIORITY.get(x.get("priority"), 99))
    attention_items = attention_candidates[:ATTENTION_CAP]
    has_more_attention = len(attention_candidates) > ATTENTION_CAP

    history_items: list[dict[str, Any]] = []
    obs_report = report_engine_svc.get_active_observation_report(db, case.id)
    if obs_report and obs_report.status in (
        ClinicalReportStatus.APPROVED.value,
        ClinicalReportStatus.LOCKED.value,
        ClinicalReportStatus.SUBMITTED_FOR_REVIEW.value,
    ):
        history_items.append({
            "id": f"obs-{obs_report.id}",
            "type": "observation_report",
            "title": "Observation Report",
            "status": obs_report.status,
            "status_label": CLINICAL_STATUS_LABELS.get(obs_report.status, obs_report.status),
            "last_updated": _iso(obs_report.approved_at or obs_report.updated_at),
            "cta_label": "View report",
            "target_url": _target_observation(case.id, obs_report.id, view="preview"),
            "sort_date": obs_report.approved_at or obs_report.updated_at or datetime.now(timezone.utc),
            "month_key": (obs_report.approved_at or obs_report.updated_at or datetime.now(timezone.utc)).strftime("%Y-%m"),
        })

    iep_report = report_engine_svc.get_active_iep_report(db, case.id)
    if iep_report:
        history_items.append({
            "id": f"iep-{iep_report.id}",
            "type": "iep",
            "title": "IEP",
            "status": iep_report.status,
            "status_label": CLINICAL_STATUS_LABELS.get(iep_report.status, iep_report.status),
            "last_updated": _iso(iep_report.updated_at),
            "cta_label": "View IEP",
            "target_url": _target_iep(case.id, view="preview"),
            "sort_date": iep_report.updated_at or datetime.now(timezone.utc),
            "month_key": (iep_report.updated_at or datetime.now(timezone.utc)).strftime("%Y-%m"),
        })

    engine_monthlies = [
        r
        for r in report_engine_svc.list_case_reports(db, case.id)
        if r.report_type == ClinicalReportType.MONTHLY.value
    ]
    covered_keys: set[tuple[int, str, str]] = set()
    for r in engine_monthlies:
        history_items.append(_history_item_from_monthly_engine(db, case, r))
        mk = report_engine_svc._report_month_from_metadata(r)  # noqa: SLF001
        if mk:
            norm = report_engine_svc._normalize_month_key(mk)  # noqa: SLF001
            covered_keys.add(artifact_read.dedupe_key(case.id, "monthly_report", norm))

    for doc in artifact_read.list_report_documents_for_case(db, case.id):
        rtype = artifact_read.document_report_type(doc.category)
        mk = artifact_read.document_month_key(doc)
        key = artifact_read.dedupe_key(case.id, rtype, mk)
        if rtype == "monthly_report" and key in covered_keys:
            if artifact_read.engine_has_exportable_monthly(db, case.id, mk or ""):
                continue
        if key in covered_keys:
            continue
        history_items.append(artifact_read.history_item_from_case_document(db, case, doc))
        covered_keys.add(key)

    for leg in db.scalars(
        select(MonthlyReport)
        .where(MonthlyReport.case_id == case.id)
        .order_by(MonthlyReport.updated_at.desc())
    ).all():
        if leg.category == ReportCategory.PROGRESS.value:
            st = leg.status.value if hasattr(leg.status, "value") else str(leg.status)
            history_items.append({
                "id": f"progress-{leg.id}",
                "type": "progress_report",
                "title": f"Progress Report — {leg.sub_category or 'Review'}",
                "status": st.lower(),
                "status_label": LEGACY_STATUS_LABELS.get(st, st),
                "last_updated": _iso(leg.updated_at),
                "cta_label": "View" if leg.status in (ReportStatus.APPROVED, ReportStatus.PUBLISHED) else "Continue",
                "target_url": _target_progress(leg.id),
                "sort_date": leg.updated_at or leg.created_at or datetime.now(timezone.utc),
                "month_key": (leg.updated_at or leg.created_at or datetime.now(timezone.utc)).strftime("%Y-%m"),
            })
            continue
        norm = report_engine_svc._normalize_month_key(leg.month) if leg.month else None  # noqa: SLF001
        leg_key = artifact_read.dedupe_key(case.id, "monthly_report", norm)
        if norm and leg_key in covered_keys:
            continue
        history_items.append(_history_item_from_monthly_legacy(db, case, leg))

    for m in db.scalars(
        select(CaseManagerMeeting)
        .where(
            CaseManagerMeeting.case_id == case.id,
            CaseManagerMeeting.status == MeetingStatus.COMPLETED,
        )
        .order_by(CaseManagerMeeting.scheduled_date.desc())
    ).all():
        if not (m.notes_summary or m.notes_follow_up):
            continue
        history_items.append({
            "id": f"meeting-{m.id}",
            "type": "cm_meeting_note",
            "title": m.title or "CM Meeting Note",
            "status": "completed",
            "status_label": "Completed",
            "period_label": m.scheduled_date.isoformat(),
            "last_updated": _iso(m.completed_at or m.scheduled_date),
            "summary": (m.notes_summary or m.notes_follow_up or "")[:200],
            "cta_label": "View note",
            "target_url": _target_meetings(case.id),
            "sort_date": m.completed_at or datetime.combine(m.scheduled_date, datetime.min.time()).replace(tzinfo=timezone.utc),
            "month_key": m.scheduled_date.strftime("%Y-%m"),
        })

    history = _group_history(history_items)
    years = sorted({int(mk[:4]) for mk in {h["month"] for h in history}}, reverse=True)

    working_progress = None
    if monthly_current.get("status") in (
        ClinicalReportStatus.DRAFT.value,
        ClinicalReportStatus.IN_PROGRESS.value,
        "draft",
    ):
        working_progress = {
            "title": monthly_current.get("title"),
            "status_label": monthly_current.get("status_label"),
            "target_url": monthly_current.get("target_url"),
            "completion_pct": 0,
            "evidence": None,
        }
        if engine_monthly:
            from app.models.clinical_report import ClinicalReportSection

            sections = list(
                db.scalars(
                    select(ClinicalReportSection).where(ClinicalReportSection.report_id == engine_monthly.id)
                ).all()
            )
            working_progress["completion_pct"] = report_engine_svc.completion_pct(sections)
            try:
                from app.services import monthly_evidence_compiler_service as compiler

                month_key = report_engine_svc._normalize_month_key(current_month)  # noqa: SLF001
                snap = compiler.compile_monthly_evidence_snapshot(db, case.id, month_key, engine_monthly.id)
                sessions = snap.get("sessions") or {}
                if sessions.get("completed_count") is not None:
                    working_progress["evidence"] = {
                        "session_logs_used": sessions.get("completed_count"),
                        "session_logs_expected": sessions.get("expected_count"),
                    }
            except Exception:
                pass

    return {
        "case_id": case.id,
        "client": {
            "id": case.child_id,
            "name": child_name,
            "service_type": service,
            "case_code": case.case_code,
        },
        "attention_items": attention_items,
        "has_more_attention": has_more_attention,
        "current_status": current_status,
        "working_progress": working_progress,
        "history": history,
        "filters": {
            "available_years": years,
            "available_types": [
                "observation_report",
                "monthly_report",
                "iep",
                "progress_report",
                "cm_meeting_note",
            ],
            "available_statuses": [
                "draft",
                "pending_cm_approval",
                "approved",
                "needs_changes",
                "overdue",
                "due_soon",
                "not_started",
            ],
        },
        "create_actions": [
            {"type": "observation_report", "label": "Observation Report", "target_url": _target_observation(case.id)},
            {"type": "monthly_report", "label": "Monthly Report", "target_url": _target_monthly_engine(case.id, current_month)},
            {"type": "iep", "label": "IEP Review", "target_url": _target_iep(case.id)},
            {"type": "progress_report", "label": "Progress Report", "target_url": f"/therapist/cases/{case.id}?tab=reports&section=progress"},
            {"type": "cm_meeting_note", "label": "CM Meeting Note", "target_url": _target_meetings(case.id)},
        ],
        "is_empty": len(history_items) == 0 and not attention_items,
    }
