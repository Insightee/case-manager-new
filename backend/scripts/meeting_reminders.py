#!/usr/bin/env python3
"""Railway Cron: send case manager meeting reminders around the 1-hour mark.

Usage:
  python scripts/meeting_reminders.py
  python scripts/meeting_reminders.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "alembic"))

import app.models  # noqa: F401

from app.core.database import SessionLocal
from app.core.timezone import now_ist
from app.services.cm_meeting_service import send_due_meeting_reminders


def main() -> int:
    parser = argparse.ArgumentParser(description="Case manager meeting reminders (Railway Cron)")
    parser.add_argument("--dry-run", action="store_true", help="Report matching meetings without sending")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        stats = send_due_meeting_reminders(db, now_ist(), dry_run=args.dry_run)
        if args.dry_run:
            db.rollback()
            print(f"[meeting_reminders] dry-run: {stats}")
            return 0
        db.commit()
        print(f"[meeting_reminders] sent {stats.get('sent', 0)} reminder(s): {stats}")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"[meeting_reminders] ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
