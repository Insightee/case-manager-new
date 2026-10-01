#!/usr/bin/env python3
"""Delete a single case and its dependent rows by case_code (maintenance)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from sqlalchemy import text  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.services import case_delete_service  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Delete one case by case_code")
    parser.add_argument("--case-code", required=True)
    parser.add_argument("--confirm", action="store_true", help="Required to execute delete")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        before = case_delete_service.case_snapshot(db, args.case_code)
        if not before:
            print(f"Case not found: {args.case_code}")
            return 1

        child_id = before["child_id"]
        sibling_cases = db.execute(
            text(
                """
                SELECT case_code, status FROM cases
                WHERE child_id = :child_id
                ORDER BY case_code
                """
            ),
            {"child_id": child_id},
        ).mappings().all()
        print("Before:")
        print(f"  Target: {before}")
        print(f"  All cases for child_id={child_id}:")
        for row in sibling_cases:
            print(f"    - {row['case_code']} ({row['status']})")

        if not args.confirm:
            print("Dry run only. Pass --confirm to delete.")
            return 0

        result = case_delete_service.delete_case_by_code(db, args.case_code)
        db.commit()

        remaining = db.execute(
            text(
                """
                SELECT case_code, status FROM cases
                WHERE child_id = :child_id
                ORDER BY case_code
                """
            ),
            {"child_id": child_id},
        ).mappings().all()
        print("After:")
        print(f"  Deleted: {result}")
        print(f"  Remaining cases for child_id={child_id}:")
        for row in remaining:
            print(f"    - {row['case_code']} ({row['status']})")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
