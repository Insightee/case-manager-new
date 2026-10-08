"""Organisation-wide operational counts for an integration key.

Read-only aggregates. Case codes appear only on capped exception lists.
Child names, contact fields, and free text are never selected.

Day windows are Asia/Kolkata calendar dates. ``sessions.scheduled_date`` is
already a date. Timestamp columns are converted to IST. ``monthly_reports.month``
is stored as ``Mon YYYY`` (for example ``Sep 2026``) and is not a day key.

A suspended session is counted as on-or-after the status change only when
``cases.status_effective_date`` is set. Rows with a null effective date stay
``unknown`` — there is no fallback date.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import Date, cast, func, or_, select
from sqlalchemy.orm import Session

from app.core.audit import log_audit
from app.core.timezone import IST
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.billing_approval_request import BillingApprovalRequest, BillingApprovalStatus
from app.models.case import BillingType, Case, CaseStatus
from app.models.client_billing import CarePackage, CarePackageStatus
from app.models.clinical_report import ClinicalReport, ClinicalReportStatus
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.ledger_billing import BillableStatus, BillingLedger, LedgerEventType
from app.models.leave import LeaveStatus, TherapistLeave
from app.models.report import MonthlyReport, ReportStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.session_absence import SessionAbsenceRequest, SessionAbsenceStatus
from app.models.user import EmploymentStatus, User
from app.services.integration.access import IntegrationPrincipal, require_scope
from app.services.integration.errors import ValidationError
from app.services.integration.rate_limit import check_rate_limit

MAX_RANGE_DAYS = 93
CASE_CODE_LIST_LIMIT = 50

_SUSPENDED_SESSION_STATUSES = (SessionStatus.SCHEDULED, SessionStatus.COMPLETED)
_CLOSED_CASE_STATUSES = (CaseStatus.CLOSED, CaseStatus.DEACTIVATED)
_PACKAGE_STATUSES = (CarePackageStatus.ACTIVE, CarePackageStatus.EXHAUSTED)
_INACTIVE_EMPLOYMENT = (EmploymentStatus.SUSPENDED, EmploymentStatus.ARCHIVED)

_OBSERVATION_UNKNOWN = (
    "observation_reports can be APPROVED but the table has no submission timestamp, "
    "so approved-without-submission cannot be computed."
)
_SUSPENDED_DATE_UNKNOWN = (
    "SUSPENDED cases with no status_effective_date cannot be placed on or after the "
    "status change. Those sessions are excluded from sessions_on_suspended_case."
)


def get_ops_aggregate(
    db: Session,
    principal: IntegrationPrincipal,
    *,
    date_from: date,
    date_to: date,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    """Counts for every case. Case grants are not applied."""
    require_scope(principal, "ops:aggregate:read")
    _validate_range(date_from, date_to)
    check_rate_limit(principal.client_id, limit_per_minute=principal.client.rate_limit_per_minute)
    _register_sqlite_ist_date(db)

    payload = {
        "timezone": "Asia/Kolkata",
        "from": date_from.isoformat(),
        "to": date_to.isoformat(),
        "snapshot": _snapshot(db),
        "days": _days(db, date_from, date_to),
        "integrity": _integrity(db, date_from, date_to),
        "not_computed": [
            {
                "metric": "observation_reports_approved_missing_submission",
                "status": "unknown",
                "reason": _OBSERVATION_UNKNOWN,
            },
            {
                "metric": "suspended_sessions_missing_status_effective_date",
                "status": "unknown",
                "reason": _SUSPENDED_DATE_UNKNOWN,
            },
        ],
        "definitions": {
            "active_cases_unassigned": "ACTIVE cases with no ACTIVE case assignment.",
            "active_case_assignments": "Assignment rows with status ACTIVE, not distinct cases.",
            "sessions_on_suspended_case": (
                "SCHEDULED or COMPLETED sessions on SUSPENDED cases whose scheduled_date "
                "is on or after status_effective_date."
            ),
            "sessions_after_closure": (
                "Sessions on CLOSED or DEACTIVATED cases whose scheduled_date is after "
                "status_effective_date."
            ),
            "completed_sessions_missing_daily_log": (
                "COMPLETED sessions with scheduled_date inside from..to and no daily_logs row."
            ),
            "care_packages_used_vs_ledger_consumption": (
                "ACTIVE or EXHAUSTED care packages whose used_sessions differs from the "
                "count of PACKAGE_CONSUMPTION ledger rows for that package."
            ),
            "care_packages_used_vs_completed_sessions": (
                "ACTIVE or EXHAUSTED care packages whose used_sessions differs from COMPLETED "
                "sessions linked by those PACKAGE_CONSUMPTION rows. Sessions have no care_package_id."
            ),
            "package_cases_missing_session_count": (
                "Cases with billing_type PACKAGE and package_session_count null or not positive."
            ),
            "day_basis": {
                "sessions": "scheduled_date",
                "daily_logs": "created_at in Asia/Kolkata",
                "monthly_reports": "created_at in Asia/Kolkata",
            },
            "separate_queues": (
                "PENDING daily logs and PENDING_REVIEW ledger rows are reported separately "
                "and are not added together."
            ),
        },
    }
    log_audit(
        db,
        actor_user_id=None,
        integration_client_id=principal.client_id,
        action="integration.ops_aggregate",
        entity_type="ops_aggregate",
        entity_id=principal.client_id,
        new_value={"from": payload["from"], "to": payload["to"]},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return payload


def _validate_range(date_from: date, date_to: date) -> None:
    if date_to < date_from:
        raise ValidationError("The start date needs to be on or before the end date.")
    inclusive_days = (date_to - date_from).days + 1
    if inclusive_days > MAX_RANGE_DAYS:
        raise ValidationError(
            f"That window is longer than {MAX_RANGE_DAYS} days. A shorter range keeps this summary quick."
        )


def _snapshot(db: Session) -> dict[str, Any]:
    case_rows = db.execute(select(Case.status, func.count()).group_by(Case.status)).all()
    log_rows = db.execute(select(DailyLog.approval_status, func.count()).group_by(DailyLog.approval_status)).all()
    ledger_rows = db.execute(
        select(BillingLedger.billable_status, func.count()).group_by(BillingLedger.billable_status)
    ).all()
    active_assignment = (
        select(CaseAssignment.id)
        .where(
            CaseAssignment.case_id == Case.id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
        .exists()
    )
    unassigned = db.scalar(
        select(func.count()).select_from(Case).where(Case.status == CaseStatus.ACTIVE, ~active_assignment)
    )
    active_assignments = db.scalar(
        select(func.count())
        .select_from(CaseAssignment)
        .where(CaseAssignment.status == CaseAssignmentStatus.ACTIVE)
    )
    return {
        "cases_by_status": _count_map(case_rows, tuple(item.value for item in CaseStatus)),
        "active_cases_unassigned": int(unassigned or 0),
        "active_case_assignments": int(active_assignments or 0),
        "daily_logs_by_approval_status": _count_map(log_rows, tuple(item.value for item in LogApprovalStatus)),
        "billing_ledger_by_billable_status": _count_map(ledger_rows, tuple(item.value for item in BillableStatus)),
        "billing_approval_requests_pending": _count_where(
            db, BillingApprovalRequest, BillingApprovalRequest.status == BillingApprovalStatus.PENDING
        ),
        "session_absence_requests_pending_approval": _count_where(
            db, SessionAbsenceRequest, SessionAbsenceRequest.status == SessionAbsenceStatus.PENDING_APPROVAL
        ),
        "therapist_leaves_pending": _count_where(db, TherapistLeave, TherapistLeave.status == LeaveStatus.PENDING),
    }


def _days(db: Session, date_from: date, date_to: date) -> list[dict[str, Any]]:
    start, end = _ist_bounds(date_from, date_to)
    by_date = {_iso(day): _blank_day(day) for day in _iter_days(date_from, date_to)}

    session_rows = db.execute(
        select(TherapySession.scheduled_date, TherapySession.status, func.count())
        .where(
            TherapySession.scheduled_date >= date_from,
            TherapySession.scheduled_date <= date_to,
        )
        .group_by(TherapySession.scheduled_date, TherapySession.status)
    ).all()
    for scheduled, status, count in session_rows:
        _add_day_count(by_date, scheduled, "sessions_by_status", status, count)

    log_day = _ist_day_expr(db, DailyLog.created_at)
    log_rows = db.execute(
        select(log_day, DailyLog.approval_status, func.count())
        .where(DailyLog.created_at >= start, DailyLog.created_at < end)
        .group_by(log_day, DailyLog.approval_status)
    ).all()
    for day_value, status, count in log_rows:
        _add_day_count(by_date, day_value, "daily_logs_created_by_approval_status", status, count)

    report_day = _ist_day_expr(db, MonthlyReport.created_at)
    report_rows = db.execute(
        select(report_day, MonthlyReport.status, func.count())
        .where(MonthlyReport.created_at >= start, MonthlyReport.created_at < end)
        .group_by(report_day, MonthlyReport.status)
    ).all()
    for day_value, status, count in report_rows:
        _add_day_count(by_date, day_value, "monthly_reports_by_status", status, count)

    return [by_date[_iso(day)] for day in _iter_days(date_from, date_to)]


def _integrity(db: Session, date_from: date, date_to: date) -> dict[str, Any]:
    inactive = _inactive_therapist_filters()
    suspended_known = _suspended_session_filters(dated=True)
    suspended_unknown = _suspended_session_filters(dated=False)
    after_close = (
        Case.status.in_(_CLOSED_CASE_STATUSES),
        Case.status_effective_date.is_not(None),
        TherapySession.scheduled_date > Case.status_effective_date,
    )
    missing_effective = (
        Case.status.in_(_CLOSED_CASE_STATUSES),
        Case.status_effective_date.is_(None),
    )
    missing_log = (
        TherapySession.status == SessionStatus.COMPLETED,
        TherapySession.scheduled_date >= date_from,
        TherapySession.scheduled_date <= date_to,
        ~select(DailyLog.id).where(DailyLog.session_id == TherapySession.id).exists(),
    )
    missing_package_count = (
        Case.billing_type == BillingType.PACKAGE,
        or_(Case.package_session_count.is_(None), Case.package_session_count <= 0),
    )
    monthly_missing_submission = (
        MonthlyReport.status == ReportStatus.APPROVED,
        MonthlyReport.submitted_for_review_at.is_(None),
    )
    clinical_missing_submission = (
        ClinicalReport.status == ClinicalReportStatus.APPROVED.value,
        ClinicalReport.submitted_at.is_(None),
    )

    unknown_sessions = _exception(
        db,
        select(func.count()).select_from(TherapySession).join(Case, Case.id == TherapySession.case_id).where(*suspended_unknown),
        select(Case.case_code)
        .join(TherapySession, TherapySession.case_id == Case.id)
        .where(*suspended_unknown)
        .distinct(),
    )
    return {
        "active_case_inactive_therapist": _exception(
            db,
            select(func.count(func.distinct(Case.id)))
            .select_from(Case)
            .join(CaseAssignment, CaseAssignment.case_id == Case.id)
            .join(User, User.id == CaseAssignment.therapist_user_id)
            .where(*inactive),
            select(Case.case_code)
            .join(CaseAssignment, CaseAssignment.case_id == Case.id)
            .join(User, User.id == CaseAssignment.therapist_user_id)
            .where(*inactive)
            .distinct(),
        ),
        "sessions_on_suspended_case": _exception(
            db,
            select(func.count()).select_from(TherapySession).join(Case, Case.id == TherapySession.case_id).where(*suspended_known),
            select(Case.case_code)
            .join(TherapySession, TherapySession.case_id == Case.id)
            .where(*suspended_known)
            .distinct(),
        ),
        "suspended_sessions_missing_status_effective_date": {
            "count": None,
            "status": "unknown",
            "reason": _SUSPENDED_DATE_UNKNOWN,
            "unclassified_session_count": unknown_sessions["count"],
            "case_codes": unknown_sessions["case_codes"],
            "case_codes_truncated": unknown_sessions["case_codes_truncated"],
        },
        "sessions_after_closure": _exception(
            db,
            select(func.count()).select_from(TherapySession).join(Case, Case.id == TherapySession.case_id).where(*after_close),
            select(Case.case_code)
            .join(TherapySession, TherapySession.case_id == Case.id)
            .where(*after_close)
            .distinct(),
        ),
        "closed_or_deactivated_missing_effective_date": _exception(
            db,
            select(func.count()).select_from(Case).where(*missing_effective),
            select(Case.case_code).where(*missing_effective).distinct(),
        ),
        "monthly_reports_approved_missing_submission": _exception(
            db,
            select(func.count()).select_from(MonthlyReport).where(*monthly_missing_submission),
            select(Case.case_code)
            .join(MonthlyReport, MonthlyReport.case_id == Case.id)
            .where(*monthly_missing_submission)
            .distinct(),
        ),
        "clinical_reports_approved_missing_submission": _exception(
            db,
            select(func.count()).select_from(ClinicalReport).where(*clinical_missing_submission),
            select(Case.case_code)
            .join(ClinicalReport, ClinicalReport.case_id == Case.id)
            .where(*clinical_missing_submission)
            .distinct(),
        ),
        "observation_reports_approved_missing_submission": {
            "count": None,
            "status": "unknown",
            "reason": _OBSERVATION_UNKNOWN,
        },
        "completed_sessions_missing_daily_log": _exception(
            db,
            select(func.count()).select_from(TherapySession).where(*missing_log),
            select(Case.case_code)
            .join(TherapySession, TherapySession.case_id == Case.id)
            .where(*missing_log)
            .distinct(),
        ),
        "care_packages_used_vs_ledger_consumption": _package_exception(
            db, lambda: CarePackage.used_sessions != _package_consumption_count()
        ),
        "care_packages_used_vs_completed_sessions": _package_exception(
            db, lambda: CarePackage.used_sessions != _package_completed_session_count()
        ),
        "package_cases_missing_session_count": _exception(
            db,
            select(func.count()).select_from(Case).where(*missing_package_count),
            select(Case.case_code).where(*missing_package_count).distinct(),
        ),
    }


def _inactive_therapist_filters():
    return (
        Case.status == CaseStatus.ACTIVE,
        CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        or_(User.is_active.is_(False), User.employment_status.in_(_INACTIVE_EMPLOYMENT)),
    )


def _suspended_session_filters(*, dated: bool):
    filters = [
        Case.status == CaseStatus.SUSPENDED,
        TherapySession.status.in_(_SUSPENDED_SESSION_STATUSES),
    ]
    if dated:
        filters.append(Case.status_effective_date.is_not(None))
        filters.append(TherapySession.scheduled_date >= Case.status_effective_date)
    else:
        filters.append(Case.status_effective_date.is_(None))
    return tuple(filters)


def _package_exception(db: Session, mismatch):
    def _status():
        return CarePackage.status.in_(_PACKAGE_STATUSES)

    return _exception(
        db,
        select(func.count()).select_from(CarePackage).where(_status(), mismatch()),
        select(Case.case_code)
        .join(CarePackage, CarePackage.case_id == Case.id)
        .where(_status(), mismatch())
        .distinct(),
    )


def _package_consumption_count():
    return (
        select(func.count())
        .select_from(BillingLedger)
        .where(
            BillingLedger.care_package_id == CarePackage.id,
            BillingLedger.event_type == LedgerEventType.PACKAGE_CONSUMPTION,
        )
        .correlate(CarePackage)
        .scalar_subquery()
    )


def _package_completed_session_count():
    return (
        select(func.count())
        .select_from(BillingLedger)
        .join(TherapySession, TherapySession.id == BillingLedger.session_id)
        .where(
            BillingLedger.care_package_id == CarePackage.id,
            BillingLedger.event_type == LedgerEventType.PACKAGE_CONSUMPTION,
            TherapySession.status == SessionStatus.COMPLETED,
        )
        .correlate(CarePackage)
        .scalar_subquery()
    )


def _exception(db: Session, count_stmt, code_stmt) -> dict[str, Any]:
    count = int(db.scalar(count_stmt) or 0)
    rows = db.scalars(code_stmt.order_by(Case.case_code).limit(CASE_CODE_LIST_LIMIT + 1)).all()
    codes = [str(code) for code in rows if code]
    truncated = len(codes) > CASE_CODE_LIST_LIMIT
    return {
        "count": count,
        "case_codes": codes[:CASE_CODE_LIST_LIMIT],
        "case_codes_truncated": truncated,
    }


def _count_where(db: Session, model, predicate) -> int:
    return int(db.scalar(select(func.count()).select_from(model).where(predicate)) or 0)


def _count_map(rows, known: tuple[str, ...]) -> dict[str, int]:
    found: dict[str, int] = {}
    for key, count in rows:
        name = _norm(key)
        if not name:
            continue
        found[name] = found.get(name, 0) + int(count or 0)
    mapped = {key: int(found.pop(key, 0)) for key in known}
    for key in sorted(found):
        mapped[key] = found[key]
    return mapped


def _blank_day(day: date) -> dict[str, Any]:
    return {
        "date": day.isoformat(),
        "sessions_by_status": {item.value: 0 for item in SessionStatus},
        "daily_logs_created_by_approval_status": {item.value: 0 for item in LogApprovalStatus},
        "monthly_reports_by_status": {item.value: 0 for item in ReportStatus},
    }


def _add_day_count(by_date: dict[str, dict], day_value, bucket: str, status, count) -> None:
    key = _day_key(day_value)
    if key is None or key not in by_date:
        return
    name = _norm(status)
    if not name:
        return
    target = by_date[key][bucket]
    target[name] = int(target.get(name, 0)) + int(count or 0)


def _iter_days(date_from: date, date_to: date):
    day = date_from
    while day <= date_to:
        yield day
        day += timedelta(days=1)


def _ist_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    start = datetime.combine(date_from, datetime.min.time(), tzinfo=IST).astimezone(timezone.utc)
    end_day = date_to + timedelta(days=1)
    end = datetime.combine(end_day, datetime.min.time(), tzinfo=IST).astimezone(timezone.utc)
    return start, end


def _ist_day_expr(db: Session, column):
    return _ist_day_expr_for_dialect(db.get_bind().dialect.name, column)


def _ist_day_expr_for_dialect(dialect_name: str, column):
    if dialect_name == "postgresql":
        return cast(func.timezone("Asia/Kolkata", column), Date)
    return func.ist_date(column)


def _register_sqlite_ist_date(db: Session) -> None:
    if db.get_bind().dialect.name != "sqlite":
        return
    raw = _sqlite_dbapi(db)
    raw.create_function("ist_date", 1, _sqlite_ist_date, deterministic=True)


def _sqlite_dbapi(db: Session):
    sa_conn = db.connection()
    raw = sa_conn.connection
    if hasattr(raw, "create_function"):
        return raw
    driver = getattr(raw, "driver_connection", None)
    if driver is not None and hasattr(driver, "create_function"):
        return driver
    raise RuntimeError("SQLite connection cannot register ist_date")


def _sqlite_ist_date(value):
    """IST calendar date for a SQLite datetime string stored as UTC wall time."""
    if value is None:
        return None
    if isinstance(value, datetime):
        moment = value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            moment = datetime.fromisoformat(text)
        except ValueError:
            return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(IST).date().isoformat()


def _day_key(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if len(text) < 10:
        return None
    return text[:10]


def _iso(day: date) -> str:
    return day.isoformat()


def _norm(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "value"):
        return str(value.value)
    text = str(value).strip()
    return text or None
