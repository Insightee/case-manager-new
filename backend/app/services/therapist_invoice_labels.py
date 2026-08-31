"""Therapist-facing invoice copy — keep finance jargon out of the therapist UI/PDF."""
from __future__ import annotations


PENDING_TAG = "Pending approval"
STILL_PAID_TAG = "Still paid"
NOT_BILLED_TAG = "Not billed"
DEDUCTED_TAG = "Deducted from pay"

BUCKET_IN_PAY = "in_pay"
BUCKET_PENDING = "pending"
BUCKET_INFO = "info"


def session_completed_label(*, line_type: str | None = None) -> str:
    if line_type == "ADDITIONAL":
        return "Extra session"
    if line_type == "INCLUDED":
        return "Counts toward package"
    return "Session completed"


def child_away_label(*, is_shadow: bool, pending: bool = False) -> str:
    if pending:
        return "Child away — waiting on review"
    if is_shadow:
        return "Child away — still paid"
    return "Session cancelled — not billed"


def leave_label(*, is_shadow: bool, paid: bool, pending: bool = False) -> str:
    if pending:
        return "Leave — waiting on review"
    if not is_shadow:
        return "Session cancelled — not billed"
    if paid:
        return "Paid leave — no deduction"
    return "Unpaid leave — deducted"


def pending_reason_label(*, late: bool) -> str:
    return "Added from invoice" if late else "Waiting for log review"
