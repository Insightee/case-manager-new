#!/usr/bin/env python3
"""Live delivery test through the safe_send gateway (portal_invite path).

Creates an email_logs row, submits via SMTP with X-TM-CLIENT-REF, prints status.

Usage (from backend/):
  python3 scripts/test_safe_send_delivery.py --to you@example.com
  python3 scripts/test_safe_send_delivery.py --to you@example.com --force
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.email_log import EmailLog, EmailLogStatus
from app.services.email.events import EmailEvent
from app.services.email.safe_send import deliver_email_log_smtp, prepare_login_email_log
from app.services.email.service import is_smtp_configured


def main() -> int:
    parser = argparse.ArgumentParser(description="Test safe_send → SMTP delivery")
    parser.add_argument("--to", required=True, help="Recipient inbox to verify delivery")
    parser.add_argument("--force", action="store_true", help="Bypass dedupe/cooldown")
    args = parser.parse_args()

    if not is_smtp_configured():
        print("ERROR: SMTP not configured (SMTP_HOST, SMTP_PASSWORD, SMTP_FROM_EMAIL).", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        prep = prepare_login_email_log(
            db,
            event=EmailEvent.PORTAL_INVITE,
            recipient_email=args.to,
            template_key="portal_invite",
            payload={
                "full_name": "Safe Send Test",
                "invite_url": f"{settings.frontend_url.rstrip('/')}/invite/delivery-test",
                "role_label": "Therapist",
                "intro_line": "This message confirms the post–email-safety gateway path is working.",
            },
            subject="[TEST] Insighte safe_send delivery",
            recipient_role="therapist",
            entity_type=None,
            entity_id=None,
            force_resend=args.force,
        )
        print(f"prepare: ok={prep.ok} skipped={prep.skipped} status={prep.status} log_id={prep.email_log_id}")
        if prep.skipped or not prep.email_log_id:
            if prep.reason:
                print(f"  reason: {prep.reason}")
            db.rollback()
            return 2 if prep.skipped else 1

        log = db.get(EmailLog, prep.email_log_id)
        assert log is not None
        print(f"client_reference: email_log:{log.id}")

        result = deliver_email_log_smtp(db, log)
        db.commit()
        db.refresh(log)

        print(f"deliver: ok={result.ok} status={result.status}")
        print(f"email_logs.id={log.id} status={log.status} attempt_count={log.attempt_count}")
        if log.status == EmailLogStatus.ACCEPTED.value:
            print(f"OK: SMTP accepted message to {args.to}. Check inbox (and ZeptoMail dashboard).")
            return 0
        print(f"FAIL: unexpected status {log.status} error={log.error_message}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
