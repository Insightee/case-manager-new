"""Session duration compliance: audit outliers and therapist pre-submit warnings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.core.session_rules import duration_minutes_between, scheduled_duration_minutes
from app.core.session_times import effective_session_datetimes
from app.models.case import CaseDayType
from app.models.daily_log import LogApprovalStatus
from app.models.session import SessionStatus

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.daily_log import DailyLog
    from app.models.session import Session as TherapySession

AUDIT_SHADOW_UNDER_3H_MINS = 180
AUDIT_HOMECARE_UNDER_30M_MINS = 30
AUDIT_OVER_10H_MINS = 600

SHADOW_HALF_DAY_REFERENCE_MINS = 300
SHADOW_FULL_DAY_REFERENCE_MINS = 600
HOMECARE_MIN_MINS = 60
HOMECARE_MAX_MINS = 240
SCHEDULED_DURATION_TOLERANCE_MINS = 15


def _enum_value(value) -> str | None:
    if value is None:
        return None
    return getattr(value, "value", value)

EXCLUDED_SESSION_STATUSES = frozenset(
    {
        SessionStatus.CANCELLED,
        SessionStatus.NO_SHOW,
        SessionStatus.RESCHEDULED,
        SessionStatus.CLIENT_ABSENT,
        SessionStatus.THERAPIST_LEAVE,
    }
)

EXCLUDED_ATTENDANCE = frozenset(
    {
        "ABSENT",
        "CLIENT_ABSENT",
        "CLIENT_LEAVE",
        "THERAPIST_LEAVE",
    }
)


@dataclass(frozen=True)
class ExpectedDurationBounds:
    min_mins: int
    max_mins: int
    reference_label: str
    has_schedule: bool


def effective_duration_minutes(
    session: TherapySession,
    log: DailyLog | None = None,
) -> int | None:
    start, end = effective_session_datetimes(session, log)
    if start is None or end is None:
        return None
    mins = duration_minutes_between(start, end)
    return mins if mins > 0 else None


def admin_list_duration_minutes(
    session: TherapySession,
    log: DailyLog | None = None,
) -> int | None:
    """Duration for admin tables/exports: effective when log exists, else clock or schedule."""
    if log is not None:
        mins = effective_duration_minutes(session, log)
        if mins is not None:
            return mins
    if session.actual_start_at and session.actual_end_at:
        return duration_minutes_between(session.actual_start_at, session.actual_end_at)
    if session.scheduled_date and session.start_time and session.end_time:
        return scheduled_duration_minutes(
            session.scheduled_date,
            session.start_time,
            session.end_time,
            slot_duration_minutes=session.slot_duration_minutes,
        )
    return None


def is_billable_session_log(session: TherapySession, log: DailyLog | None) -> bool:
    if log is None:
        return False
    if session.status != SessionStatus.COMPLETED:
        return False
    status = session.status.value if hasattr(session.status, "value") else str(session.status)
    if status in {s.value for s in EXCLUDED_SESSION_STATUSES}:
        return False
    attendance = (log.attendance_status or "").upper()
    if attendance in EXCLUDED_ATTENDANCE:
        return False
    return True


def audit_outlier_flag(product_module: str | None, duration_mins: int | None) -> str | None:
    if duration_mins is None:
        return None
    module = (product_module or "").lower()
    if duration_mins > AUDIT_OVER_10H_MINS:
        return "over_10h"
    if module == "shadow_support" and duration_mins < AUDIT_SHADOW_UNDER_3H_MINS:
        return "shadow_under_3h"
    if module == "homecare" and duration_mins < AUDIT_HOMECARE_UNDER_30M_MINS:
        return "homecare_under_30m"
    return None


def _has_scheduled_window(session: TherapySession) -> bool:
    return (
        session.scheduled_date is not None
        and session.start_time is not None
        and session.end_time is not None
    )


def expected_duration_bounds(case: Case, session: TherapySession) -> ExpectedDurationBounds:
    module = (case.product_module or "").lower()
    if _has_scheduled_window(session):
        sched_mins = scheduled_duration_minutes(
            session.scheduled_date,
            session.start_time,
            session.end_time,
            slot_duration_minutes=session.slot_duration_minutes,
        )
        sched_mins = max(1, sched_mins)
        return ExpectedDurationBounds(
            min_mins=max(1, sched_mins - SCHEDULED_DURATION_TOLERANCE_MINS),
            max_mins=sched_mins + SCHEDULED_DURATION_TOLERANCE_MINS,
            reference_label=f"scheduled {sched_mins} min",
            has_schedule=True,
        )
    if module == "shadow_support":
        day_type = _enum_value(case.day_type) or CaseDayType.FULL_DAY.value
        if day_type == CaseDayType.HALF_DAY.value:
            ref = SHADOW_HALF_DAY_REFERENCE_MINS
            return ExpectedDurationBounds(
                min_mins=ref,
                max_mins=ref,
                reference_label="half-day shadow (5 hours)",
                has_schedule=False,
            )
        ref = SHADOW_FULL_DAY_REFERENCE_MINS
        return ExpectedDurationBounds(
            min_mins=ref,
            max_mins=ref,
            reference_label="full-day shadow (10 hours)",
            has_schedule=False,
        )
    if module == "homecare":
        return ExpectedDurationBounds(
            min_mins=HOMECARE_MIN_MINS,
            max_mins=HOMECARE_MAX_MINS,
            reference_label="homecare (1–4 hours)",
            has_schedule=False,
        )
    return ExpectedDurationBounds(
        min_mins=1,
        max_mins=AUDIT_OVER_10H_MINS,
        reference_label="session duration",
        has_schedule=False,
    )


def duration_compliance_warning(
    case: Case,
    session: TherapySession,
    log: DailyLog | None = None,
) -> dict | None:
    if not is_billable_session_log(session, log):
        return None
    actual_mins = effective_duration_minutes(session, log)
    if actual_mins is None:
        return None
    bounds = expected_duration_bounds(case, session)
    if bounds.min_mins <= actual_mins <= bounds.max_mins:
        return None

    if actual_mins < bounds.min_mins:
        code = "under_minimum"
        message = (
            f"{actual_mins} min vs {bounds.reference_label} (±{SCHEDULED_DURATION_TOLERANCE_MINS})."
            if bounds.has_schedule
            else f"{actual_mins} min — below {bounds.reference_label}."
        )
    else:
        code = "over_maximum"
        message = (
            f"{actual_mins} min vs {bounds.reference_label} (±{SCHEDULED_DURATION_TOLERANCE_MINS})."
            if bounds.has_schedule
            else f"{actual_mins} min — above {bounds.reference_label}."
        )

    return {
        "code": code,
        "message": message,
        "min_mins": bounds.min_mins,
        "max_mins": bounds.max_mins,
        "actual_mins": actual_mins,
        "reference_label": bounds.reference_label,
        "has_schedule": bounds.has_schedule,
    }


def audit_outlier_label(flag: str | None) -> str:
    labels = {
        "shadow_under_3h": "Shadow under 3 hours",
        "shadow_over_10h": "Shadow over 10 hours",
        "homecare_under_30m": "Homecare under 30 minutes",
        "over_10h": "Over 10 hours",
    }
    return labels.get(flag or "", flag or "")
