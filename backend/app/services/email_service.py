"""Backward-compatible shim — prefer `app.services.email`."""
from __future__ import annotations

from app.core.config import settings
from app.services.email.service import (
    booking_cancelled_email,
    booking_confirmed_email,
    booking_rescheduled_email,
    invite_portal_email,
    leave_admin_summary_email,
    leave_approved_therapist_email,
    leave_pending_hr_email,
    leave_rejected_therapist_email,
    leave_sessions_cancelled_email,
    leave_sessions_reinstated_email,
    parent_invoice_ready_email,
    password_reset_email,
    send_email,
    therapist_staff_invite_email,
)

__all__ = [
    "settings",
    "send_email",
    "booking_confirmed_email",
    "booking_cancelled_email",
    "booking_rescheduled_email",
    "password_reset_email",
    "therapist_staff_invite_email",
    "invite_portal_email",
    "leave_sessions_cancelled_email",
    "leave_approved_therapist_email",
    "leave_admin_summary_email",
    "leave_pending_hr_email",
    "leave_rejected_therapist_email",
    "leave_sessions_reinstated_email",
    "parent_invoice_ready_email",
]
