#!/usr/bin/env python3
"""Railway Cron: auto-close IN_PROGRESS sessions at 10 PM IST.

Dashboard setup:
  1. New Railway service → name: session-day-end (or session-day-end-cron)
  2. Root Directory: backend
  3. Settings → Config file: railway.session-day-end-cron.toml
  4. Variables: DATABASE_URL=${{Postgres.DATABASE_URL}} (copy from API service)
  5. Deploy — cronSchedule runs daily at 16:30 UTC (22:00 IST)

Manual run from backend/:
  python scripts/auto_close_sessions_day_end.py
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
from app.services.session_day_end_service import auto_close_open_sessions_at_day_end


def main() -> int:
    db = SessionLocal()
    try:
        closed = auto_close_open_sessions_at_day_end(db, now_ist())
        db.commit()
        print(f"[session_day_end] closed {len(closed)} session(s): {closed}")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"[session_day_end] ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
