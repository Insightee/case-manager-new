from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.email_log import EmailLog
from app.services.email import logging as email_logging
from app.services.email.events import EmailEvent
from app.services.email.providers.smtp import SmtpEmailProvider, parse_envelope_from
from app.services.email.senders import from_header_for_event
from app.services.email.templates import render_template

logger = logging.getLogger(__name__)

_smtp_provider = SmtpEmailProvider()


def is_smtp_configured() -> bool:
    if not settings.smtp_host:
        return False
    return bool(settings.smtp_from_header)


def send_email(
    *,
    to: str | list[str],
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    event: EmailEvent | None = None,
    from_email: str | None = None,
) -> bool:
    """Send one email. Returns True if sent or skipped (no config), False on hard failure."""
    recipients = [to] if isinstance(to, str) else list(to)
    recipients = [r.strip() for r in recipients if r and r.strip()]
    if not recipients:
        return False

    if not is_smtp_configured():
        logger.info("[email] SMTP not configured; would send to %s: %s", recipients, subject)
        return True

    if from_email:
        from_header = settings.format_from_header(from_email)
    elif event is not None:
        from_header = from_header_for_event(event)
    else:
        from_header = settings.smtp_from_header
    envelope = parse_envelope_from(from_header)
    result = _smtp_provider.send(
        to=recipients,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        from_header=from_header,
        envelope_from=envelope,
    )
    return result.ok


def enqueue_email_event(
    background_tasks: BackgroundTasks,
    db: Session,
    *,
    event: EmailEvent,
    to: str,
    template_key: str,
    payload: dict[str, Any],
    subject: str | None = None,
    recipient_role: str | None = None,
) -> int | None:
    """Queue an email for background delivery. Returns email_logs.id or None if no recipient."""
    to_clean = (to or "").strip()
    if not to_clean:
        return None

    subj, _, _ = render_template(template_key, payload)
    final_subject = subject or subj
    provider = settings.email_provider if is_smtp_configured() else "noop"

    row = email_logging.create_email_log(
        db,
        event_type=event.value,
        recipient_email=to_clean,
        subject=final_subject,
        template_key=template_key,
        payload=payload,
        recipient_role=recipient_role,
        provider=provider,
    )
    background_tasks.add_task(_deliver_email_log, row.id)
    return row.id


def schedule_email_log_delivery(background_tasks: BackgroundTasks, log_id: int) -> None:
    """Enqueue delivery for an existing log row (e.g. after commit)."""
    background_tasks.add_task(_deliver_email_log, log_id)


def _deliver_email_log(log_id: int) -> None:
    db = SessionLocal()
    try:
        log = db.get(EmailLog, log_id)
        if not log:
            logger.warning("email_logs row %s not found", log_id)
            return
        _deliver_with_session(db, log)
        db.commit()
    except Exception:
        logger.exception("Background email delivery failed for log %s", log_id)
        db.rollback()
    finally:
        db.close()


def _deliver_with_session(db: Session, log: EmailLog) -> None:
    subject, body_text, body_html = render_template(log.template_key, log.payload_json)
    if log.subject:
        subject = log.subject

    if not is_smtp_configured():
        logger.info(
            "[email] noop delivery log_id=%s event=%s to=%s subject=%s",
            log.id,
            log.event_type,
            log.recipient_email,
            subject,
        )
        email_logging.mark_email_sent(db, log, provider="noop")
        return

    try:
        event = EmailEvent(log.event_type)
        from_header = from_header_for_event(event)
    except ValueError:
        from_header = settings.smtp_from_header
    envelope = parse_envelope_from(from_header)
    result = _smtp_provider.send(
        to=[log.recipient_email],
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        from_header=from_header,
        envelope_from=envelope,
    )
    if result.ok:
        email_logging.mark_email_sent(
            db,
            log,
            provider=_smtp_provider.name,
            provider_message_id=result.provider_message_id,
        )
    else:
        email_logging.mark_email_failed(
            db,
            log,
            error_message=result.error or "SMTP send failed",
            provider=_smtp_provider.name,
        )


# --- Legacy plain-text helpers (unchanged behavior for booking/leave/invites) ---


def booking_confirmed_email(
    *,
    to: str,
    child_name: str,
    therapist_name: str,
    when: str,
    portal_url: str,
) -> None:
    body = (
        f"Your session for {child_name} with {therapist_name} is confirmed for {when}.\n\n"
        f"View details in the portal: {portal_url}\n"
    )
    send_email(to=to, subject=f"Session confirmed — {child_name}", body_text=body)


def booking_cancelled_email(
    *,
    to: str,
    child_name: str,
    when: str,
    reason: str,
    portal_url: str,
) -> None:
    body = (
        f"The session for {child_name} on {when} was cancelled.\n"
        f"Reason: {reason}\n\n"
        f"Book a new time: {portal_url}\n"
    )
    send_email(to=to, subject=f"Session cancelled — {child_name}", body_text=body)


def booking_rescheduled_email(
    *,
    to: str,
    child_name: str,
    old_when: str,
    new_when: str,
    portal_url: str,
) -> None:
    body = (
        f"{child_name}'s session was moved from {old_when} to {new_when}.\n\n"
        f"Open the portal: {portal_url}\n"
    )
    send_email(to=to, subject=f"Session rescheduled — {child_name}", body_text=body)


def password_reset_email(
    *,
    to: str,
    full_name: str,
    reset_url: str,
    expires_hours: int = 1,
) -> None:
    payload = {
        "full_name": full_name,
        "reset_url": reset_url,
        "expires_hours": expires_hours,
    }
    subject, body_text, body_html = render_template("password_reset", payload)
    send_email(
        to=to,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        event=EmailEvent.PASSWORD_RESET,
    )


def enqueue_password_reset_email(
    background_tasks: BackgroundTasks,
    db: Session,
    *,
    to: str,
    full_name: str,
    reset_url: str,
    expires_hours: int = 1,
) -> int | None:
    return enqueue_email_event(
        background_tasks,
        db,
        event=EmailEvent.PASSWORD_RESET,
        to=to,
        template_key="password_reset",
        payload={
            "full_name": full_name,
            "reset_url": reset_url,
            "expires_hours": expires_hours,
        },
        recipient_role="user",
    )


def therapist_staff_invite_email(
    *,
    to: str,
    invite_url: str,
    full_name: str,
) -> None:
    _send_portal_invite_sync(
        to=to,
        invite_url=invite_url,
        full_name=full_name,
        role_label="Therapist",
    )


def invite_portal_email(
    *,
    to: str,
    invite_url: str,
    therapist_name: str,
    client_name: str,
    slot_when: str,
) -> None:
    payload = {
        "full_name": client_name,
        "invite_url": invite_url,
        "role_label": "Client",
        "intro_line": (
            f"{therapist_name} has invited you to join the Insighte client portal "
            f"for an appointment on {slot_when}."
        ),
    }
    subject, body_text, body_html = render_template("portal_invite", payload)
    send_email(
        to=to,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        event=EmailEvent.PORTAL_INVITE,
    )


def _send_portal_invite_sync(
    *,
    to: str,
    invite_url: str,
    full_name: str,
    role_label: str,
    intro_line: str | None = None,
) -> None:
    payload = {
        "full_name": full_name,
        "invite_url": invite_url,
        "role_label": role_label,
        "intro_line": intro_line
        or f"You have been invited to join Insighte as a {role_label.lower()}.",
    }
    subject, body_text, body_html = render_template("portal_invite", payload)
    send_email(
        to=to,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        event=EmailEvent.PORTAL_INVITE,
    )


def enqueue_portal_invite_email(
    background_tasks: BackgroundTasks,
    db: Session,
    *,
    to: str,
    invite_url: str,
    full_name: str,
    role_label: str,
    intro_line: str | None = None,
    recipient_role: str | None = None,
) -> int | None:
    return enqueue_email_event(
        background_tasks,
        db,
        event=EmailEvent.PORTAL_INVITE,
        to=to,
        template_key="portal_invite",
        payload={
            "full_name": full_name,
            "invite_url": invite_url,
            "role_label": role_label,
            "intro_line": intro_line
            or f"You have been invited to join Insighte as a {role_label.lower()}.",
        },
        recipient_role=recipient_role,
    )


def leave_sessions_cancelled_email(
    *,
    to: str,
    therapist_name: str,
    date_range: str,
    lines: list[str],
    portal_url: str,
) -> None:
    detail = "\n".join(f"• {ln}" for ln in lines) if lines else "No individual session lines."
    body = (
        f"Leave for {therapist_name} ({date_range}) is confirmed.\n\n"
        f"The following session(s) were cancelled:\n{detail}\n\n"
        f"{portal_url}\n"
    )
    send_email(to=to, subject="Sessions cancelled — therapist on leave", body_text=body)


def leave_approved_therapist_email(
    *,
    to: str,
    therapist_name: str,
    date_range: str,
    cancelled_count: int,
    portal_url: str,
) -> None:
    body = (
        f"Hi {therapist_name},\n\n"
        f"Your leave from {date_range} has been approved.\n"
        f"{cancelled_count} booked session(s) were cancelled and clients were notified.\n\n"
        f"{portal_url}\n"
    )
    send_email(to=to, subject="Leave approved", body_text=body)


def leave_admin_summary_email(
    *,
    to: str,
    therapist_name: str,
    date_range: str,
    cancelled_count: int,
) -> None:
    body = (
        f"Therapist {therapist_name} — leave {date_range} approved.\n"
        f"Booked sessions cancelled: {cancelled_count}.\n"
    )
    send_email(to=to, subject=f"[Admin] Leave approved — {therapist_name}", body_text=body)


def leave_pending_hr_email(
    *,
    to: str,
    therapist_name: str,
    date_range: str,
    leave_type: str,
    portal_url: str,
) -> None:
    body = (
        f"A new leave request needs your review.\n\n"
        f"Therapist: {therapist_name}\n"
        f"Dates: {date_range}\n"
        f"Type: {leave_type}\n\n"
        f"Review here: {portal_url}\n"
    )
    send_email(to=to, subject=f"Leave request — {therapist_name}", body_text=body)


def leave_rejected_therapist_email(
    *,
    to: str,
    therapist_name: str,
    date_range: str,
    review_note: str | None,
    portal_url: str,
) -> None:
    note_line = f"\nNote from reviewer: {review_note}\n" if review_note else ""
    body = (
        f"Hi {therapist_name},\n\n"
        f"Your leave request for {date_range} was not approved.{note_line}\n"
        f"View details: {portal_url}\n"
    )
    send_email(to=to, subject="Leave request not approved", body_text=body)


def leave_sessions_reinstated_email(
    *,
    to: str,
    therapist_name: str,
    date_range: str,
    portal_url: str,
) -> None:
    body = (
        f"The leave request for {therapist_name} ({date_range}) was withdrawn or not approved.\n"
        f"Your scheduled sessions remain as planned.\n\n{portal_url}\n"
    )
    send_email(to=to, subject="Sessions unchanged", body_text=body)


def parent_invoice_ready_email(
    *,
    to: str,
    parent_name: str,
    invoice_number: str,
    child_name: str,
    total_inr: float,
    balance_inr: float,
    due_date_str: str | None,
    is_overdue: bool,
    payments_url: str,
) -> None:
    payload = {
        "parent_name": parent_name,
        "invoice_number": invoice_number,
        "child_name": child_name,
        "total_inr": total_inr,
        "balance_inr": balance_inr,
        "due_date_str": due_date_str,
        "is_overdue": is_overdue,
        "payments_url": payments_url,
    }
    subject, body_text, body_html = render_template("invoice_generated", payload)
    send_email(
        to=to,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        event=EmailEvent.INVOICE_GENERATED,
    )


def enqueue_parent_invoice_email(
    background_tasks: BackgroundTasks,
    db: Session,
    *,
    to: str,
    parent_name: str,
    invoice_number: str,
    child_name: str,
    total_inr: float,
    balance_inr: float,
    due_date_str: str | None,
    is_overdue: bool,
    payments_url: str,
) -> int | None:
    return enqueue_email_event(
        background_tasks,
        db,
        event=EmailEvent.INVOICE_GENERATED,
        to=to,
        template_key="invoice_generated",
        payload={
            "parent_name": parent_name,
            "invoice_number": invoice_number,
            "child_name": child_name,
            "total_inr": total_inr,
            "balance_inr": balance_inr,
            "due_date_str": due_date_str,
            "is_overdue": is_overdue,
            "payments_url": payments_url,
        },
        recipient_role="parent",
    )


def enqueue_report_published_email(
    background_tasks: BackgroundTasks,
    db: Session,
    *,
    to: str,
    parent_name: str,
    child_name: str,
    report_label: str,
    portal_url: str,
) -> int | None:
    return enqueue_email_event(
        background_tasks,
        db,
        event=EmailEvent.REPORT_APPROVED,
        to=to,
        template_key="report_published",
        payload={
            "parent_name": parent_name,
            "child_name": child_name,
            "report_label": report_label,
            "portal_url": portal_url,
        },
        recipient_role="parent",
    )


def send_payment_reminder_email(
    background_tasks: BackgroundTasks,
    db: Session,
    *,
    to: str,
    parent_name: str,
    invoice_number: str,
    balance_inr: float,
    payments_url: str,
) -> int | None:
    """Stub for future billing reminders; queues PAYMENT_REMINDER event."""
    return enqueue_email_event(
        background_tasks,
        db,
        event=EmailEvent.PAYMENT_REMINDER,
        to=to,
        template_key="payment_reminder",
        payload={
            "parent_name": parent_name,
            "invoice_number": invoice_number,
            "balance_inr": balance_inr,
            "payments_url": payments_url,
        },
        recipient_role="parent",
    )
