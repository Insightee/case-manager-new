#!/usr/bin/env python3
"""Raise unsubmitted therapist invoices at 11:59 PM IST on the last day of the month.

Manual backfill from backend/:
  python scripts/auto_submit_month_end_invoices.py --month 2026-09
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
from app.core.timezone import now_ist
from app.services.invoice_auto_submit_service import (
    auto_submit_unsubmitted_invoices,
    billing_month_due_at_close,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", help="YYYY-MM. Without this, the job runs only at month-end close.")
    args = parser.parse_args()
    month = (args.month or "").strip() or billing_month_due_at_close(now_ist())
    if not month:
        print("[invoice_month_end] not the last day at 23:59 IST; nothing to submit")
        return 0
    db = SessionLocal()
    try:
        result = auto_submit_unsubmitted_invoices(db, month)
    except Exception as exc:
        db.rollback()
        print(f"[invoice_month_end] ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()
    print(
        f"[invoice_month_end] {result['month']} submitted {len(result['submitted'])} "
        f"skipped {len(result['skipped'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
