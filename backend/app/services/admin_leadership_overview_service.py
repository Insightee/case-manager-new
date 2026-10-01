"""Period-aware leadership modules for super-admin /admin home.

Each module is isolated: a failure returns unavailable, never a fake zero.
Does not run payout preview or full margin reconcile.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session

from app.core.billing_month import (
    default_billing_month,
    ist_date_range_utc_bounds,
    month_date_bounds,
    parse_billing_month,
    therapist_invoice_month_keys,
    today_ist,
)
from app.core.module_access import user_has_feature
from app.core.permissions import user_has_permission
from app.core.timezone import IST
from app.models.app_usage_chunk import AppUsageChunk
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.audit_event import AuditEvent
from app.models.case import Case, CaseStatus
from app.models.case_client_status_audit import CaseClientStatusAudit
from app.models.case_status_request import CaseStatusRequest, CaseStatusRequestStatus
from app.models.client_billing import (
    BillingDispute,
    BillingDisputeStatus,
    ClientInvoice,
    ClientInvoiceStatus,
    ClientPayment,
    ClientPaymentStatus,
)
from app.models.clinical import ObservationChecklist, ObservationChecklistStatus
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.incident import Incident, OPEN_INCIDENT_STATUSES
from app.models.invoice import Invoice, InvoiceStatus
from app.models.leave import LeaveStatus, TherapistLeave
from app.models.report import MonthlyReport, ObservationReport, ReportStatus
from app.models.role import Role
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.slot import SlotStatus, TherapistSlot
from app.models.staff_attendance import StaffAttendance, StaffAttendanceStatus
from app.models.support_ticket import SupportTicket, TicketStatus
from app.models.therapist_profile import TherapistProfile, TherapistProfileStatus
from app.models.user import EmploymentStatus, User
from app.services.admin_scope_service import apply_case_scope
from app.services.support_access_service import can_view_support_tickets


OPEN_CLIENT_INVOICE = (
    ClientInvoiceStatus.GENERATED,
    ClientInvoiceStatus.ISSUED,
    ClientInvoiceStatus.SENT,
    ClientInvoiceStatus.PARTIALLY_PAID,
    ClientInvoiceStatus.OVERDUE,
)

REACTIVATION_FROM = frozenset(
    {
        CaseStatus.SUSPENDED.value,
        CaseStatus.DEACTIVATED.value,
        CaseStatus.CLOSED.value,
    }
)


def _as_date(value: datetime | date | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo:
            return value.astimezone(IST).date()
        return value.date()
    return value


def _age_days(value: datetime | date | None, today: date) -> int | None:
    day = _as_date(value)
    if day is None:
        return None
    return max(0, (today - day).days)


def _module_ok(payload: dict) -> dict:
    return {"ok": True, "error": None, **payload}


def _module_fail(exc: Exception) -> dict:
    return {
        "ok": False,
        "error": "This module could not load. Other figures are still available.",
        "unavailable": True,
        "detail": str(exc)[:240],
    }


def _module_unavailable(reason: str) -> dict:
    return {"ok": True, "error": None, "unavailable": True, "reason": reason}


def resolve_period(period_month: str | None) -> dict:
    ym = parse_billing_month(period_month)
    first, last = month_date_bounds(ym)
    today = today_ist()
    end = min(today, last) if first <= today else last
    start_utc, end_utc = ist_date_range_utc_bounds(first, end)
    return {
        "month": ym,
        "dateFrom": first.isoformat(),
        "dateTo": end.isoformat(),
        "start": first,
        "end": end,
        "startUtc": start_utc,
        "endUtc": end_utc,
        "today": today,
        "timezone": "Asia/Kolkata",
    }


def _scope_case(stmt, user: User, product_module: str | None):
    stmt = apply_case_scope(stmt, user)
    if product_module:
        stmt = stmt.where(Case.product_module == product_module)
    return stmt


def _count(db: Session, stmt) -> int:
    return int(db.scalar(stmt) or 0)


def _cases_module(db: Session, user: User, period: dict, product_module: str | None) -> dict:
    today = period["today"]
    start, end = period["start"], period["end"]
    start_utc, end_utc = period["startUtc"], period["endUtc"]

    status_counts = {}
    for status in CaseStatus:
        stmt = _scope_case(
            select(func.count()).select_from(Case).where(Case.status == status),
            user,
            product_module,
        )
        status_counts[status.value] = _count(db, stmt)

    created_stmt = _scope_case(
        select(func.count()).select_from(Case).where(Case.created_at >= start_utc, Case.created_at < end_utc),
        user,
        product_module,
    )

    first_active = (
        select(
            CaseClientStatusAudit.case_id,
            func.min(CaseClientStatusAudit.effective_date).label("first_active"),
        )
        .where(CaseClientStatusAudit.new_status == CaseStatus.ACTIVE.value)
        .group_by(CaseClientStatusAudit.case_id)
        .subquery()
    )
    first_activation_stmt = _scope_case(
        select(func.count())
        .select_from(first_active)
        .join(Case, Case.id == first_active.c.case_id)
        .where(first_active.c.first_active >= start, first_active.c.first_active <= end),
        user,
        product_module,
    )

    def _audit_count(new_status: str, *, previous_in: frozenset[str] | None = None) -> int:
        stmt = (
            select(func.count())
            .select_from(CaseClientStatusAudit)
            .join(Case, Case.id == CaseClientStatusAudit.case_id)
            .where(
                CaseClientStatusAudit.new_status == new_status,
                CaseClientStatusAudit.effective_date >= start,
                CaseClientStatusAudit.effective_date <= end,
            )
        )
        if previous_in:
            stmt = stmt.where(CaseClientStatusAudit.previous_status.in_(previous_in))
        return _count(db, _scope_case(stmt, user, product_module))

    cases_not_pending = _scope_case(
        select(func.count()).select_from(Case).where(Case.status != CaseStatus.PENDING_ALLOTMENT),
        user,
        product_module,
    )
    with_audit = _scope_case(
        select(func.count(func.distinct(CaseClientStatusAudit.case_id)))
        .select_from(CaseClientStatusAudit)
        .join(Case, Case.id == CaseClientStatusAudit.case_id)
        .where(Case.status != CaseStatus.PENDING_ALLOTMENT),
        user,
        product_module,
    )
    not_pending = _count(db, cases_not_pending)
    audited = _count(db, with_audit)
    coverage = "complete" if not_pending == 0 or audited >= not_pending else "partial"

    return _module_ok(
        {
            "dateBasis": "current",
            "movementDateBasis": "during_period",
            "statusCounts": status_counts,
            "createdDuringPeriod": _count(db, created_stmt),
            "firstActivationDuringPeriod": _count(db, first_activation_stmt),
            "reactivationDuringPeriod": _audit_count(CaseStatus.ACTIVE.value, previous_in=REACTIVATION_FROM),
            "suspensionDuringPeriod": _audit_count(CaseStatus.SUSPENDED.value),
            "closureDuringPeriod": _audit_count(CaseStatus.CLOSED.value),
            "deactivationDuringPeriod": _audit_count(CaseStatus.DEACTIVATED.value),
            "movementCoverage": coverage,
            "href": "/admin/cases",
            "asOf": today.isoformat(),
        }
    )


def _assignments_module(db: Session, user: User, period: dict, product_module: str | None) -> dict:
    start, end = period["start"], period["end"]
    has_any_assignment = exists().where(CaseAssignment.case_id == Case.id)
    has_active = exists().where(
        CaseAssignment.case_id == Case.id,
        CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
    )

    awaiting_first = _count(
        db,
        _scope_case(
            select(func.count())
            .select_from(Case)
            .where(
                or_(
                    Case.status == CaseStatus.PENDING_ALLOTMENT,
                    and_(~has_any_assignment, Case.status != CaseStatus.CLOSED),
                )
            ),
            user,
            product_module,
        ),
    )
    awaiting_replacement = _count(
        db,
        _scope_case(
            select(func.count()).select_from(Case).where(Case.status == CaseStatus.PENDING_REPLACEMENT),
            user,
            product_module,
        ),
    )
    active_without = _count(
        db,
        _scope_case(
            select(func.count())
            .select_from(Case)
            .where(Case.status == CaseStatus.ACTIVE, ~has_active),
            user,
            product_module,
        ),
    )

    ended_filter = or_(
        and_(CaseAssignment.end_date.is_not(None), CaseAssignment.end_date >= start, CaseAssignment.end_date <= end),
        and_(
            CaseAssignment.end_date.is_(None),
            CaseAssignment.created_at >= period["startUtc"],
            CaseAssignment.created_at < period["endUtc"],
        ),
    )
    ended_base = (
        select(CaseAssignment)
        .join(Case, CaseAssignment.case_id == Case.id)
        .where(
            CaseAssignment.status.in_([CaseAssignmentStatus.ENDED, CaseAssignmentStatus.TRANSFERRED]),
            ended_filter,
        )
    )
    ended_base = _scope_case(ended_base, user, product_module)
    ended_rows = list(db.scalars(ended_base).all())
    unique_cases = {row.case_id for row in ended_rows}

    return _module_ok(
        {
            "dateBasis": "current",
            "awaitingFirstAssignment": awaiting_first,
            "awaitingReplacement": awaiting_replacement,
            "activeWithoutActiveAssignment": active_without,
            "assignmentEndedEvents": len(ended_rows),
            "uniqueCasesWithEndedAssignment": len(unique_cases),
            "endedNote": "Ended or transferred assignments in the period. Not every ENDED row is a replacement.",
            "hrefFirst": "/admin/cases?queue=allotment",
            "hrefReplacement": "/admin/cases?status=PENDING_REPLACEMENT",
        }
    )


def _sessions_module(db: Session, user: User, period: dict, product_module: str | None) -> dict:
    start, end = period["start"], period["end"]

    def status_count(status: SessionStatus) -> int:
        stmt = (
            select(func.count())
            .select_from(TherapySession)
            .join(Case, TherapySession.case_id == Case.id)
            .where(
                TherapySession.status == status,
                TherapySession.scheduled_date >= start,
                TherapySession.scheduled_date <= end,
            )
        )
        return _count(db, _scope_case(stmt, user, product_module))

    completed = status_count(SessionStatus.COMPLETED)
    auto_closed_stmt = (
        select(func.count())
        .select_from(TherapySession)
        .join(Case, TherapySession.case_id == Case.id)
        .where(
            TherapySession.auto_ended.is_(True),
            TherapySession.scheduled_date >= start,
            TherapySession.scheduled_date <= end,
        )
    )
    return _module_ok(
        {
            "dateBasis": "during_period",
            "completed": completed,
            "clientAbsent": status_count(SessionStatus.CLIENT_ABSENT),
            "therapistLeave": status_count(SessionStatus.THERAPIST_LEAVE),
            "cancelled": status_count(SessionStatus.CANCELLED),
            "noShow": status_count(SessionStatus.NO_SHOW),
            "autoClosed": _count(db, _scope_case(auto_closed_stmt, user, product_module)),
            "autoClosedNote": "Auto-closed sessions are not proof of attended delivery.",
            "href": "/admin/logs",
        }
    )


def _finance_module(db: Session, user: User, period: dict, product_module: str | None) -> dict:
    if not user_has_permission(user, "invoice.approve"):
        return _module_unavailable("Finance cards need invoice.approve.")
    if not (user_has_feature(user, "invoices") or user_has_feature(user, "dashboard")):
        return _module_unavailable("Billing module is not on this account.")

    ym = period["month"]
    today = period["today"]
    start_utc, end_utc = period["startUtc"], period["endUtc"]
    month_keys = therapist_invoice_month_keys(ym)

    invoiced_stmt = (
        select(func.coalesce(func.sum(ClientInvoice.total_inr), 0))
        .select_from(ClientInvoice)
        .join(Case, ClientInvoice.case_id == Case.id)
        .where(
            ClientInvoice.billing_month == ym,
            ClientInvoice.status.notin_([ClientInvoiceStatus.VOID, ClientInvoiceStatus.CANCELLED]),
        )
    )
    invoiced_stmt = _scope_case(invoiced_stmt, user, product_module)

    cash_stmt = (
        select(func.coalesce(func.sum(ClientPayment.amount_inr), 0))
        .select_from(ClientPayment)
        .join(ClientInvoice, ClientPayment.client_invoice_id == ClientInvoice.id)
        .join(Case, ClientInvoice.case_id == Case.id)
        .where(
            ClientPayment.payment_status == ClientPaymentStatus.CONFIRMED,
            ClientPayment.paid_at >= start_utc,
            ClientPayment.paid_at < end_utc,
        )
    )
    cash_stmt = _scope_case(cash_stmt, user, product_module)

    pending_claims_stmt = (
        select(func.count())
        .select_from(ClientPayment)
        .join(ClientInvoice, ClientPayment.client_invoice_id == ClientInvoice.id)
        .join(Case, ClientInvoice.case_id == Case.id)
        .where(ClientPayment.payment_status == ClientPaymentStatus.PENDING_REVIEW)
    )
    pending_claims_stmt = _scope_case(pending_claims_stmt, user, product_module)

    outstanding_stmt = (
        select(
            func.coalesce(func.sum(ClientInvoice.total_inr - ClientInvoice.amount_paid_inr), 0),
            func.count(),
        )
        .select_from(ClientInvoice)
        .join(Case, ClientInvoice.case_id == Case.id)
        .where(ClientInvoice.status.in_(OPEN_CLIENT_INVOICE))
    )
    outstanding_stmt = _scope_case(outstanding_stmt, user, product_module)
    outstanding_amount, outstanding_count = db.execute(outstanding_stmt).one()

    overdue_stmt = (
        select(
            func.coalesce(func.sum(ClientInvoice.total_inr - ClientInvoice.amount_paid_inr), 0),
            func.count(),
        )
        .select_from(ClientInvoice)
        .join(Case, ClientInvoice.case_id == Case.id)
        .where(
            ClientInvoice.status.in_(OPEN_CLIENT_INVOICE),
            ClientInvoice.due_date.is_not(None),
            ClientInvoice.due_date < today,
        )
    )
    overdue_stmt = _scope_case(overdue_stmt, user, product_module)
    overdue_amount, overdue_count = db.execute(overdue_stmt).one()

    in_review = _count(db, select(func.count()).select_from(Invoice).where(Invoice.status == InvoiceStatus.IN_REVIEW))
    approved = _count(
        db,
        select(func.count())
        .select_from(Invoice)
        .where(Invoice.status.in_([InvoiceStatus.APPROVED, InvoiceStatus.EXPORTING])),
    )
    approved_month = _count(
        db,
        select(func.count())
        .select_from(Invoice)
        .where(
            Invoice.status.in_([InvoiceStatus.APPROVED, InvoiceStatus.EXPORTING]),
            Invoice.month.in_(month_keys),
        ),
    )

    return _module_ok(
        {
            "invoicedAmountInr": float(invoiced_stmt and db.scalar(invoiced_stmt) or 0),
            "invoicedDateBasis": "billing_month",
            "confirmedCashInr": float(db.scalar(cash_stmt) or 0),
            "cashDateBasis": "during_period",
            "pendingClaims": _count(db, pending_claims_stmt),
            "outstandingAmountInr": float(outstanding_amount or 0),
            "outstandingCount": int(outstanding_count or 0),
            "outstandingDateBasis": "current",
            "overdueAmountInr": float(overdue_amount or 0),
            "overdueCount": int(overdue_count or 0),
            "overdueDateBasis": "current",
            "overdueNote": "Overdue only when due_date is set and before today IST.",
            "therapistStatementsInReview": in_review,
            "approvedAwaitingPayment": approved,
            "approvedAwaitingPaymentThisMonth": approved_month,
            "hrefInvoices": "/admin/invoices",
            "hrefPayouts": "/admin/therapist-payouts?sub=payouts",
            "hrefPayoutPreview": "/admin/finance-reports",
        }
    )


def _tickets_module(db: Session, user: User, period: dict, product_module: str | None) -> dict:
    if not user_has_feature(user, "tickets") and not can_view_support_tickets(user, db):
        return _module_unavailable("Ticket cards need support-ticket access.")

    start_utc, end_utc = period["startUtc"], period["endUtc"]
    filters = []
    if product_module:
        filters.append(SupportTicket.product_module == product_module)

    open_count = _count(
        db,
        select(func.count()).select_from(SupportTicket).where(SupportTicket.status == TicketStatus.OPEN, *filters),
    )
    in_progress = _count(
        db,
        select(func.count())
        .select_from(SupportTicket)
        .where(SupportTicket.status == TicketStatus.IN_PROGRESS, *filters),
    )
    opened = _count(
        db,
        select(func.count())
        .select_from(SupportTicket)
        .where(SupportTicket.created_at >= start_utc, SupportTicket.created_at < end_utc, *filters),
    )
    qs = f"tab=ticket-report&date_from={period['dateFrom']}&date_to={period['dateTo']}"
    if product_module:
        qs += f"&product_module={product_module}"
    return _module_ok(
        {
            "open": open_count,
            "inProgress": in_progress,
            "needsAction": open_count + in_progress,
            "openedDuringPeriod": opened,
            "dateBasisCurrent": "current",
            "dateBasisOpened": "during_period",
            "href": f"/admin/support?{qs}",
            "hrefOpen": f"/admin/support?{qs}&status=OPEN",
            "hrefInProgress": f"/admin/support?{qs}&status=IN_PROGRESS",
        }
    )


def _staff_attendance_module(db: Session, user: User, period: dict) -> dict:
    can_see = user_has_permission(user, "admin.override") or user_has_permission(user, "user.manage")
    if not can_see:
        return _module_unavailable("Staff workplace attendance is an organisation view.")

    today = period["today"]
    start, end = period["start"], period["end"]
    coverage = _count(db, select(func.count(func.distinct(StaffAttendance.user_id))))
    today_clocked = _count(
        db,
        select(func.count(func.distinct(StaffAttendance.user_id))).where(StaffAttendance.work_date == today),
    )
    period_records = _count(
        db,
        select(func.count()).select_from(StaffAttendance).where(
            StaffAttendance.work_date >= start,
            StaffAttendance.work_date <= end,
        ),
    )
    period_staff = _count(
        db,
        select(func.count(func.distinct(StaffAttendance.user_id))).where(
            StaffAttendance.work_date >= start,
            StaffAttendance.work_date <= end,
        ),
    )
    auto_closed = _count(
        db,
        select(func.count()).select_from(StaffAttendance).where(
            StaffAttendance.work_date >= start,
            StaffAttendance.work_date <= end,
            or_(StaffAttendance.status == StaffAttendanceStatus.AUTO_CLOSED, StaffAttendance.auto_closed.is_(True)),
        ),
    )
    today_gaps = max(0, coverage - today_clocked) if coverage else 0
    return _module_ok(
        {
            "dateBasis": "current" if start <= today <= end else "during_period",
            "source": "in_app_staff_attendance",
            "sourceLabel": "In-app clock-in (check-in, check-out, auto-closed)",
            "coverageStaff": coverage,
            "clockedInToday": today_clocked,
            "todayGaps": today_gaps,
            "recordsDuringPeriod": period_records,
            "uniqueStaffDuringPeriod": period_staff,
            "autoClosedDuringPeriod": auto_closed,
            "coverageNote": "Only staff who use the app clock-in appear here. No clock-in is an attendance gap in this source, not a missing integration.",
            "href": "/admin/attendance",
        }
    )


def _queue_item(
    *,
    key: str,
    label: str,
    count: int,
    href: str,
    owner: str,
    date_basis: str,
    oldest_age_days: int | None = None,
    age_field: str | None = None,
    overdue: int | None = None,
    overdue_available: bool = False,
) -> dict:
    return {
        "key": key,
        "label": label,
        "count": count,
        "href": href,
        "owner": owner,
        "dateBasis": date_basis,
        "oldestAgeDays": oldest_age_days,
        "ageField": age_field,
        "overdue": overdue if overdue_available else None,
        "overdueAvailable": overdue_available,
    }


def _queues_module(db: Session, user: User, period: dict, product_module: str | None) -> dict:
    today = period["today"]
    items: list[dict] = []

    def add(item: dict | None) -> None:
        if item:
            items.append(item)

    if user_has_permission(user, "daily_log.review") and user_has_feature(user, "session_logs"):
        stmt = (
            select(func.count(), func.min(DailyLog.submitted_at))
            .select_from(DailyLog)
            .join(TherapySession, DailyLog.session_id == TherapySession.id)
            .join(Case, TherapySession.case_id == Case.id)
            .where(DailyLog.approval_status == LogApprovalStatus.PENDING)
        )
        stmt = _scope_case(stmt, user, product_module)
        count, oldest = db.execute(stmt).one()
        add(
            _queue_item(
                key="session_logs",
                label="Session logs pending review",
                count=int(count or 0),
                href="/admin/workbench?section=logs",
                owner="Case manager",
                date_basis="current",
                oldest_age_days=_age_days(oldest, today),
                age_field="submitted_at",
            )
        )

    if user_has_permission(user, "monthly_report.approve") and user_has_feature(user, "reports"):
        monthly_stmt = (
            select(func.count(), func.min(MonthlyReport.updated_at))
            .select_from(MonthlyReport)
            .join(Case, MonthlyReport.case_id == Case.id)
            .where(MonthlyReport.status == ReportStatus.UNDER_REVIEW)
        )
        monthly_stmt = _scope_case(monthly_stmt, user, product_module)
        m_count, m_oldest = db.execute(monthly_stmt).one()
        add(
            _queue_item(
                key="monthly_reports",
                label="Monthly reports in review",
                count=int(m_count or 0),
                href="/admin/reports?tab=queue",
                owner="Case manager",
                date_basis="current",
                oldest_age_days=_age_days(m_oldest, today),
                age_field="updated_at",
            )
        )
        obs_stmt = (
            select(func.count(), func.min(ObservationReport.updated_at))
            .select_from(ObservationReport)
            .join(Case, ObservationReport.case_id == Case.id)
            .where(ObservationReport.status == ReportStatus.UNDER_REVIEW)
        )
        obs_stmt = _scope_case(obs_stmt, user, product_module)
        o_count, o_oldest = db.execute(obs_stmt).one()
        add(
            _queue_item(
                key="observation_reports",
                label="Observation reports in review",
                count=int(o_count or 0),
                href="/admin/reports?tab=queue",
                owner="Case manager",
                date_basis="current",
                oldest_age_days=_age_days(o_oldest, today),
                age_field="updated_at",
            )
        )
        chk_stmt = (
            select(func.count(), func.min(ObservationChecklist.submitted_at))
            .select_from(ObservationChecklist)
            .join(Case, ObservationChecklist.case_id == Case.id)
            .where(ObservationChecklist.status == ObservationChecklistStatus.SUBMITTED.value)
        )
        chk_stmt = _scope_case(chk_stmt, user, product_module)
        c_count, c_oldest = db.execute(chk_stmt).one()
        overdue_stmt = (
            select(func.count())
            .select_from(ObservationChecklist)
            .join(Case, ObservationChecklist.case_id == Case.id)
            .where(
                ObservationChecklist.due_at.is_not(None),
                ObservationChecklist.due_at < today,
                ObservationChecklist.status.in_(
                    [ObservationChecklistStatus.DRAFT.value, ObservationChecklistStatus.REJECTED.value]
                ),
            )
        )
        overdue_stmt = _scope_case(overdue_stmt, user, product_module)
        add(
            _queue_item(
                key="observation_checklists",
                label="Observation checklists pending",
                count=int(c_count or 0),
                href="/admin/workbench?section=observations",
                owner="Case manager",
                date_basis="current",
                oldest_age_days=_age_days(c_oldest, today),
                age_field="submitted_at",
                overdue=_count(db, overdue_stmt),
                overdue_available=True,
            )
        )

    if user_has_permission(user, "case.update"):
        sr_stmt = (
            select(func.count(), func.min(CaseStatusRequest.created_at))
            .select_from(CaseStatusRequest)
            .join(Case, CaseStatusRequest.case_id == Case.id)
            .where(CaseStatusRequest.status == CaseStatusRequestStatus.PENDING)
        )
        sr_stmt = _scope_case(sr_stmt, user, product_module)
        sr_count, sr_oldest = db.execute(sr_stmt).one()
        add(
            _queue_item(
                key="status_requests",
                label="Case status requests",
                count=int(sr_count or 0),
                href="/admin/workbench?section=status_requests",
                owner="Case manager",
                date_basis="current",
                oldest_age_days=_age_days(sr_oldest, today),
                age_field="created_at",
            )
        )

    if user_has_permission(user, "invoice.approve"):
        pay_stmt = (
            select(func.count(), func.min(ClientPayment.paid_at))
            .select_from(ClientPayment)
            .join(ClientInvoice, ClientPayment.client_invoice_id == ClientInvoice.id)
            .join(Case, ClientInvoice.case_id == Case.id)
            .where(ClientPayment.payment_status == ClientPaymentStatus.PENDING_REVIEW)
        )
        pay_stmt = _scope_case(pay_stmt, user, product_module)
        p_count, p_oldest = db.execute(pay_stmt).one()
        add(
            _queue_item(
                key="client_claims",
                label="Client payment claims",
                count=int(p_count or 0),
                href="/admin/invoices?tab=payments",
                owner="Finance",
                date_basis="current",
                oldest_age_days=_age_days(p_oldest, today),
                age_field="paid_at",
            )
        )
        inv_stmt = select(func.count(), func.min(Invoice.updated_at)).where(Invoice.status == InvoiceStatus.IN_REVIEW)
        i_count, i_oldest = db.execute(inv_stmt).one()
        add(
            _queue_item(
                key="therapist_invoices",
                label="Therapist statements in review",
                count=int(i_count or 0),
                href="/admin/therapist-payouts?sub=payouts",
                owner="Finance",
                date_basis="current",
                oldest_age_days=_age_days(i_oldest, today),
                age_field="updated_at",
            )
        )
        dispute_stmt = (
            select(func.count(), func.min(BillingDispute.created_at))
            .select_from(BillingDispute)
            .join(ClientInvoice, BillingDispute.client_invoice_id == ClientInvoice.id)
            .join(Case, ClientInvoice.case_id == Case.id)
            .where(BillingDispute.status.in_([BillingDisputeStatus.OPEN, BillingDisputeStatus.UNDER_REVIEW]))
        )
        dispute_stmt = _scope_case(dispute_stmt, user, product_module)
        d_count, d_oldest = db.execute(dispute_stmt).one()
        add(
            _queue_item(
                key="billing_disputes",
                label="Billing holds / disputes",
                count=int(d_count or 0),
                href="/admin/invoices",
                owner="Finance",
                date_basis="current",
                oldest_age_days=_age_days(d_oldest, today),
                age_field="created_at",
            )
        )

    if user_has_permission(user, "leave.manage"):
        leave_stmt = select(func.count(), func.min(TherapistLeave.created_at)).where(
            TherapistLeave.status == LeaveStatus.PENDING
        )
        l_count, l_oldest = db.execute(leave_stmt).one()
        add(
            _queue_item(
                key="therapist_leave",
                label="Therapist leave pending",
                count=int(l_count or 0),
                href="/admin/leave",
                owner="HR",
                date_basis="current",
                oldest_age_days=_age_days(l_oldest, today),
                age_field="created_at",
            )
        )

    if can_view_support_tickets(user, db) or user_has_feature(user, "tickets"):
        t_open = select(func.count(), func.min(SupportTicket.created_at)).where(
            SupportTicket.status == TicketStatus.OPEN
        )
        t_prog = select(func.count(), func.min(SupportTicket.created_at)).where(
            SupportTicket.status == TicketStatus.IN_PROGRESS
        )
        o_count, o_oldest = db.execute(t_open).one()
        p_count, p_oldest = db.execute(t_prog).one()
        qs = f"tab=ticket-report&date_from={period['dateFrom']}&date_to={period['dateTo']}"
        add(
            _queue_item(
                key="tickets_open",
                label="Open tickets",
                count=int(o_count or 0),
                href=f"/admin/support?{qs}&status=OPEN",
                owner="Support",
                date_basis="current",
                oldest_age_days=_age_days(o_oldest, today),
                age_field="created_at",
            )
        )
        add(
            _queue_item(
                key="tickets_in_progress",
                label="In-progress tickets",
                count=int(p_count or 0),
                href=f"/admin/support?{qs}&status=IN_PROGRESS",
                owner="Support",
                date_basis="current",
                oldest_age_days=_age_days(p_oldest, today),
                age_field="created_at",
            )
        )

    if user_has_permission(user, "incident.read_sensitive") and user_has_feature(user, "incidents"):
        inc_stmt = select(func.count(), func.min(Incident.created_at)).where(
            Incident.status.in_(list(OPEN_INCIDENT_STATUSES))
        )
        n_count, n_oldest = db.execute(inc_stmt).one()
        add(
            _queue_item(
                key="incidents",
                label="Open incidents",
                count=int(n_count or 0),
                href="/admin/support?tab=incidents",
                owner="Support",
                date_basis="current",
                oldest_age_days=_age_days(n_oldest, today),
                age_field="created_at",
            )
        )

    if user_has_permission(user, "case.read.all") or user_has_permission(user, "case.create"):
        slot_stmt = (
            select(func.count(), func.min(TherapistSlot.slot_date))
            .select_from(TherapistSlot)
            .join(Case, TherapistSlot.case_id == Case.id)
            .where(
                TherapistSlot.approval_status == "PENDING_THERAPIST",
                TherapistSlot.status == SlotStatus.BOOKED,
            )
        )
        slot_stmt = _scope_case(slot_stmt, user, product_module)
        s_count, s_oldest = db.execute(slot_stmt).one()
        add(
            _queue_item(
                key="slot_confirmation",
                label="Slot confirmation pending",
                count=int(s_count or 0),
                href="/admin/workbench?section=reschedules",
                owner="Therapist / CM",
                date_basis="current",
                oldest_age_days=_age_days(s_oldest, today),
                age_field="slot_date",
            )
        )

    return _module_ok(
        {
            "dateBasis": "current",
            "items": items,
            "note": "Queue counts are separate. Do not add them together — items can sit in more than one list.",
        }
    )


def _therapist_attention_summary(db: Session, user: User) -> dict:
    if not (
        user_has_permission(user, "user.manage")
        or user_has_permission(user, "admin.override")
        or user_has_permission(user, "case.read.all")
    ):
        return _module_unavailable("Therapist attention needs people or case-read-all access.")

    therapist_ids = list(
        db.scalars(select(User.id).join(User.roles).where(Role.name == "THERAPIST")).all()
    )
    if not therapist_ids:
        return _module_ok(
            {
                "dateBasis": "current",
                "therapistCount": 0,
                "noRecordedLogin": 0,
                "pendingProfiles": 0,
                "inactiveWithActiveAssignment": 0,
                "href": "/admin/therapist-attention",
            }
        )

    logged_in = set(
        db.scalars(
            select(AuditEvent.actor_user_id)
            .where(
                AuditEvent.action == "login",
                AuditEvent.actor_user_id.in_(therapist_ids),
            )
            .distinct()
        ).all()
    )
    pending_profiles = _count(
        db,
        select(func.count())
        .select_from(TherapistProfile)
        .where(
            TherapistProfile.status.in_(
                [TherapistProfileStatus.PENDING, TherapistProfileStatus.CHANGES_REQUESTED]
            )
        ),
    )
    inactive_assigned = _count(
        db,
        select(func.count(func.distinct(CaseAssignment.therapist_user_id)))
        .select_from(CaseAssignment)
        .join(User, User.id == CaseAssignment.therapist_user_id)
        .where(
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            or_(User.is_active.is_(False), User.employment_status != EmploymentStatus.ACTIVE),
        ),
    )
    return _module_ok(
        {
            "dateBasis": "current",
            "therapistCount": len(therapist_ids),
            "noRecordedLogin": sum(1 for tid in therapist_ids if tid not in logged_in),
            "pendingProfiles": pending_profiles,
            "inactiveWithActiveAssignment": inactive_assigned,
            "loginNote": "No recorded login is not the same as never used.",
            "href": "/admin/therapist-attention",
        }
    )


def _data_exceptions_summary(db: Session, user: User) -> dict:
    if not (user_has_permission(user, "case.read.all") or user_has_permission(user, "admin.override")):
        return _module_unavailable("Data exceptions need organisation case access.")

    from app.services.data_exceptions_service import exception_counts

    counts = exception_counts(db, user)
    return _module_ok(
        {
            "dateBasis": "as_of_generation",
            "asOf": today_ist().isoformat(),
            "confirmed": counts.get("confirmed", 0),
            "suspected": counts.get("suspected", 0),
            "href": "/admin/data-exceptions",
        }
    )


def build_leadership_overview(
    db: Session,
    user: User,
    *,
    period_month: str | None = None,
    product_module: str | None = None,
) -> dict:
    period = resolve_period(period_month)
    module = (product_module or "").strip() or None
    modules: dict[str, dict] = {}

    builders = {
        "cases": lambda: _cases_module(db, user, period, module),
        "assignments": lambda: _assignments_module(db, user, period, module),
        "sessions": lambda: _sessions_module(db, user, period, module),
        "finance": lambda: _finance_module(db, user, period, module),
        "tickets": lambda: _tickets_module(db, user, period, module),
        "staffAttendance": lambda: _staff_attendance_module(db, user, period),
        "queues": lambda: _queues_module(db, user, period, module),
        "therapistAttention": lambda: _therapist_attention_summary(db, user),
        "dataExceptions": lambda: _data_exceptions_summary(db, user),
    }
    for name, builder in builders.items():
        try:
            modules[name] = builder()
        except Exception as exc:  # noqa: BLE001 — isolate dashboard modules
            modules[name] = _module_fail(exc)

    generated = datetime.now(timezone.utc).astimezone(IST)
    return {
        "period": {
            "month": period["month"],
            "dateFrom": period["dateFrom"],
            "dateTo": period["dateTo"],
            "timezone": period["timezone"],
            "generatedAt": generated.isoformat(),
            "asOf": period["today"].isoformat(),
            "defaultMonth": default_billing_month(),
        },
        "productModule": module,
        "modules": modules,
    }
