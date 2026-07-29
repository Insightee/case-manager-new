"""Time-limited leave and child-absence re-entry window for platform migration."""
from __future__ import annotations

from datetime import date

from app.core.config import settings


def migration_window_end() -> date:
    raw = (settings.leave_migration_end_date or "2026-07-31").strip()
    return date.fromisoformat(raw)


def migration_reentry_start() -> date:
    end = migration_window_end()
    return date(end.year, end.month, 1)


def migration_reentry_end() -> date:
    return migration_window_end()


def is_migration_window_active(*, as_of: date | None = None) -> bool:
    as_of = as_of or date.today()
    return as_of <= migration_window_end()


def is_retroactive_leave(start_date: date, end_date: date, *, as_of: date | None = None) -> bool:
    as_of = as_of or date.today()
    if end_date < as_of:
        return True
    return False


def is_retroactive_absence(absence_date: date, *, as_of: date | None = None) -> bool:
    return is_retroactive_leave(absence_date, absence_date, as_of=as_of)


def is_migration_reentry(start_date: date, end_date: date, *, as_of: date | None = None) -> bool:
    """Past leave within the migration month while the re-entry window is open."""
    if not is_migration_window_active(as_of=as_of):
        return False
    if not is_retroactive_leave(start_date, end_date, as_of=as_of):
        return False
    window_start = migration_reentry_start()
    window_end = migration_reentry_end()
    return start_date >= window_start and end_date <= window_end


def is_migration_absence_reentry(absence_date: date, *, as_of: date | None = None) -> bool:
    return is_migration_reentry(absence_date, absence_date, as_of=as_of)


def validate_therapist_leave_dates(
    start_date: date,
    end_date: date,
    *,
    as_of: date | None = None,
) -> None:
    """Block retroactive therapist submissions outside the migration re-entry window."""
    as_of = as_of or date.today()
    if not is_retroactive_leave(start_date, end_date, as_of=as_of):
        return
    if is_migration_reentry(start_date, end_date, as_of=as_of):
        return
    if is_migration_window_active(as_of=as_of):
        window_start = migration_reentry_start()
        window_end = migration_reentry_end()
        raise ValueError(
            f"During migration, past leave can only be re-entered for "
            f"{window_start.isoformat()} through {window_end.isoformat()}."
        )
    raise ValueError(
        "Past leave dates are not open for self-service entry. "
        "Contact HR if you need a historical leave recorded."
    )


def validate_child_absence_date(scheduled_date: date, *, as_of: date | None = None) -> None:
    """Block retroactive child absence outside the migration re-entry window."""
    as_of = as_of or date.today()
    if scheduled_date > as_of:
        raise ValueError("Child absence cannot be logged for a future date.")
    if scheduled_date >= as_of:
        return
    if is_migration_absence_reentry(scheduled_date, as_of=as_of):
        return
    if is_migration_window_active(as_of=as_of):
        window_start = migration_reentry_start()
        window_end = migration_reentry_end()
        raise ValueError(
            f"During migration, past child absence can only be logged for "
            f"{window_start.isoformat()} through {window_end.isoformat()}."
        )
    raise ValueError(
        "Past child absence can only be logged for today's scheduled visit. "
        "Contact your case manager if you need a historical absence recorded."
    )


def migration_info_payload(*, as_of: date | None = None) -> dict:
    as_of = as_of or date.today()
    window_end = migration_window_end()
    reentry_start = migration_reentry_start()
    reentry_end = migration_reentry_end()
    active = is_migration_window_active(as_of=as_of)
    month_label = reentry_start.strftime("%B %Y")
    return {
        "window_active": active,
        "window_end": window_end.isoformat(),
        "reentry_start": reentry_start.isoformat(),
        "reentry_end": reentry_end.isoformat(),
        "banner_message": (
            f"July backfill open through {reentry_end.day} {reentry_end.strftime('%B')}: "
            f"re-enter therapist leave or child absence for any day in {month_label}. "
            "HR will review and approve — live sessions will not be changed for past dates."
        )
        if active
        else None,
        "hr_retroactive_hint": (
            "Previous leave — this dates back to before today. Approving records it for "
            "balance tracking only; booked sessions will not be cancelled."
        ),
        "hr_retroactive_absence_hint": (
            "Previous absence — this dates back to before today. Approving records the child "
            "as absent for billing; visit times were not changed."
        ),
    }
