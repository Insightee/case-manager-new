#!/usr/bin/env python3
"""Backfill structured legacy monthly_reports into clinical_reports (idempotent).

Does NOT migrate uploaded PDFs in case_documents — those stay canonical (Option B).

Usage (from backend/):
  python -m scripts.backfill_legacy_monthly_to_clinical          # dry-run (default)
  python -m scripts.backfill_legacy_monthly_to_clinical --apply
  python -m scripts.backfill_legacy_monthly_to_clinical --apply --include-under-review
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.report import MonthlyReport, ReportCategory, ReportStatus
from app.services.monthly_report_sync_service import sync_legacy_monthly_to_clinical


def _statuses(include_under_review: bool) -> tuple[ReportStatus, ...]:
    base = (ReportStatus.APPROVED, ReportStatus.PUBLISHED)
    if include_under_review:
        return base + (ReportStatus.UNDER_REVIEW,)
    return base


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Execute backfill (default is dry-run)",
    )
    parser.add_argument(
        "--include-under-review",
        action="store_true",
        help="Also sync UNDER_REVIEW legacy rows (admin queue support)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max rows to process (0 = all)",
    )
    args = parser.parse_args()

    db = SessionLocal()
    synced = 0
    skipped = 0
    errors = 0
    try:
        stmt = (
            select(MonthlyReport)
            .where(
                MonthlyReport.category != ReportCategory.PROGRESS.value,
                MonthlyReport.status.in_(_statuses(args.include_under_review)),
            )
            .order_by(MonthlyReport.id.asc())
        )
        if args.limit > 0:
            stmt = stmt.limit(args.limit)
        rows = list(db.scalars(stmt).all())

        for legacy in rows:
            try:
                if args.apply:
                    report = sync_legacy_monthly_to_clinical(db, legacy, reviewer=None)
                    print(f"synced legacy_id={legacy.id} -> clinical_id={report.id} case={legacy.case_id} month={legacy.month}")
                else:
                    print(f"would sync legacy_id={legacy.id} case={legacy.case_id} month={legacy.month} status={legacy.status}")
                synced += 1
            except Exception as exc:
                errors += 1
                print(f"ERROR legacy_id={legacy.id}: {exc}", file=sys.stderr)

        if args.apply:
            db.commit()
            print(f"\napply complete: synced={synced} errors={errors}")
        else:
            db.rollback()
            print(f"\ndry-run: would sync={synced} errors={errors} skipped={skipped}")
    finally:
        db.close()
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
