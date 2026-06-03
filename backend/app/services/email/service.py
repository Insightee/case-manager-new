from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.email_log import EmailLog, LOGIN_TEMPLATE_KEYS, TRANSACTIONAL_DEDUPE_TEMPLATE_KEYS
from app.services.email import logging as email_logging
from app.services.email.events import EmailEvent
from app.services.email.providers.smtp import SmtpEmailProvider, parse_envelope_from
from app.services.email.safe_send import (
    check_suppression_only,
    deliver_email_log_smtp,
    is_login_template,
    prepare_login_email_log,
)
from app.services.email.senders import from_header_for_event
from app.services.email.templates import render_template

logger = logging.getLogger(__name__)

_smtp_provider = SmtpEmailProvider()


def _transactional_dedupe_hit(
    db: Session,
    *,
    recipient: str,
    template_key: str,
    payload: dict[str, Any],
    entity_type: str | None,
    entity_id: int | None,
) -> bool:
    """Return True if a recent successful send exists for invoice/report-style mail."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select

    from app.services.email.status_helpers import is_submission_success

    if template_key not in TRANSACTIONAL_DEDUPE_TEMPLATE_KEYS:
        return False
    since = datetime.now(timezone.utc) - timedelta(minutes=settings.email_template_dedupe_minutes)
    email_l = recipient.lower().strip()
    rows = list(
        db.scalars(
            select(EmailLog)
            .where(
                EmailLog.recipient_email == email_l,
                EmailLog.template_key == template_key,
                EmailLog.created_at >= since,
            )
            .order_by(EmailLog.id.desc())
            .limit(5)
        ).all()
    )
    if entity_type and entity_id:
        rows = [r for r in rows if r.entity_type == entity_type and r.entity_id == entity_id]
    elif template_key == "invoice_generated" and payload.get("invoice_number"):
        inv_no = str(payload["invoice_number"])
        rows = [r for r in rows if str((r.payload_json or {}).get("invoice_number")) == inv_no]
    elif template_key == "report_published" and payload.get("report_label"):
        label = str(payload["report_label"])
        rows = [r for r in rows if str((r.payload_json or {}).get("report_label")) == label]
    for row in rows:
        if is_submission_success(row.status):
            return True
    return False


def invite_email_delivery_status(*, send_email: bool, background_tasks: BackgroundTasks | None) -> str:
    """UI hint: whether an invite email was queued, skipped, or sent synchronously."""
    if not send_email:
        return "skipped_disabled"
    if not is_smtp_configured():
        return "skipped_no_smtp"
    if background_tasks is not None:
        return "queued"
    return "sent_sync"


def is_smtp_configured() -> bool:
    if not settings.smtp_host:
        return False
    if not settings.smtp_from_header:
        return False
    provider = (settings.email_provider or "smtp").strip().lower()
    if provider in ("zeptomail", "zepto"):
        return bool((settings.smtp_user or "").strip() and (settings.smtp_password or "").strip())
    return True


def send_email(
    *,
    to: str | list[str],
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    event: EmailEvent | None = None,
    from_email: str | None = None,
    db: Session | None = None,
) -> bool:
    """Send one email. Returns True if sent or skipped (no config), False on hard failure."""
    recipients = [to] if isinstance(to, str) else list(to)
    recipients = [r.strip() for r in recipients if r and r.strip()]
    if not recipients:
        return False

    if db is not None:
        recipients = [r for r in recipients if check_suppression_only(db, r)]
        if not recipients:
            logger.info("[email] suppressed; skip send to %s", to)
            return True

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
    entity_type: str | None = None,
    entity_id: int | None = None,
    force_resend: bool = False,
) -> int | None:
    """Queue an email for background delivery. Returns email_logs.id or None if no recipient."""
    to_clean = (to or "").strip()
    if not to_clean:
        return None

    if is_login_template(template_key):
        prep = prepare_login_email_log(
            db,
            event=event,
            recipient_email=to_clean,
            template_key=template_key,
            payload=payload,
            subject=subject,
            recipient_role=recipient_role,
            entity_type=entity_type,
            entity_id=entity_id,
            force_resend=force_resend,
        )
        if prep.skipped or not prep.email_log_id:
            logger.info(
                "[email] login send skipped to=%s status=%s reason=%s",
                to_clean,
                prep.status,
                prep.reason,
            )
            return prep.email_log_id
        background_tasks.add_task(_deliver_email_log, prep.email_log_id)
        return prep.email_log_id

    if not check_suppression_only(db, to_clean):
        logger.info("[email] suppressed skip enqueue to=%s template=%s", to_clean, template_key)
        return None

    if _transactional_dedupe_hit(
        db,
        recipient=to_clean,
        template_key=template_key,
        payload=payload,
        entity_type=entity_type,
        entity_id=entity_id,
    ):
        logger.info("[email] transactional dedupe skip to=%s template=%s", to_clean, template_key)
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
        entity_type=entity_type,
        entity_id=entity_id,
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
    if is_login_template(log.template_key):
        deliver_email_log_smtp(db, log)
        return

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
        email_logging.mark_email_accepted(db, log, provider="noop")
        return

    if not check_suppression_only(db, log.recipient_email):
        email_logging.mark_email_status(
            db,
            log,
            "skipped_suppressed",
            error_message="suppressed",
        )
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
        client_reference=f"email_log:{log.id}",
    )
    if result.ok:
        email_logging.mark_email_accepted(
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
    entity_id: int | None = None,
    force_resend: bool = False,
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
        entity_type="password_reset_token" if entity_id else None,
        entity_id=entity_id,
        force_resend=force_resend,
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


def cm_meeting_invite_email(
    *,
    to: str,
    full_name: str,
    meeting_title: str,
    when: str,
    duration_minutes: int,
    organizer_name: str,
    meeting_url: str | None = None,
    portal_url: str | None = None,
    google_calendar_url: str | None = None,
    calendar_details: str | None = None,
    child_name: str | None = None,
    case_code: str | None = None,
    is_update: bool = False,
) -> None:
    payload = {
        "full_name": full_name,
        "meeting_title": meeting_title,
        "when": when,
        "duration_minutes": duration_minutes,
        "organizer_name": organizer_name,
        "meeting_url": meeting_url or "",
        "portal_url": portal_url or "",
        "google_calendar_url": google_calendar_url or "",
        "calendar_details": calendar_details or "",
        "child_name": child_name,
        "case_code": case_code,
        "is_update": is_update,
    }
    subject, body_text, body_html = render_template("cm_meeting_invite", payload)
    send_email(
        to=to,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        event=EmailEvent.CM_MEETING_INVITE,
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
    invite_id: int | None = None,
    force_resend: bool = False,
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
        entity_type="invite_token" if invite_id else None,
        entity_id=invite_id,
        force_resend=force_resend,
    )


def leave_sessions_cancelled_email(
    *,
    to: str,
    therapist_name: str,
    date_range: str,
    lines: list[str],
    portal_url: str,
    db: Session | None = None,
) -> None:
    detail = "\n".join(f"• {ln}" for ln in lines) if lines else "No individual session lines."
    body = (
        f"Leave for {therapist_name} ({date_range}) is confirmed.\n\n"
        f"The following session(s) were cancelled:\n{detail}\n\n"
        f"{portal_url}\n"
    )
    send_email(to=to, subject="Sessions cancelled — therapist on leave", body_text=body, db=db)


def leave_approved_therapist_email(
    *,
    to: str,
    therapist_name: str,
    date_range: str,
    cancelled_count: int,
    portal_url: str,
    db: Session | None = None,
) -> None:
    body = (
        f"Hi {therapist_name},\n\n"
        f"Your leave from {date_range} has been approved.\n"
        f"{cancelled_count} booked session(s) were cancelled and clients were notified.\n\n"
        f"{portal_url}\n"
    )
    send_email(to=to, subject="Leave approved", body_text=body, db=db)


def leave_admin_summary_email(
    *,
    to: str,
    therapist_name: str,
    date_range: str,
    cancelled_count: int,
    db: Session | None = None,
) -> None:
    body = (
        f"Therapist {therapist_name} — leave {date_range} approved.\n"
        f"Booked sessions cancelled: {cancelled_count}.\n"
    )
    send_email(to=to, subject=f"[Admin] Leave approved — {therapist_name}", body_text=body, db=db)


def leave_pending_hr_email(
    *,
    to: str,
    therapist_name: str,
    date_range: str,
    leave_type: str,
    portal_url: str,
    db: Session | None = None,
) -> None:
    body = (
        f"A new leave request needs your review.\n\n"
        f"Therapist: {therapist_name}\n"
        f"Dates: {date_range}\n"
        f"Type: {leave_type}\n\n"
        f"Review here: {portal_url}\n"
    )
    send_email(to=to, subject=f"Leave request — {therapist_name}", body_text=body, db=db)


def leave_rejected_therapist_email(
    *,
    to: str,
    therapist_name: str,
    date_range: str,
    review_note: str | None,
    portal_url: str,
    db: Session | None = None,
) -> None:
    note_line = f"\nNote from reviewer: {review_note}\n" if review_note else ""
    body = (
        f"Hi {therapist_name},\n\n"
        f"Your leave request for {date_range} was not approved.{note_line}\n"
        f"View details: {portal_url}\n"
    )
    send_email(to=to, subject="Leave request not approved", body_text=body, db=db)


def leave_sessions_reinstated_email(
    *,
    to: str,
    therapist_name: str,
    date_range: str,
    portal_url: str,
    db: Session | None = None,
) -> None:
    body = (
        f"The leave request for {therapist_name} ({date_range}) was withdrawn or not approved.\n"
        f"Your scheduled sessions remain as planned.\n\n{portal_url}\n"
    )
    send_email(to=to, subject="Sessions unchanged", body_text=body, db=db)


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
