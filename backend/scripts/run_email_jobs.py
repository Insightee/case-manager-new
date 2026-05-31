#!/usr/bin/env python3
"""Railway Cron entry for email retry and ZeptoMail log sync.

Usage:
  python scripts/run_email_jobs.py retry-invites
  python scripts/run_email_jobs.py sync-zeptomail
  python scripts/run_email_jobs.py all
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "alembic"))

import app.models  # noqa: F401

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import get_redis

LOCK_KEY = "email_jobs:lock"
LOCK_TTL_SECONDS = 540


def _acquire_lock() -> bool:
    r = get_redis()
    if not r:
        print("[email_jobs] WARNING: Redis unavailable; running without lock")
        return True
    acquired = r.set(LOCK_KEY, "1", nx=True, ex=LOCK_TTL_SECONDS)
    return bool(acquired)


def _release_lock() -> None:
    r = get_redis()
    if r:
        r.delete(LOCK_KEY)


def cmd_retry_invites() -> int:
    from app.services.email.retry_jobs import retry_invite_emails

    db = SessionLocal()
    try:
        stats = retry_invite_emails(db)
        print(f"[email_jobs] retry-invites: {stats}")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def cmd_sync_zeptomail() -> int:
    if not settings.zeptomail_log_sync_enabled:
        print("[email_jobs] sync-zeptomail skipped (ZEPTOMAIL_LOG_SYNC_ENABLED=false)")
        return 0
    from app.services.email.zeptomail_logs import sync_zeptomail_logs

    db = SessionLocal()
    try:
        stats = sync_zeptomail_logs(db)
        db.commit()
        print(f"[email_jobs] sync-zeptomail: {stats}")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def cmd_all() -> int:
    rc = cmd_retry_invites()
    if settings.zeptomail_log_sync_enabled:
        rc = max(rc, cmd_sync_zeptomail())
    return rc


def main() -> int:
    parser = argparse.ArgumentParser(description="Email background jobs (Railway Cron)")
    parser.add_argument(
        "command",
        choices=("retry-invites", "sync-zeptomail", "all"),
        help="Job to run",
    )
    args = parser.parse_args()

    if not _acquire_lock():
        print("[email_jobs] Another run holds the lock; exiting")
        return 0

    try:
        if args.command == "retry-invites":
            return cmd_retry_invites()
        if args.command == "sync-zeptomail":
            return cmd_sync_zeptomail()
        return cmd_all()
    finally:
        _release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
