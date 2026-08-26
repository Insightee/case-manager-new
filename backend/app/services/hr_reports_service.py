"""HR portal exports: operational reports, clinical summaries, and people status."""
from __future__ import annotations

import csv
import io
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.permissions import case_scope_check
from app.core.reports_catalog import REPORT_KEYS
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.report import MonthlyReport, ObservationReport, ReportStatus
from app.models.therapist_profile import TherapistProfile
from app.models.user import User
from app.services import case_service, log_service, operational_reports_service
from app.services.reports_export_helpers import (
    active_assignment,
    assignment_therapist,
    case_people_export_fields,
    export_therapist_id,
    parent_by_child,
)

LEGACY_REPORT_KEYS = frozenset(
    {
        "observation",
        "client-monthly",
        "cm-meeting",
        "progress",
        "session-logs",
        "cases-roster",
        "staff-status",
        "therapist-status",
    }
)

OPERATIONAL_REPORT_KEYS = REPORT_KEYS - LEGACY_REPORT_KEYS

STAFF_ROLE_NAMES = frozenset(
    {
        "SUPER_ADMIN",
        "MODULE_ADMIN",
        "ADMIN",
        "CASE_MANAGER",
        "SUPERVISOR",
        "FINANCE",
        "HR",
        "VIEWER",
    }
)


def run_hr_report(
    db: Session,
    report_key: str,
    *,
    category: Optional[str] = None,
    month: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    product_module: Optional[str] = None,
    case_manager_user_id: Optional[int] = None,
    therapist_user_id: Optional[int] = None,
    case_id: Optional[int] = None,
    user: User | None = None,
) -> dict[str, Any]:
    if report_key not in REPORT_KEYS:
        raise ValueError(f"Unknown report: {report_key}")
    if report_key in OPERATIONAL_REPORT_KEYS:
        return operational_reports_service.run_report(
            db,
            report_key,
            user=user,
            month=month,
            date_from=date_from,
            date_to=date_to,
            product_module=product_module,
            case_manager_user_id=case_manager_user_id,
            therapist_user_id=therapist_user_id,
            case_id=case_id,
        )
    rows = report_rows(
        db,
        report_key,
        category=category,
        month=month,
        product_module=product_module,
        user=user,
    )
    return {"rows": rows, "count": len(rows)}


def report_rows(
    db: Session,
    report_key: str,
    *,
    category: Optional[str] = None,
    month: Optional[str] = None,
    product_module: Optional[str] = None,
    user: User | None = None,
) -> list[dict]:
    if report_key not in LEGACY_REPORT_KEYS:
        raise ValueError(f"Unknown legacy report: {report_key}")

    if report_key == "observation":
        return _observation_rows(db, month=month, product_module=product_module, user=user)
    if report_key == "client-monthly":
        return _monthly_rows(db, month=month, product_module=product_module, user=user)
    if report_key == "cm-meeting":
        return _placeholder_category_rows("CM_MEETING", category)
    if report_key == "progress":
        return _placeholder_category_rows("PROGRESS", category)
    if report_key == "session-logs":
        return _session_log_rows(db, month=month, product_module=product_module, user=user)
    if report_key == "cases-roster":
        return _cases_roster_rows(db, product_module=product_module, user=user)
    if report_key == "staff-status":
        return _staff_status_rows(db)
    if report_key == "therapist-status":
        return _therapist_status_rows(db)
    return []


def report_csv(report_key: str, rows: list[dict]) -> str:
    if not rows:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["message"])
        writer.writerow(["No rows"])
        return buf.getvalue()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


def _case_allowed(db: Session, user: User | None, case: Case | None) -> bool:
    if not case or not user:
        return True
    return case_scope_check(db, user, case)


def _observation_rows(
    db: Session,
    *,
    month: Optional[str],
    product_module: Optional[str],
    user: User | None,
) -> list[dict]:
    stmt = select(ObservationReport).order_by(ObservationReport.id.desc())
    rows = db.scalars(stmt).all()
    cases_by_id = {
        r.case_id: case_service.get_case(db, r.case_id)
        for r in rows
        if r.case_id
    }
    parents = parent_by_child(
        db, {c.child_id for c in cases_by_id.values() if c and c.child_id}
    )
    out: list[dict] = []
    for r in rows:
        case = cases_by_id.get(r.case_id) if r.case_id else None
        if product_module and case and case.product_module != product_module:
            continue
        if not _case_allowed(db, user, case):
            continue
        therapist = db.get(User, r.therapist_user_id)
        parent_info = parents.get(case.child_id, {}) if case and case.child_id else {}
        out.append(
            {
                **case_people_export_fields(case, therapist=therapist, parent_info=parent_info),
                "Report Date": r.report_date.isoformat() if r.report_date else "",
                "Status": getattr(r, "status", None) and getattr(r.status, "value", str(r.status)) or "",
                "Category": "OBSERVATION",
            }
        )
    return out


def _monthly_rows(
    db: Session,
    *,
    month: Optional[str],
    product_module: Optional[str],
    user: User | None,
) -> list[dict]:
    stmt = select(MonthlyReport).order_by(MonthlyReport.id.desc())
    if month:
        stmt = stmt.where(MonthlyReport.month == month)
    rows = db.scalars(stmt).all()
    cases_by_id = {
        r.case_id: case_service.get_case(db, r.case_id)
        for r in rows
        if r.case_id
    }
    parents = parent_by_child(
        db, {c.child_id for c in cases_by_id.values() if c and c.child_id}
    )
    out: list[dict] = []
    for r in rows:
        case = cases_by_id.get(r.case_id) if r.case_id else None
        if product_module and case and case.product_module != product_module:
            continue
        if not _case_allowed(db, user, case):
            continue
        therapist = db.get(User, r.therapist_user_id)
        parent_info = parents.get(case.child_id, {}) if case and case.child_id else {}
        out.append(
            {
                **case_people_export_fields(case, therapist=therapist, parent_info=parent_info),
                "Report Month": r.month,
                "Status": r.status.value if isinstance(r.status, ReportStatus) else str(r.status),
                "Category": "CLIENT_MONTHLY",
            }
        )
    return out


def _placeholder_category_rows(label: str, category: Optional[str]) -> list[dict]:
    if category and category.upper() != label:
        return []
    return [{"Category": label, "Message": "No dedicated export table yet; use case documents hub."}]


def _session_log_rows(
    db: Session,
    *,
    month: Optional[str],
    product_module: Optional[str],
    user: User | None,
) -> list[dict]:
    logs = log_service.list_logs(db, month=month, product_module=product_module)
    case_ids = {log.session.case_id for log in logs if log.session}
    cases_by_id = {cid: case_service.get_case(db, cid) for cid in case_ids}
    parents = parent_by_child(
        db, {c.child_id for c in cases_by_id.values() if c and c.child_id}
    )
    out: list[dict] = []
    for log in logs:
        if not log.session:
            continue
        case = cases_by_id.get(log.session.case_id)
        if not _case_allowed(db, user, case):
            continue
        s = log.session
        therapist = db.get(User, s.therapist_user_id) if s else None
        parent_info = parents.get(case.child_id, {}) if case and case.child_id else {}
        out.append(
            {
                **case_people_export_fields(case, therapist=therapist, parent_info=parent_info),
                "Session Date": s.scheduled_date.isoformat() if s and s.scheduled_date else "",
                "Approval Status": (
                    log.approval_status.value
                    if log.approval_status and hasattr(log.approval_status, "value")
                    else (str(log.approval_status) if log.approval_status else "")
                ),
                "Submitted At": log.submitted_at.isoformat() if log.submitted_at else "",
            }
        )
    return out


def _cases_roster_rows(
    db: Session,
    *,
    product_module: Optional[str],
    user: User | None,
) -> list[dict]:
    stmt = select(Case).options(selectinload(Case.child)).order_by(Case.id.desc())
    if product_module:
        stmt = stmt.where(Case.product_module == product_module)
    cases = db.scalars(stmt).all()
    parents = parent_by_child(db, {c.child_id for c in cases if c.child_id})
    out: list[dict] = []
    for case in cases:
        if not _case_allowed(db, user, case):
            continue
        therapist = assignment_therapist(db, active_assignment(db, case.id))
        parent_info = parents.get(case.child_id or -1, {})
        out.append(
            {
                **case_people_export_fields(case, therapist=therapist, parent_info=parent_info),
                "Programme": case.product_module,
                "Status": case.status.value if case.status else "",
                "Service Type": case.service_type or "",
            }
        )
    return out


def _staff_status_rows(db: Session) -> list[dict]:
    users = db.scalars(
        select(User).options(selectinload(User.roles)).order_by(User.email)
    ).all()
    out: list[dict] = []
    for u in users:
        role_names = [r.name for r in (u.roles or [])]
        if not any(r in STAFF_ROLE_NAMES for r in role_names):
            continue
        out.append(
            {
                "Email": u.email,
                "Full Name": u.full_name,
                "Roles": ", ".join(role_names),
                "Employment Status": u.employment_status.value if u.employment_status else "",
                "Active": u.is_active,
            }
        )
    return out


def _therapist_status_rows(db: Session) -> list[dict]:
    profiles = db.scalars(
        select(TherapistProfile).options(selectinload(TherapistProfile.user)).order_by(TherapistProfile.id)
    ).all()
    out: list[dict] = []
    for p in profiles:
        u = p.user
        count = db.scalar(
            select(func.count())
            .select_from(CaseAssignment)
            .where(
                CaseAssignment.therapist_user_id == p.user_id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
        ) or 0
        out.append(
            {
                "Therapist ID": export_therapist_id(u),
                "Therapist Name": p.display_name or (u.full_name if u else ""),
                "Email": u.email if u else "",
                "Profile Status": p.status.value if p.status else "",
                "Employment Status": u.employment_status.value if u and u.employment_status else "",
                "Employment Start Date": p.employment_start_date.isoformat() if p.employment_start_date else "",
                "Active Assignments": int(count),
            }
        )
    return out
