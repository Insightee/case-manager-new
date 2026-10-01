#!/usr/bin/env python3
"""Scope, snapshot, and diff therapist payout preview around segment-end calendar-day clamp.

Usage (from backend/):

  # 1) List rows in scope (segment_end outside billing month)
  python -m scripts.payout_preview_segment_end_diff scope --billing-month 2026-06

  # 2) Snapshot full preview to CSV (run on main before fix, on branch after)
  python -m scripts.payout_preview_segment_end_diff snapshot \\
    --billing-month 2026-06 --output /tmp/payout_2026-06_before.csv

  # 3) Diff two snapshots; fail if any changed row is outside scoped set
  python -m scripts.payout_preview_segment_end_diff diff \\
    --before /tmp/payout_2026-06_before.csv \\
    --after /tmp/payout_2026-06_after.csv \\
    --billing-month 2026-06
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.case import BillingType, Case
from app.models.user import User
from app.services.finance_payout_preview_service import (
    build_cycle_segments,
    month_bounds,
    payout_preview_rows,
    segment_start_day,
    uses_calendar_day_pay,
    _assignment_for_month,
    _assignment_start_for_therapist,
    _employment_start,
    _resolve_segment_end,
    _last_approved_log_for_therapist,
    _therapist_segments_for_case,
)


COMPARE_COLUMNS = (
    "caseId",
    "Case ID",
    "Therapist ID",
    "Calendar Days",
    "Predicted Subtotal",
    "Predicted Total",
    "Client Amount (INR)",
    "Therapist Pay (INR)",
)


def _row_key(row: dict[str, Any]) -> tuple:
    case_id = row.get("caseId")
    try:
        case_id = int(case_id)
    except (TypeError, ValueError):
        pass
    return (case_id, str(row.get("Therapist ID") or ""))


def _scoped_segment_keys(db, ym: str) -> set[tuple]:
    """Therapist×case segments where segment_end falls outside the billing month."""
    month_start, month_end = month_bounds(ym)
    keys: set[tuple] = set()
    cases = db.scalars(
        select(Case).where(Case.product_module.ilike("%shadow%"))
    ).all()
    for case in cases:
        if not uses_calendar_day_pay(case):
            continue
        if case.billing_type != BillingType.PACKAGE:
            continue
        for seg in _therapist_segments_for_case(db, case.id, month_start, month_end):
            assignment = _assignment_for_month(
                db, case.id, seg.therapist_user_id, month_start, month_end
            )
            last_approved_ever = (
                _last_approved_log_for_therapist(db, case.id, seg.therapist_user_id)
                if seg.is_outgoing_replacement
                else None
            )
            segment_end = _resolve_segment_end(
                case=case,
                assignment=assignment,
                is_outgoing_replacement=seg.is_outgoing_replacement,
                last_log=seg.last_log,
                last_approved_ever=last_approved_ever,
                month_start=month_start,
                month_end=month_end,
            )
            if segment_end is None or (month_start <= segment_end <= month_end):
                continue
            therapist = db.get(User, seg.therapist_user_id)
            keys.add((case.id, therapist.employee_id if therapist else seg.therapist_user_id))
    return keys


def cmd_scope(ym: str) -> int:
    month_start, month_end = month_bounds(ym)
    db = SessionLocal()
    try:
        rows_out: list[dict[str, Any]] = []
        cases = db.scalars(select(Case).where(Case.product_module.ilike("%shadow%"))).all()
        for case in cases:
            if not uses_calendar_day_pay(case) or case.billing_type != BillingType.PACKAGE:
                continue
            for seg in _therapist_segments_for_case(db, case.id, month_start, month_end):
                assignment = _assignment_for_month(
                    db, case.id, seg.therapist_user_id, month_start, month_end
                )
                assignment_start = _assignment_start_for_therapist(
                    db,
                    case.id,
                    seg.therapist_user_id,
                    month_start=month_start,
                    month_end=month_end,
                    reference_date=seg.first_log,
                )
                employment_start = _employment_start(db, seg.therapist_user_id)
                seg_start = segment_start_day(
                    assignment_start=assignment_start,
                    employment_start=employment_start,
                    month_start=month_start,
                    month_end=month_end,
                )
                last_approved_ever = (
                    _last_approved_log_for_therapist(db, case.id, seg.therapist_user_id)
                    if seg.is_outgoing_replacement
                    else None
                )
                segment_end = _resolve_segment_end(
                    case=case,
                    assignment=assignment,
                    is_outgoing_replacement=seg.is_outgoing_replacement,
                    last_log=seg.last_log,
                    last_approved_ever=last_approved_ever,
                    month_start=month_start,
                    month_end=month_end,
                )
                if segment_end is None or (month_start <= segment_end <= month_end):
                    continue
                cycle = next(
                    (
                        s
                        for s in build_cycle_segments(db, case, ym)
                        if s.therapist_user_id == seg.therapist_user_id
                    ),
                    None,
                )
                therapist = db.get(User, seg.therapist_user_id)
                rows_out.append(
                    {
                        "caseId": case.id,
                        "Case ID": case.case_code,
                        "Therapist ID": therapist.employee_id if therapist else "",
                        "seg_start_day": seg_start,
                        "segment_end": segment_end.isoformat(),
                        "last_log_in_month": seg.last_log.isoformat() if seg.last_log else "",
                        "calendar_days": cycle.calendar_days if cycle else "",
                        "outgoing": seg.is_outgoing_replacement,
                    }
                )
        print(f"scoped_segments={len(rows_out)} billing_month={ym}")
        for row in sorted(rows_out, key=lambda r: (r["Case ID"], r["Therapist ID"])):
            print(
                f"{row['Case ID']:16} therapist={row['Therapist ID']:6} "
                f"seg_start={row['seg_start_day']:2} segment_end={row['segment_end']} "
                f"last_log={row['last_log_in_month']:10} cal_days={row['calendar_days']} "
                f"outgoing={row['outgoing']}"
            )
        return 0
    finally:
        db.close()


def cmd_snapshot(ym: str, output: Path) -> int:
    db = SessionLocal()
    try:
        rows = payout_preview_rows(db, ym, user=None, product_module=None)
        if not rows:
            print("No preview rows returned.", file=sys.stderr)
            return 1
        fieldnames = list(rows[0].keys())
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"wrote {len(rows)} rows -> {output}")
        return 0
    finally:
        db.close()


def _load_csv(path: Path) -> dict[tuple, dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return {_row_key(row): row for row in reader}


def cmd_diff(before: Path, after: Path, ym: str) -> int:
    db = SessionLocal()
    try:
        scoped = _scoped_segment_keys(db, ym)
    finally:
        db.close()

    before_rows = _load_csv(before)
    after_rows = _load_csv(after)
    all_keys = set(before_rows) | set(after_rows)
    changed: list[tuple] = []
    unexpected: list[tuple] = []

    for key in sorted(all_keys):
        b = before_rows.get(key, {})
        a = after_rows.get(key, {})
        delta = {
            col: (b.get(col), a.get(col))
            for col in COMPARE_COLUMNS
            if b.get(col) != a.get(col)
        }
        if not delta:
            continue
        changed.append(key)
        case_id, therapist_id = key
        scope_key = (case_id, therapist_id)
        if scope_key not in scoped:
            unexpected.append(key)
        print(f"CHANGED caseId={case_id} therapist={therapist_id}: {delta}")

    print(f"\nchanged_rows={len(changed)} scoped_keys={len(scoped)} unexpected={len(unexpected)}")
    if unexpected:
        print("FAIL: changed rows outside scoped segment_end set:", unexpected, file=sys.stderr)
        return 1
    print("PASS: every changed row is in scoped segment_end set.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_scope = sub.add_parser("scope", help="List segments with segment_end outside billing month")
    p_scope.add_argument("--billing-month", required=True)

    p_snap = sub.add_parser("snapshot", help="Export payout preview CSV")
    p_snap.add_argument("--billing-month", required=True)
    p_snap.add_argument("--output", type=Path, required=True)

    p_diff = sub.add_parser("diff", help="Diff before/after snapshots against scoped set")
    p_diff.add_argument("--before", type=Path, required=True)
    p_diff.add_argument("--after", type=Path, required=True)
    p_diff.add_argument("--billing-month", required=True)

    args = parser.parse_args()
    if args.command == "scope":
        return cmd_scope(args.billing_month)
    if args.command == "snapshot":
        return cmd_snapshot(args.billing_month, args.output)
    if args.command == "diff":
        return cmd_diff(args.before, args.after, args.billing_month)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
