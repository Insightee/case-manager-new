"""HR portal exports: clinical summaries, operations, and people status."""
from __future__ import annotations

import csv
import io
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.permissions import case_scope_check
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.report import MonthlyReport, ObservationReport, ReportStatus
from app.models.therapist_profile import TherapistProfile
from app.models.user import User
from app.services import case_service, log_service

REPORT_KEYS = frozenset(
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


def report_rows(
    db: Session,
    report_key: str,
    *,
    category: Optional[str] = None,
    month: Optional[str] = None,
    product_module: Optional[str] = None,
    user: User | None = None,
) -> list[dict]:
    if report_key not in REPORT_KEYS:
        raise ValueError(f"Unknown report: {report_key}")

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
    out: list[dict] = []
    for r in rows:
        case = case_service.get_case(db, r.case_id) if r.case_id else None
        if product_module and case and case.product_module != product_module:
            continue
        if not _case_allowed(db, user, case):
            continue
        out.append(
            {
                "reportId": r.id,
                "caseId": r.case_id,
                "caseCode": case.case_code if case else "",
                "clientName": case_service.case_child_display_name(case) if case else "",
                "therapistUserId": r.therapist_user_id,
                "reportDate": r.report_date.isoformat() if r.report_date else "",
                "status": getattr(r, "status", None) and getattr(r.status, "value", str(r.status)) or "",
                "category": "OBSERVATION",
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
    out: list[dict] = []
    for r in rows:
        case = case_service.get_case(db, r.case_id) if r.case_id else None
        if product_module and case and case.product_module != product_module:
            continue
        if not _case_allowed(db, user, case):
            continue
        out.append(
            {
                "reportId": r.id,
                "caseId": r.case_id,
                "caseCode": case.case_code if case else "",
                "clientName": case_service.case_child_display_name(case) if case else "",
                "therapistUserId": r.therapist_user_id,
                "reportMonth": r.month,
                "status": r.status.value if isinstance(r.status, ReportStatus) else str(r.status),
                "category": "CLIENT_MONTHLY",
            }
        )
    return out


def _placeholder_category_rows(label: str, category: Optional[str]) -> list[dict]:
    if category and category.upper() != label:
        return []
    return [{"category": label, "message": "No dedicated export table yet; use case documents hub."}]


def _session_log_rows(
    db: Session,
    *,
    month: Optional[str],
    product_module: Optional[str],
    user: User | None,
) -> list[dict]:
    logs = log_service.list_logs(db, month=month, product_module=product_module)
    out: list[dict] = []
    for log in logs:
        if not log.session:
            continue
        case = case_service.get_case(db, log.session.case_id)
        if not _case_allowed(db, user, case):
            continue
        s = log.session
        out.append(
            {
                "logId": log.id,
                "sessionId": log.session_id,
                "caseId": s.case_id if s else "",
                "caseCode": case.case_code if case else "",
                "clientName": case_service.case_child_display_name(case) if case else "",
                "scheduledDate": s.scheduled_date.isoformat() if s and s.scheduled_date else "",
                "approvalStatus": log.approval_status.value if log.approval_status else "",
                "submittedAt": log.submitted_at.isoformat() if log.submitted_at else "",
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
    out: list[dict] = []
    for case in cases:
        if not _case_allowed(db, user, case):
            continue
        child = case.child
        out.append(
            {
                "caseId": case.id,
                "caseCode": case.case_code,
                "clientName": case_service.case_child_display_name(case),
                "productModule": case.product_module,
                "status": case.status.value if case.status else "",
                "serviceType": case.service_type or "",
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
                "userId": u.id,
                "email": u.email,
                "fullName": u.full_name,
                "roles": ", ".join(role_names),
                "employmentStatus": u.employment_status.value if u.employment_status else "",
                "isActive": u.is_active,
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
                "therapistUserId": p.user_id,
                "displayName": p.display_name or (u.full_name if u else ""),
                "email": u.email if u else "",
                "profileStatus": p.status.value if p.status else "",
                "employmentStatus": u.employment_status.value if u and u.employment_status else "",
                "employmentStartDate": p.employment_start_date.isoformat() if p.employment_start_date else "",
                "activeAssignments": int(count),
            }
        )
    return out
