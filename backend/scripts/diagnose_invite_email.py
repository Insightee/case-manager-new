#!/usr/bin/env python3
"""Read-only invite/email diagnosis for an address (plan: diagnose-nicky).

Usage (from backend/):
  python3 scripts/diagnose_invite_email.py nickylalu@gmail.com
  python3 scripts/diagnose_invite_email.py midhunnoble@gmail.com
"""
from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.email_log import EmailLog
from app.models.user import InviteToken, User
from app.services.email.service import is_smtp_configured


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: diagnose_invite_email.py <email>", file=sys.stderr)
        return 1
    email = sys.argv[1].strip().lower()
    print(f"is_smtp_configured()={is_smtp_configured()}\n")
    db = SessionLocal()
    try:
        user = db.scalars(select(User).where(User.email == email)).first()
        print("users:", "found id=%s roles=%s" % (user.id, user.role_names) if user else "none")

        invites = list(
            db.scalars(
                select(InviteToken)
                .where(InviteToken.email == email)
                .order_by(InviteToken.id.desc())
            ).all()
        )
        if not invites:
            print("invite_tokens: none")
        else:
            print(f"invite_tokens: {len(invites)} row(s)")
            for inv in invites[:5]:
                used = "used" if inv.used_at else "pending"
                print(
                    f"  id={inv.id} role={inv.role_name} {used} "
                    f"expires={inv.expires_at.isoformat()}"
                )

        logs = list(
            db.scalars(
                select(EmailLog)
                .where(EmailLog.recipient_email == email)
                .order_by(EmailLog.created_at.desc())
            ).all()
        )
        if not logs:
            print("email_logs: none (no SMTP traffic recorded for this address)")
        else:
            print(f"email_logs: {len(logs)} row(s)")
            for row in logs[:10]:
                print(
                    f"  id={row.id} event={row.event_type} status={row.status} "
                    f"provider={row.provider} subject={row.subject[:50]!r}"
                )
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
