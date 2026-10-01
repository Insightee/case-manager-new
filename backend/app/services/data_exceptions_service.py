"""Live Layer-1 data exception checks. No stored history and no auto-repair."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.billing_month import today_ist, try_parse_billing_month
from app.core.permissions import user_has_permission
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case, CaseStatus
from app.models.client_billing import ClientInvoice
from app.models.daily_log import DailyLog
from app.models.invoice import Invoice
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.user import EmploymentStatus, User
from app.services.admin_scope_service import apply_case_scope


def can_view_data_exceptions(user: User) -> bool:
    return user_has_permission(user, "case.read.all") or user_has_permission(user, "admin.override")


def _row(
    *,
    rule: str,
    severity: str,
    confirmation: str,
    record_type: str,
    record_id: int,
    label: str,
    dates: str,
    owner: str,
    href: str,
) -> dict:
    return {
        "rule": rule,
        "severity": severity,
        "confirmation": confirmation,
        "recordType": record_type,
        "recordId": record_id,
        "label": label,
        "dates": dates,
        "owner": owner,
        "href": href,
    }


def exception_rows(db: Session, user: User) -> list[dict]:
    today = today_ist()
    log_cutoff = today - timedelta(days=2)
    rows: list[dict] = []

    active_assign_exists = (
        select(CaseAssignment.id)
        .where(
            CaseAssignment.case_id == Case.id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
        .exists()
    )
    no_assign_stmt = apply_case_scope(
        select(Case).where(Case.status == CaseStatus.ACTIVE, ~active_assign_exists),
        user,
    )
    for case in db.scalars(no_assign_stmt).all():
        rows.append(
            _row(
                rule="active_case_no_active_assignment",
                severity="high",
                confirmation="confirmed",
                record_type="case",
                record_id=case.id,
                label=case.case_code,
                dates="",
                owner="Case manager / allotment",
                href=f"/admin/cases/{case.id}",
            )
        )

    inactive_stmt = (
        select(CaseAssignment, User, Case)
        .join(User, User.id == CaseAssignment.therapist_user_id)
        .join(Case, Case.id == CaseAssignment.case_id)
        .where(
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            or_(User.is_active.is_(False), User.employment_status != EmploymentStatus.ACTIVE),
        )
    )
    inactive_stmt = apply_case_scope(inactive_stmt, user)
    for assignment, therapist, case in db.execute(inactive_stmt).all():
        rows.append(
            _row(
                rule="inactive_user_with_active_assignment",
                severity="high",
                confirmation="confirmed",
                record_type="assignment",
                record_id=assignment.id,
                label=f"{therapist.full_name} · {case.case_code}",
                dates=assignment.start_date.isoformat() if assignment.start_date else "",
                owner="HR",
                href=f"/admin/cases/{case.id}",
            )
        )

    missing_log_stmt = (
        select(TherapySession, Case)
        .join(Case, TherapySession.case_id == Case.id)
        .outerjoin(DailyLog, DailyLog.session_id == TherapySession.id)
        .where(
            TherapySession.status == SessionStatus.COMPLETED,
            TherapySession.scheduled_date <= log_cutoff,
            DailyLog.id.is_(None),
        )
        .order_by(TherapySession.scheduled_date.desc())
        .limit(500)
    )
    missing_log_stmt = apply_case_scope(missing_log_stmt, user)
    for session, case in db.execute(missing_log_stmt).all():
        rows.append(
            _row(
                rule="completed_session_no_log",
                severity="medium",
                confirmation="confirmed",
                record_type="session",
                record_id=session.id,
                label=f"{case.case_code} session {session.id}",
                dates=session.scheduled_date.isoformat(),
                owner="Therapist / CM",
                href=f"/admin/logs?case_id={case.id}",
            )
        )

    invoices = list(db.scalars(select(Invoice).order_by(Invoice.id.desc()).limit(2000)).all())
    for inv in invoices:
        if try_parse_billing_month(inv.month) is None:
            rows.append(
                _row(
                    rule="invoice_month_unparseable",
                    severity="low",
                    confirmation="suspected",
                    record_type="therapist_invoice",
                    record_id=inv.id,
                    label=f"Therapist invoice #{inv.id} month={inv.month!r}",
                    dates=str(inv.month or ""),
                    owner="Finance",
                    href="/admin/therapist-payouts?sub=payouts",
                )
            )

    multi_assign = db.execute(
        select(CaseAssignment.case_id, func.count(CaseAssignment.id))
        .where(CaseAssignment.status == CaseAssignmentStatus.ACTIVE)
        .group_by(CaseAssignment.case_id)
        .having(func.count(CaseAssignment.id) > 1)
    ).all()
    for case_id, n in multi_assign:
        case = db.get(Case, case_id)
        if not case:
            continue
        rows.append(
            _row(
                rule="multiple_active_assignments",
                severity="low",
                confirmation="suspected",
                record_type="case",
                record_id=case_id,
                label=f"{case.case_code} · {n} active assignments",
                dates="",
                owner="Case manager",
                href=f"/admin/cases/{case_id}",
            )
        )

    multi_inv = db.execute(
        select(ClientInvoice.case_id, ClientInvoice.billing_month, func.count(ClientInvoice.id))
        .group_by(ClientInvoice.case_id, ClientInvoice.billing_month)
        .having(func.count(ClientInvoice.id) > 1)
    ).all()
    for case_id, month, n in multi_inv:
        case = db.get(Case, case_id)
        rows.append(
            _row(
                rule="multiple_invoices_case_month",
                severity="low",
                confirmation="suspected",
                record_type="case",
                record_id=case_id or 0,
                label=f"{getattr(case, 'case_code', case_id)} · {month} · {n} invoices",
                dates=str(month or ""),
                owner="Finance",
                href="/admin/invoices",
            )
        )

    return rows


def exception_counts(db: Session, user: User) -> dict[str, int]:
    rows = exception_rows(db, user)
    confirmed = sum(1 for r in rows if r["confirmation"] == "confirmed")
    suspected = sum(1 for r in rows if r["confirmation"] == "suspected")
    return {"confirmed": confirmed, "suspected": suspected, "total": len(rows)}


def list_data_exceptions(
    db: Session,
    user: User,
    *,
    page: int = 1,
    page_size: int = 50,
    confirmation: str | None = None,
) -> dict:
    rows = exception_rows(db, user)
    if confirmation in {"confirmed", "suspected"}:
        rows = [r for r in rows if r["confirmation"] == confirmation]
    total = len(rows)
    start = (max(page, 1) - 1) * page_size
    page_rows = rows[start : start + page_size]
    return {
        "rows": page_rows,
        "count": total,
        "page": page,
        "pageSize": page_size,
        "previewLimited": len(page_rows) < total,
        "asOf": today_ist().isoformat(),
        "note": "Live checks at generation time. Multiple active assignments or case-month invoices are not automatic errors.",
    }
