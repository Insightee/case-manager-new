#!/usr/bin/env python3
"""CLI export for HR session-discrepancies report (local DB or READONLY_DATABASE_URL).

Usage (from backend/):
  python scripts/run_session_discrepancy_export.py --date-from 2026-09-26 --date-to 2026-09-30
  python scripts/run_session_discrepancy_export.py --date-from 2026-09-26 --date-to 2026-09-30 --case-statuses ACTIVE --output ../exports/session-discrepancies-2026-09-26_30.xlsx
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.user import User
from app.services.reports_export_helpers import parse_case_status_list
from app.services.reports_export_service import export_payload
from app.services.session_discrepancy_report_service import build_session_discrepancies_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Export session discrepancies HR report.")
    parser.add_argument("--date-from", required=True, help="ISO date start (YYYY-MM-DD)")
    parser.add_argument("--date-to", required=True, help="ISO date end (YYYY-MM-DD)")
    parser.add_argument("--case-statuses", default="ACTIVE", help="Comma-separated case statuses")
    parser.add_argument("--product-module", default=None)
    parser.add_argument("--output", default=None, help="Output .xlsx path")
    args = parser.parse_args()

    statuses = parse_case_status_list(args.case_statuses)
    db = SessionLocal()
    try:
        actor = db.scalars(select(User).where(User.email == "superadmin@demo.com")).first()
        payload = build_session_discrepancies_report(
            db,
            date_from=args.date_from,
            date_to=args.date_to,
            case_statuses=statuses,
            product_module=args.product_module,
            user=actor,
        )
    finally:
        db.close()

    content, _media, stem = export_payload(
        "session-discrepancies",
        payload,
        "xlsx",
        user=actor,
        subtitle=f"Period: {args.date_from} to {args.date_to}",
    )
    out_path = Path(args.output or f"../exports/{stem}.xlsx")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(content)

    sheets = payload.get("sheets") or {}
    print(f"Wrote {out_path}")
    for name, rows in sheets.items():
        print(f"  {name}: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
