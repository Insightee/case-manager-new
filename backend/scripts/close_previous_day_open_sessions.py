#!/usr/bin/env python3
"""One-time cleanup: close IN_PROGRESS sessions from prior IST days only.

Safe to run after Phase 1A deploy when production has stale open sessions.
Does NOT close same-day live sessions.

From backend/:
  python scripts/close_previous_day_open_sessions.py

Dry-run style: set INSIGHTECASE_DRY_RUN=1 to print candidates without committing.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "alembic"))

import app.models  # noqa: F401

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import SessionLocal
from app.core.timezone import now_ist
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.services.session_day_end_service import close_previous_day_open_sessions
from app.services.session_service import session_ist_calendar_day


def main() -> int:
    dry_run = os.environ.get("INSIGHTECASE_DRY_RUN", "").strip() in ("1", "true", "yes")
    db = SessionLocal()
    try:
        now = now_ist()
        today = now.date()
        if dry_run:
            rows = list(
                db.scalars(
                    select(TherapySession)
                    .where(
                        TherapySession.status == SessionStatus.IN_PROGRESS,
                        TherapySession.actual_start_at.is_not(None),
                    )
                    .options(selectinload(TherapySession.case))
                ).all()
            )
            stale = [s for s in rows if session_ist_calendar_day(s) < today]
            print(f"[previous_day_cleanup] DRY RUN — would close {len(stale)} session(s)")
            for s in stale:
                print(
                    f"  session_id={s.id} therapist={s.therapist_user_id} "
                    f"case_id={s.case_id} day={session_ist_calendar_day(s)}"
                )
            return 0
        closed = close_previous_day_open_sessions(db, now)
        db.commit()
        print(f"[previous_day_cleanup] closed {len(closed)} session(s): {closed}")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"[previous_day_cleanup] ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
