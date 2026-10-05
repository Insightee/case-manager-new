"""Shared billing-month parsing and IST timestamp bounds.

Stored therapist invoice months may be YYYY-MM, 'Oct 2026', or 'October 2026'.
Those are valid aliases, not corrupt data. Do not rewrite stored strings.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone

from app.core.timezone import IST, today_ist


def default_billing_month() -> str:
    return today_ist().strftime("%Y-%m")


def try_parse_billing_month(value: str | None) -> str | None:
    """Return YYYY-MM or None when the value is not a known month spelling."""
    raw = (value or "").strip()
    if not raw:
        return None
    if len(raw) >= 7 and raw[4] == "-":
        y, m = raw[:7].split("-")
        if y.isdigit() and m.isdigit() and 1 <= int(m) <= 12:
            return raw[:7]
    for fmt in ("%b %Y", "%B %Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m")
        except ValueError:
            continue
    return None


def parse_billing_month(value: str | None) -> str:
    """Return YYYY-MM. Accepts YYYY-MM, %b %Y, and %B %Y. Default: current IST month."""
    return try_parse_billing_month(value) or default_billing_month()


def therapist_invoice_month_keys(ym: str) -> tuple[str, ...]:
    """All stored Invoice.month spellings that mean the same billing month."""
    canonical = parse_billing_month(ym)
    y, m = int(canonical[:4]), int(canonical[5:7])
    start = date(y, m, 1)
    return (canonical, start.strftime("%b %Y"), start.strftime("%B %Y"))


def month_date_bounds(ym: str) -> tuple[date, date]:
    canonical = parse_billing_month(ym)
    y, m = int(canonical[:4]), int(canonical[5:7])
    return date(y, m, 1), date(y, m, monthrange(y, m)[1])


def ist_day_utc_bounds(day: date) -> tuple[datetime, datetime]:
    """Half-open UTC interval covering one IST calendar date: [start, end)."""
    start = datetime.combine(day, time.min, tzinfo=IST).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=IST).astimezone(timezone.utc)
    return start, end


def ist_date_range_utc_bounds(start: date, end_inclusive: date) -> tuple[datetime, datetime]:
    start_utc, _ = ist_day_utc_bounds(start)
    _, end_utc = ist_day_utc_bounds(end_inclusive)
    return start_utc, end_utc


def ist_month_utc_bounds(ym: str) -> tuple[datetime, datetime]:
    first, last = month_date_bounds(ym)
    return ist_date_range_utc_bounds(first, last)
