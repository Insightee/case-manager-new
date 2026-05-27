#!/usr/bin/env python3
"""Verify ZeptoMail SMTP connectivity (no secrets printed).

From backend/ with Railway env or .env loaded:
  python3 scripts/smtp_check.py
  python3 scripts/smtp_check.py --send-to you@example.com
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))

from app.core.config import settings
from app.services.email.events import EmailEvent
from app.services.email.providers.smtp import parse_envelope_from, smtp_connect
from app.services.email.senders import from_email_for_event, from_header_for_event
from app.services.email.service import is_smtp_configured, send_email


def _mask(s: str) -> str:
    if not s:
        return "(empty)"
    if len(s) <= 4:
        return "****"
    return s[:2] + "****" + s[-2:]


def main() -> int:
    parser = argparse.ArgumentParser(description="ZeptoMail SMTP connectivity check")
    parser.add_argument("--send-to", help="Optional recipient for a live send test")
    args = parser.parse_args()

    print("SMTP configuration (masked)")
    print(f"  EMAIL_PROVIDER={settings.email_provider}")
    print(f"  SMTP_HOST={settings.smtp_host}")
    print(f"  SMTP_PORT={settings.smtp_port} TLS={settings.smtp_tls} SSL={settings.smtp_ssl}")
    print(f"  SMTP_USER={settings.smtp_user or '(empty)'}")
    print(f"  SMTP_PASSWORD={_mask(settings.smtp_password)}")
    print(f"  SMTP_FROM_EMAIL={settings.smtp_from_email}")
    print(f"  is_smtp_configured()={is_smtp_configured()}")

    if not is_smtp_configured():
        print("\nERROR: SMTP is not fully configured (host, password, from).", file=sys.stderr)
        return 1

    reset_from = from_email_for_event(EmailEvent.PASSWORD_RESET)
    reset_header = from_header_for_event(EmailEvent.PASSWORD_RESET)
    print(f"\nPassword-reset From: {reset_header} (envelope {parse_envelope_from(reset_header)})")
    if reset_from != settings.smtp_from_email:
        print("  NOTE: using dedicated SMTP_FROM_VERIFICATION_EMAIL")

    try:
        with smtp_connect():
            print("\nOK: SMTP connect + login succeeded")
    except Exception as exc:
        print(f"\nFAIL: SMTP connect/login — {exc}", file=sys.stderr)
        return 1

    if args.send_to:
        ok = send_email(
            to=args.send_to,
            subject="Insighte SMTP test",
            body_text="If you received this, ZeptoMail SMTP is working.",
            event=EmailEvent.PASSWORD_RESET,
        )
        if ok:
            print(f"OK: test email queued/sent to {args.send_to}")
            return 0
        print("FAIL: send_email returned False — check API logs / email_logs table", file=sys.stderr)
        return 1

    print("\nTip: run with --send-to your@email.com to deliver a password-reset-style test message")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
