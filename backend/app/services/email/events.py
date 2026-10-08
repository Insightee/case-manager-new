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
    CM_MEETING_REMINDER = "cm_meeting_reminder"
    SESSION_LOG_SUBMITTED = "session_log_submitted"
    SESSION_LOG_PUBLISHED = "session_log_published"
    SESSION_LOG_REVIEWED = "session_log_reviewed"
    LEAVE_APPROVED = "leave_approved"
    SECURITY_ALERT = "security_alert"
    TICKET_ESCALATED = "ticket_escalated"
    PARENT_SAME_DAY_SCHEDULE = "parent_same_day_schedule"
    PARENT_INCIDENT_SHARED = "parent_incident_shared"
    PARENT_SUPPORT_ESCALATED = "parent_support_escalated"
    CM_MEETING_CANCELLED = "cm_meeting_cancelled"
