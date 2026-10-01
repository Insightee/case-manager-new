"""HR session discrepancy detection (pure rules, IST wall-clock)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from app.core.session_rules import duration_minutes_between
from app.core.session_times import effective_session_datetimes
from app.core.timezone import ensure_utc_aware
from app.models.case import Case
from app.models.session import SessionStatus

if TYPE_CHECKING:
    from app.models.daily_log import DailyLog
    from app.models.session import Session as TherapySession

IST = ZoneInfo("Asia/Kolkata")

MIN_COMPLIANCE_MINUTES = 40
SCHEDULE_PADDING_HOURS = 1
VERY_SHORT_MAX_MINUTES = 5

MODULES_PREFER_SCHEDULED_WINDOW = frozenset({"shadow_support", "homecare"})

ANOMALY_GUIDANCE: dict[str, str] = {
    "MISSING_LOG": "This visit is completed but still needs a session log submitted.",
    "DURATION_UNDER_40_MIN": (
        f"Recorded visit time is under {MIN_COMPLIANCE_MINUTES} minutes — "
        "please review clock times or use Forgot to log with accurate times."
    ),
    "CLOCK_OUTSIDE_SCHEDULE": (
        "Visit clock-in or clock-out sits outside the scheduled window "
        f"(±{SCHEDULE_PADDING_HOURS} hour). Please review times."
    ),
    "USE_FORGOT_TO_LOG_INSTEAD": (
        "Times look like a retroactive entry outside the live session window — "
        "use Forgot to log with when the visit actually happened."
    ),
    "FORGOT_TO_LOG_USED": "Visit was completed through Forgot to log (audit trail).",
    "MANUAL_SESSION": "Visit was created as a manual / walk-in session (audit trail).",
    "LOG_SUBMITTED_BEFORE_VISIT_START": (
        "Log submission timestamp is before the recorded visit start — please verify times."
    ),
    "NEXT_SESSION_STARTED_BEFORE_PRIOR_LOG": (
        "A later visit started before the previous visit's log was submitted — "
        "complete logs in order when you can."
    ),
    "AUTO_CLOSED_NO_LOG": "Visit auto-closed at day end and still needs a log.",
    "LATE_ADDITION": "Log was added after the visit day (late addition).",
    "VERY_SHORT_AFTER_START": (
        f"Very short visit ({VERY_SHORT_MAX_MINUTES} minutes or less) — "
        "confirm this was intentional or cancel accidental starts quickly."
    ),
    "MULTIPLE_COMPLETED_SAME_DAY": "More than one completed visit on the same day — may need review.",
    "COMPLETED_WITHOUT_CLOCK": "Visit is completed but has no clock-in/out times recorded.",
    "NO_SCHEDULED_WINDOW": (
        "This service line usually expects a scheduled start/end — add schedule or use Forgot to log."
    ),
}


def _combine_ist(d: date, t: time) -> datetime:
    return datetime.combine(d, t, tzinfo=IST)


def scheduled_window_ist(session: TherapySession) -> tuple[datetime, datetime] | None:
    if session.scheduled_date is None or session.start_time is None or session.end_time is None:
        return None
    start = _combine_ist(session.scheduled_date, session.start_time)
    end = _combine_ist(session.scheduled_date, session.end_time)
    if end <= start:
        end += timedelta(days=1)
    return start, end


def _to_ist(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    aware = ensure_utc_aware(dt)
    if aware is None:
        return None
    return aware.astimezone(IST)


def effective_duration_minutes(session: TherapySession, log: DailyLog | None = None) -> int | None:
    start, end = effective_session_datetimes(session, log)
    if start is None or end is None:
        if session.actual_start_at and session.actual_end_at:
            return duration_minutes_between(session.actual_start_at, session.actual_end_at)
        return None
    mins = duration_minutes_between(start, end)
    return mins if mins > 0 else None


def on_time_early_checkout_exception(
    session: TherapySession,
    log: DailyLog | None,
    window: tuple[datetime, datetime],
    duration_mins: int | None,
) -> bool:
    """Allowed: on-time check-in, ≥40 min, checkout before scheduled end."""
    if duration_mins is None or duration_mins < MIN_COMPLIANCE_MINUTES:
        return False
    sched_start, sched_end = window
    actual_start = _to_ist(session.actual_start_at)
    actual_end = _to_ist(session.actual_end_at)
    if actual_start is None or actual_end is None:
        start, end = effective_session_datetimes(session, log)
        actual_start = _to_ist(start)
        actual_end = _to_ist(end)
    if actual_start is None or actual_end is None:
        return False
    checkin_lo = sched_start - timedelta(hours=SCHEDULE_PADDING_HOURS)
    checkin_hi = sched_start + timedelta(hours=SCHEDULE_PADDING_HOURS)
    if not (checkin_lo <= actual_start <= checkin_hi):
        return False
    if actual_end >= sched_end:
        return False
    return True


def clock_outside_padded_schedule(
    session: TherapySession,
    log: DailyLog | None,
) -> bool:
    window = scheduled_window_ist(session)
    if window is None:
        return False
    sched_start, sched_end = window
    pad_start = sched_start - timedelta(hours=SCHEDULE_PADDING_HOURS)
    pad_end = sched_end + timedelta(hours=SCHEDULE_PADDING_HOURS)

    duration = effective_duration_minutes(session, log)
    if on_time_early_checkout_exception(session, log, window, duration):
        return False

    actual_start = _to_ist(session.actual_start_at)
    actual_end = _to_ist(session.actual_end_at)
    if actual_start is None or actual_end is None:
        return True

    def outside(dt: datetime) -> bool:
        return dt < pad_start or dt > pad_end

    return outside(actual_start) or outside(actual_end)


@dataclass(frozen=True)
class SessionAnomalyResult:
    codes: tuple[str, ...]
    guidance: str


def evaluate_session_anomalies(
    session: TherapySession,
    log: DailyLog | None,
    case: Case | None,
    *,
    audit_action: str | None = None,
    completed_same_day_count: int = 1,
    next_session_started_before_prior_log: bool = False,
) -> SessionAnomalyResult:
    codes: list[str] = []

    status_val = session.status.value if hasattr(session.status, "value") else str(session.status)
    is_completed = status_val == SessionStatus.COMPLETED.value

    if is_completed and log is None:
        codes.append("MISSING_LOG")

    duration = effective_duration_minutes(session, log) if is_completed else None
    if is_completed and duration is not None and duration < MIN_COMPLIANCE_MINUTES:
        codes.append("DURATION_UNDER_40_MIN")

    window = scheduled_window_ist(session)
    module = (case.product_module or "").lower() if case else ""
    if is_completed and window is None and module in MODULES_PREFER_SCHEDULED_WINDOW:
        codes.append("NO_SCHEDULED_WINDOW")

    if is_completed and window is not None and clock_outside_padded_schedule(session, log):
        codes.append("CLOCK_OUTSIDE_SCHEDULE")
        codes.append("USE_FORGOT_TO_LOG_INSTEAD")

    if audit_action == "complete_forgotten":
        codes.append("FORGOT_TO_LOG_USED")
    elif audit_action in ("create_manual", "create_manual_walk_in"):
        codes.append("MANUAL_SESSION")

    if log is not None and log.submitted_at and session.actual_start_at:
        submitted = ensure_utc_aware(log.submitted_at)
        started = ensure_utc_aware(session.actual_start_at)
        if submitted and started and submitted < started:
            codes.append("LOG_SUBMITTED_BEFORE_VISIT_START")

    if next_session_started_before_prior_log:
        codes.append("NEXT_SESSION_STARTED_BEFORE_PRIOR_LOG")

    if is_completed and session.auto_ended and log is None:
        codes.append("AUTO_CLOSED_NO_LOG")

    if log is not None and log.late_addition:
        codes.append("LATE_ADDITION")

    if is_completed and duration is not None and duration <= VERY_SHORT_MAX_MINUTES:
        codes.append("VERY_SHORT_AFTER_START")

    if is_completed and completed_same_day_count > 1:
        codes.append("MULTIPLE_COMPLETED_SAME_DAY")

    if is_completed and not session.actual_start_at and not session.actual_end_at:
        start, end = effective_session_datetimes(session, log)
        if start is None or end is None:
            codes.append("COMPLETED_WITHOUT_CLOCK")

    # Stable order for exports
    ordered = []
    seen: set[str] = set()
    for code in codes:
        if code not in seen:
            seen.add(code)
            ordered.append(code)

    guidance_parts = [ANOMALY_GUIDANCE[c] for c in ordered if c in ANOMALY_GUIDANCE]
    guidance = " ".join(guidance_parts)
    return SessionAnomalyResult(codes=tuple(ordered), guidance=guidance)


def fmt_time_ist(dt: datetime | None) -> str:
    ist = _to_ist(dt)
    if ist is None:
        return ""
    return ist.strftime("%Y-%m-%d %H:%M IST")


def fmt_time_only(t: time | None) -> str:
    if t is None:
        return ""
    return t.isoformat()[:5]
