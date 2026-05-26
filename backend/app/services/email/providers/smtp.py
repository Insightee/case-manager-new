from __future__ import annotations

import logging
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parseaddr

from app.core.config import settings
from app.services.email.providers.base import SendResult

logger = logging.getLogger(__name__)

_ADDR_IN_ANGLE = re.compile(r"<([^>]+)>")


def parse_envelope_from(from_header: str) -> str:
    """Extract bare email for SMTP envelope (ZeptoMail requires verified address)."""
    _, addr = parseaddr(from_header)
    if addr:
        return addr
    m = _ADDR_IN_ANGLE.search(from_header)
    if m:
        return m.group(1).strip()
    return from_header.strip()


class SmtpEmailProvider:
    name = "smtp"

    def send(
        self,
        *,
        to: list[str],
        subject: str,
        body_text: str,
        body_html: str | None,
        from_header: str,
        envelope_from: str,
    ) -> SendResult:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = from_header
            msg["To"] = ", ".join(to)
            msg.attach(MIMEText(body_text, "plain", "utf-8"))
            if body_html:
                msg.attach(MIMEText(body_html, "html", "utf-8"))

            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
                if settings.smtp_tls:
                    server.starttls()
                if settings.smtp_user and settings.smtp_password:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.sendmail(envelope_from, to, msg.as_string())
            return SendResult(ok=True)
        except Exception as exc:
            logger.exception("SMTP send failed to %s", to)
            return SendResult(ok=False, error=str(exc)[:2000])
