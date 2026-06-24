#!/usr/bin/env python3
"""Read-only diagnostic: sessions auto-closed before scheduled end (likely mis-mapped category)."""

from __future__ import annotations

import json
import os
import sys
from datetime import timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, selectinload

from app.core.clinical_service_resolver import resolve_clinical_service_category
from app.core.session_rules import duration_minutes_between, scheduled_end_at_utc
from app.core.timezone import ensure_utc_aware
from app.models.case import Case
from app.models.session import Session as TherapySession


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("Set DATABASE_URL to run this diagnostic (read-only).")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def _near_four_hours(minutes: int) -> bool:
    return 235 <= minutes <= 245


def find_premature_auto_closes(db: Session) -> list[dict]:
    rows = db.scalars(
        select(TherapySession)
        .where(
            TherapySession.auto_ended.is_(True),
            TherapySession.actual_start_at.is_not(None),
            TherapySession.actual_end_at.is_not(None),
            TherapySession.auto_end_reason.in_(
                ("slot_duration_limit", "category_duration_limit", "homecare_3h_limit")
            ),
        )
        .options(selectinload(TherapySession.case).selectinload(Case.services))
        .order_by(TherapySession.actual_end_at.desc())
    ).all()

    findings: list[dict] = []
    for session in rows:
        sched_end = scheduled_end_at_utc(session.scheduled_date, session.end_time)
        if sched_end is None:
            continue
        actual_end = ensure_utc_aware(session.actual_end_at)
        if actual_end >= sched_end:
            continue
        started = ensure_utc_aware(session.actual_start_at)
        duration_mins = duration_minutes_between(started, actual_end)
        if not _near_four_hours(duration_mins):
            continue
        case = session.case
        resolved = resolve_clinical_service_category(case, db=db) if case else "unknown"
        findings.append(
            {
                "case_code": getattr(case, "case_code", None),
                "case_id": session.case_id,
                "service_type": getattr(case, "service_type", None),
                "product_module": getattr(case, "product_module", None),
                "resolved_category": resolved,
                "session_id": session.id,
                "scheduled_start": str(session.start_time) if session.start_time else None,
                "scheduled_end": str(session.end_time) if session.end_time else None,
                "scheduled_date": str(session.scheduled_date),
                "actual_start_at": started.isoformat(),
                "actual_end_at": actual_end.isoformat(),
                "duration_minutes": duration_mins,
                "auto_end_reason": session.auto_end_reason,
            }
        )
    return findings


def main() -> int:
    engine = create_engine(_database_url())
    with Session(engine) as db:
        findings = find_premature_auto_closes(db)
    print(json.dumps({"count": len(findings), "sessions": findings}, indent=2))
    if findings:
        print(
            "\nReview product_module / service_type for these cases. "
            "Therapists can correct via Edit Times; reason: "
            "'System auto-closed early due to safety cap; corrected to actual end time.'",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
