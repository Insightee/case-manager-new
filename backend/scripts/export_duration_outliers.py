#!/usr/bin/env python3
"""Export session-log duration outliers to Excel (local DB or READONLY_DATABASE_URL).

Usage (from backend/):
  python scripts/export_duration_outliers.py --month 2026-08 --output ../exports/session_duration_outliers_2026-08.xlsx
  READONLY_DATABASE_URL=postgresql://... python scripts/export_duration_outliers.py --date-from 2026-08-01 --date-to 2026-08-31
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.models.user import User
from app.services import session_duration_outlier_export_service as outlier_export
from sqlalchemy import select


def main() -> int:
    parser = argparse.ArgumentParser(description="Export duration outlier session logs to Excel")
    parser.add_argument("--month", help="YYYY-MM")
    parser.add_argument("--date-from", dest="date_from")
    parser.add_argument("--date-to", dest="date_to")
    parser.add_argument("--output", required=True, help="Output .xlsx path")
    parser.add_argument("--admin-email", default="superadmin@demo.com")
    args = parser.parse_args()

    d_from, d_to = outlier_export.resolve_export_date_range(
        date_from=args.date_from,
        date_to=args.date_to,
        month=args.month,
    )

    db_url = os.environ.get("READONLY_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if db_url:
        os.environ["DATABASE_URL"] = db_url

    with SessionLocal() as db:
        user = db.scalars(select(User).where(User.email == args.admin_email).limit(1)).first()
        if not user:
            print(f"Admin user not found: {args.admin_email}", file=sys.stderr)
            return 1
        content, filename = outlier_export.build_duration_outliers_xlsx(
            db,
            user=user,
            date_from=d_from,
            date_to=d_to,
        )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(content)
    print(f"Wrote {out_path} ({filename})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
