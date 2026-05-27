from __future__ import annotations

from app.core.config import settings
from app.services.email.events import EmailEvent

_BILLING_EVENTS = frozenset(
    {
        EmailEvent.INVOICE_GENERATED,
        EmailEvent.PAYMENT_REMINDER,
    }
)
_VERIFICATION_EVENTS = frozenset(
    {
        EmailEvent.PASSWORD_RESET,
        EmailEvent.SECURITY_ALERT,
    }
)


def from_email_for_event(event: EmailEvent | str) -> str:
    if isinstance(event, str):
        try:
            event = EmailEvent(event)
        except ValueError:
            return settings.smtp_from_email
    if event in _VERIFICATION_EVENTS:
        dedicated = (settings.smtp_from_verification_email or "").strip()
        return dedicated or settings.smtp_from_email
    if event in _BILLING_EVENTS:
        dedicated = (settings.smtp_from_billing_email or "").strip()
        return dedicated or settings.smtp_from_email
    return settings.smtp_from_email


def from_header_for_event(event: EmailEvent | str) -> str:
    return settings.format_from_header(from_email_for_event(event))
