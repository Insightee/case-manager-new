from __future__ import annotations

from enum import Enum


class EmailEvent(str, Enum):
    PASSWORD_RESET = "password_reset"
    PORTAL_INVITE = "portal_invite"
    REPORT_UPLOADED = "report_uploaded"
    REPORT_APPROVED = "report_approved"
    INVOICE_GENERATED = "invoice_generated"
    PAYMENT_REMINDER = "payment_reminder"
    SESSION_DISPUTED = "session_disputed"
    THERAPIST_ASSIGNED = "therapist_assigned"
    CM_MEETING_INVITE = "cm_meeting_invite"
    SECURITY_ALERT = "security_alert"
