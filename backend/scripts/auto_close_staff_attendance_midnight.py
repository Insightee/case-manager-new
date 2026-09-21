#!/usr/bin/env python3
"""Railway Cron: auto-close open staff attendance at midnight IST.

Dashboard setup:
  1. New Railway service → name: staff-attendance-midnight
  2. Root Directory: backend
  3. Settings → Config file: railway.staff-attendance-midnight-cron.toml
  4. Variables: DATABASE_URL=${{Postgres.DATABASE_URL}}
  5. Deploy — cronSchedule runs daily at 18:30 UTC (00:00 IST)

Manual run from backend/:
  python scripts/auto_close_staff_attendance_midnight.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "alembic"))

import app.models  # noqa: F401

from app.core.database import SessionLocal
from app.core.timezone import now_ist
from app.services.staff_attendance_service import auto_close_open_attendance_at_midnight


def main() -> int:
    db = SessionLocal()
    try:
        closed = auto_close_open_attendance_at_midnight(db, now_ist())
        db.commit()
        print(f"[staff_attendance_midnight] closed {len(closed)} record(s): {closed}")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"[staff_attendance_midnight] ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
