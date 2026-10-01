#!/usr/bin/env python3
"""Railway Cron: IEP deadline reminders for assigned therapists.

Usage:
  python scripts/iep_reminders.py
  python scripts/iep_reminders.py --dry-run
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
from app.services.iep_reminder_service import send_due_iep_reminders


def main() -> int:
    parser = argparse.ArgumentParser(description="IEP deadline reminders (Railway Cron)")
    parser.add_argument("--dry-run", action="store_true", help="Report matching cases without sending")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        stats = send_due_iep_reminders(db, dry_run=args.dry_run)
        if args.dry_run:
            db.rollback()
            print(f"[iep_reminders] dry-run: {stats}")
            return 0
        db.commit()
        print(f"[iep_reminders] sent {stats.get('sent', 0)} reminder(s): {stats}")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"[iep_reminders] ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
