"""Central gateway for parent notification emails (preferences, suppression, logging, dedupe)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.permissions import RoleName
from app.models.email_log import EmailLog
from app.models.user import User
from app.services.email.events import EmailEvent
from app.services.email.safe_send import check_suppression_only
from app.services.email.service import enqueue_email_event, send_email
from app.services.email.status_helpers import is_submission_success
from app.services.email.templates import render_template
from app.services.parent_notification_preferences import ParentEmailCategory, parent_should_receive_email

_TEMPLATE_DEFAULT_EVENTS: dict[str, EmailEvent] = {
    "session_log_submitted": EmailEvent.SESSION_LOG_SUBMITTED,
    "report_published": EmailEvent.REPORT_APPROVED,
    "invoice_generated": EmailEvent.INVOICE_GENERATED,
    "payment_reminder": EmailEvent.PAYMENT_REMINDER,
    "cm_meeting_invite": EmailEvent.CM_MEETING_INVITE,
    "session_cancelled_today": EmailEvent.PARENT_SAME_DAY_SCHEDULE,
    "session_rescheduled_today": EmailEvent.PARENT_SAME_DAY_SCHEDULE,
    "incident_family_notice": EmailEvent.PARENT_INCIDENT_SHARED,
    "parent_support_escalated": EmailEvent.PARENT_SUPPORT_ESCALATED,
    "support_ticket_reply": EmailEvent.PARENT_SUPPORT_TICKET_REPLY,
    "incident_staff_reply": EmailEvent.PARENT_INCIDENT_STAFF_REPLY,
    "child_absence_confirmed": EmailEvent.PARENT_CHILD_ABSENCE,
    "leave_sessions_cancelled": EmailEvent.LEAVE_APPROVED,
    "cm_meeting_cancelled": EmailEvent.CM_MEETING_CANCELLED,
}


def parent_manage_prefs_url() -> str:
    base = (settings.frontend_url or "http://localhost:5173").rstrip("/")
    return f"{base}/parent/profile#email-preferences"


def _parent_email_dedupe_hit(
    db: Session,
    *,
    recipient: str,
    template_key: str,
    entity_type: str | None,
    entity_id: int | None,
    within_minutes: int | None = None,
) -> bool:
    if not entity_type or entity_id is None:
        return False
    email_l = recipient.lower().strip()
    rows = db.scalars(
        select(EmailLog)
        .where(
            EmailLog.recipient_email == email_l,
            EmailLog.template_key == template_key,
            EmailLog.entity_type == entity_type,
            EmailLog.entity_id == entity_id,
        )
        .order_by(EmailLog.id.desc())
        .limit(10)
    ).all()
    cutoff = None
    if within_minutes is not None and within_minutes > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=within_minutes)
    for row in rows:
        if not is_submission_success(row.status):
            continue
        if cutoff is not None:
            created = row.created_at
            if created is not None and created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created is not None and created < cutoff:
                continue
        return True
    return False


def send_parent_email(
    db: Session,
    parent: User,
    *,
    category: ParentEmailCategory,
    template_key: str,
    payload: dict[str, Any],
    entity_type: str | None = None,
    entity_id: int | None = None,
    event: EmailEvent | None = None,
    background_tasks: BackgroundTasks | None = None,
    subject: str | None = None,
    attachments: list[dict[str, Any]] | None = None,
    force_resend: bool = False,
    dedupe_window_minutes: int | None = None,
) -> int | None:
    """Queue or send one parent email. Returns email_logs.id when queued, 0 when sent sync, None if skipped."""
    if RoleName.PARENT.value not in parent.role_names:
        return None
    if not parent_should_receive_email(parent, category):
        return None
    to_clean = (parent.email or "").strip()
    if not to_clean:
        return None
    if not check_suppression_only(db, to_clean):
        return None
    if not force_resend and _parent_email_dedupe_hit(
        db,
        recipient=to_clean,
        template_key=template_key,
        entity_type=entity_type,
        entity_id=entity_id,
        within_minutes=dedupe_window_minutes,
    ):
        return None

    full_payload = {**payload, "manage_prefs_url": parent_manage_prefs_url()}
    email_event = event or _TEMPLATE_DEFAULT_EVENTS.get(template_key, EmailEvent.SECURITY_ALERT)

    if background_tasks is not None and not attachments:
        return enqueue_email_event(
            background_tasks,
            db,
            event=email_event,
            to=to_clean,
            template_key=template_key,
            payload=full_payload,
            subject=subject,
            recipient_role="parent",
            entity_type=entity_type,
            entity_id=entity_id,
            force_resend=force_resend,
        )

    subj, body_text, body_html = render_template(template_key, full_payload)
    final_subject = subject or subj
    sent = send_email(
        to=to_clean,
        subject=final_subject,
        body_text=body_text,
        body_html=body_html,
        event=email_event,
        db=db,
        attachments=attachments,
    )
    if not sent:
        return None
    from app.models.email_log import EmailLogStatus
    from app.services.email import logging as email_logging

    row = email_logging.create_email_log(
        db,
        event_type=email_event.value,
        recipient_email=to_clean,
        subject=final_subject,
        template_key=template_key,
        payload=full_payload,
        recipient_role="parent",
        provider=settings.email_provider if settings.smtp_host else "noop",
        entity_type=entity_type,
        entity_id=entity_id,
    )
    row.status = EmailLogStatus.ACCEPTED.value
    db.flush()
    return row.id
