"""Transactional email via SMTP. No-op when SMTP is not configured (dev)."""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


def _smtp_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_from)


def send_email(
    *,
    to: str | list[str],
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
) -> bool:
    """Send one email. Returns True if sent or skipped (no config), False on hard failure."""
    recipients = [to] if isinstance(to, str) else list(to)
    recipients = [r.strip() for r in recipients if r and r.strip()]
    if not recipients:
        return False

    if not _smtp_configured():
        logger.info("[email] SMTP not configured; would send to %s: %s", recipients, subject)
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        if body_html:
            msg.attach(MIMEText(body_html, "html", "utf-8"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
            if settings.smtp_tls:
                server.starttls()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_from, recipients, msg.as_string())
        return True
    except Exception:
        logger.exception("Failed to send email to %s", recipients)
        return False


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
    send_email(
        to=to,
        subject=f"Session confirmed — {child_name}",
        body_text=body,
    )


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


def invite_portal_email(
    *,
    to: str,
    invite_url: str,
    therapist_name: str,
    client_name: str,
    slot_when: str,
) -> None:
    body = (
        f"Hi {client_name},\n\n"
        f"{therapist_name} has invited you to join the InsightCase client portal "
        f"for an appointment on {slot_when}.\n\n"
        f"Create your account here:\n{invite_url}\n\n"
        "If you did not expect this, you can ignore this email.\n"
    )
    send_email(to=to, subject="You're invited to InsightCase", body_text=body)


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
    due_line = f"Due date: {due_date_str}.\n" if due_date_str else ""
    overdue_line = "This invoice is now overdue — please pay as soon as you can.\n" if is_overdue else ""
    body = (
        f"Hi {parent_name},\n\n"
        f"A new invoice is ready in your client portal.\n\n"
        f"Invoice: {invoice_number}\n"
        f"For: {child_name}\n"
        f"Amount: ₹{total_inr:,.0f} (balance due: ₹{balance_inr:,.0f})\n"
        f"{due_line}"
        f"{overdue_line}\n"
        f"View details, download a copy, and see payment instructions here:\n{payments_url}\n\n"
        "If you have questions, reply to your case coordinator or raise a dispute from the invoice page.\n"
    )
    subj = f"Invoice {invoice_number} — action needed" if balance_inr > 0 else f"Invoice {invoice_number} — InsightCase"
    send_email(to=to, subject=subj, body_text=body)
