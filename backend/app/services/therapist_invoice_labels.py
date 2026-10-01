"""Therapist-facing invoice copy — keep finance jargon out of the therapist UI/PDF."""
from __future__ import annotations


PENDING_TAG = "Pending"

BUCKET_IN_PAY = "in_pay"
BUCKET_PENDING = "pending"
BUCKET_INFO = "info"


def session_completed_label(*, line_type: str | None = None) -> str:
    if line_type == "ADDITIONAL":
        return "Extra session"
    if line_type == "INCLUDED":
        return "Session completed"
    return "Session completed"


def child_away_label(*, is_shadow: bool = False, pending: bool = False) -> str:
    del is_shadow  # Same wording for all modules — amount stays ₹0.
    if pending:
        return "Session cancelled"
    return "Session cancelled"


def leave_label(*, is_shadow: bool, paid: bool, pending: bool = False) -> str:
    if pending:
        return "Leave" if is_shadow else "Session cancelled"
    if not is_shadow:
        return "Session cancelled"
    if paid:
        return "Paid leave"
    return "Unpaid leave"


def pending_reason_label(*, late: bool) -> str:
    return "Added from invoice" if late else "Waiting for log review"
