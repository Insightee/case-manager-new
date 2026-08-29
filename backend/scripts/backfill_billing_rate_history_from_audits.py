#!/usr/bin/env python3
"""Backfill case_billing_rate_changes from historical billing audit events.

Safety defaults:
  - Dry-run unless --apply
  - INSERT only (never mutates cases, invoices, settlements, or Step-6 periods)
  - Idempotent on audit_event_id

Usage (from backend/):
  python scripts/backfill_billing_rate_history_from_audits.py --dry-run
  python scripts/backfill_billing_rate_history_from_audits.py --apply
  python scripts/backfill_billing_rate_history_from_audits.py --dry-run --case-id 42
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal  # noqa: E402
from app.services import billing_rate_history_service  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill billing rate history from audit_events (idempotent INSERT only)."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview rows without writing")
    group.add_argument("--apply", action="store_true", help="Persist new history rows")
    parser.add_argument("--case-id", type=int, default=None, help="Limit to one case")
    parser.add_argument("--limit", type=int, default=None, help="Max audit events to scan")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        outcome = billing_rate_history_service.backfill_rate_history_from_audits(
            db,
            dry_run=not args.apply,
            case_id=args.case_id,
            limit=args.limit,
        )
        if args.apply:
            db.commit()
        print(
            f"{'Dry run' if outcome['dry_run'] else 'Applied'}: "
            f"scanned={outcome['scanned']} "
            f"insert={outcome['inserted_or_would_insert']} "
            f"skipped={outcome['skipped']}"
        )
        for sample in outcome.get("samples") or []:
            print(json.dumps(sample, default=str))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
