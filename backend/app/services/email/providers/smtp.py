from __future__ import annotations

import logging
import re
import smtplib
import ssl
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


def smtp_connect():
    """Open an authenticated SMTP connection using app settings."""
    host = (settings.smtp_host or "").strip()
    if not host:
        raise ValueError("SMTP_HOST is not set")
    port = int(settings.smtp_port or 587)
    timeout = 30
    if settings.smtp_ssl:
        context = ssl.create_default_context()
        server = smtplib.SMTP_SSL(host, port, timeout=timeout, context=context)
    else:
        server = smtplib.SMTP(host, port, timeout=timeout)
        server.ehlo()
        if settings.smtp_tls:
            context = ssl.create_default_context()
            server.starttls(context=context)
            server.ehlo()
    user = (settings.smtp_user or "").strip()
    password = (settings.smtp_password or "").strip()
    if user and password:
        server.login(user, password)
    elif password:
        server.login("", password)
    return server


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
        client_reference: str | None = None,
    ) -> SendResult:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = from_header
            msg["To"] = ", ".join(to)
            if client_reference:
                msg["X-TM-CLIENT-REF"] = client_reference
            msg.attach(MIMEText(body_text, "plain", "utf-8"))
            if body_html:
                msg.attach(MIMEText(body_html, "html", "utf-8"))

            with smtp_connect() as server:
                server.sendmail(envelope_from, to, msg.as_string())
            return SendResult(ok=True)
        except smtplib.SMTPAuthenticationError as exc:
            logger.error("SMTP authentication failed for user %r: %s", settings.smtp_user, exc)
            return SendResult(
                ok=False,
                error=(
                    "SMTP authentication failed — check SMTP_USER=emailapikey and SMTP_PASSWORD "
                    "(ZeptoMail Send Mail token from Mail Agent → SMTP/API). "
                    f"{exc}"
                )[:2000],
            )
        except smtplib.SMTPRecipientsRefused as exc:
            logger.error("SMTP recipients refused: %s", exc)
            return SendResult(ok=False, error=f"Recipient rejected: {exc}"[:2000])
        except smtplib.SMTPDataError as exc:
            logger.error("SMTP data error (often unverified From): %s", exc)
            return SendResult(
                ok=False,
                error=(
                    f"SMTP rejected message — verify From address {envelope_from!r} is added "
                    f"in ZeptoMail Mail Agent. {exc}"
                )[:2000],
            )
        except Exception as exc:
            logger.exception("SMTP send failed to %s", to)
            return SendResult(ok=False, error=str(exc)[:2000])
