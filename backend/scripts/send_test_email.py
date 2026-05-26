#!/usr/bin/env python3
"""Send one test email using app SMTP settings from environment (no secrets in repo).

Usage (from backend/):
  export SMTP_HOST=smtp.zeptomail.com SMTP_USER=emailapikey SMTP_PASSWORD='...'
  export SMTP_FROM_EMAIL=noreply@insighte.in SMTP_FROM_NAME=Insighte
  python3 scripts/send_test_email.py --to you@example.com
"""
from __future__ import annotations

import argparse
import sys

# Allow running as script from backend/
sys.path.insert(0, ".")

from app.services.email.providers.smtp import SmtpEmailProvider, parse_envelope_from
from app.services.email.templates import render_template
from app.core.config import settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a ZeptoMail SMTP test via app config")
    parser.add_argument("--to", required=True, help="Recipient email")
    parser.add_argument(
        "--from-email",
        default=None,
        help="Override sender (default: settings.smtp_from_email)",
    )
    parser.add_argument(
        "--template",
        default="password_reset",
        choices=["password_reset", "portal_invite", "invoice_generated"],
    )
    args = parser.parse_args()

    if not settings.smtp_host or not settings.smtp_password:
        print("ERROR: Set SMTP_HOST and SMTP_PASSWORD in the environment.", file=sys.stderr)
        return 1

    from_email = args.from_email or settings.smtp_from_email
    from_header = settings.format_from_header(from_email)
    envelope = parse_envelope_from(from_header)

    if args.template == "password_reset":
        payload = {
            "full_name": "Test User",
            "reset_url": f"{settings.frontend_url.rstrip('/')}/reset-password/test-token",
            "expires_hours": 1,
        }
    elif args.template == "portal_invite":
        payload = {
            "full_name": "Test User",
            "invite_url": f"{settings.frontend_url.rstrip('/')}/invite/test-token",
            "role_label": "Therapist",
            "intro_line": "This is a ZeptoMail delivery test from Insighte.",
        }
    else:
        payload = {
            "parent_name": "Test",
            "invoice_number": "TEST-001",
            "child_name": "Demo Child",
            "total_inr": 1000,
            "balance_inr": 500,
            "due_date_str": None,
            "is_overdue": False,
            "payments_url": f"{settings.frontend_url.rstrip('/')}/parent/billing",
        }

    subject, body_text, body_html = render_template(args.template, payload)
    provider = SmtpEmailProvider()
    result = provider.send(
        to=[args.to],
        subject=f"[TEST] {subject}",
        body_text=body_text,
        body_html=body_html,
        from_header=from_header,
        envelope_from=envelope,
    )
    if result.ok:
        print(f"OK: sent to {args.to} from {from_header}")
        return 0
    print(f"FAIL: {result.error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
