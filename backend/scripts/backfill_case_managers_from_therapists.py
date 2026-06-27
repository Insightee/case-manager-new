#!/usr/bin/env python3
"""Align case.case_manager_user_id with each therapist profile primary CM.

Usage (from backend/):
  python scripts/backfill_case_managers_from_therapists.py --dry-run
  python scripts/backfill_case_managers_from_therapists.py --apply
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal  # noqa: E402
from app.services.assignment_service import backfill_case_managers_from_therapist_profiles  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill case CMs from therapist primary CM for assigned sync-eligible cases."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview mismatches without writing")
    group.add_argument("--apply", action="store_true", help="Persist updates")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        outcome = backfill_case_managers_from_therapist_profiles(db, dry_run=not args.apply)
        if args.apply:
            db.commit()
        print(
            f"{'Dry run' if outcome['dry_run'] else 'Applied'}: "
            f"{outcome['cases_updated']} case(s) across {outcome['therapists_touched']} therapist(s)"
        )
        for row in outcome["mismatches"][:50]:
            print(
                f"  {row['case_code']} (case_id={row['case_id']}): "
                f"CM {row['old_case_manager_user_id']} -> {row['new_case_manager_user_id']}"
            )
        if len(outcome["mismatches"]) > 50:
            print(f"  ... and {len(outcome['mismatches']) - 50} more")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
