#!/usr/bin/env python3
"""Classify outgoing Shadow/B2B calendar-day segments and snapshot money.

ID-only audit (no child/parent/therapist names). Demo May–July 2026 is not a
production merge gate.

Usage (from backend/):
  python -m scripts.outgoing_calendar_day_clamp_audit --month 2026-08
  python -m scripts.outgoing_calendar_day_clamp_audit --month 2026-08 --out ../exports
  python -m scripts.outgoing_calendar_day_clamp_audit --diff before.json after.json --freeze freeze.json
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.database import SessionLocal
from app.services.finance_payout_preview_service import (
    classify_outgoing_calendar_day_segments,
    diff_calendar_day_clamp_snapshots,
    freeze_outgoing_clamp_scope,
    freeze_payout_identities,
    is_demo_calendar_seed_month,
    snapshot_calendar_day_money,
)

AUDIT_FIELDS = (
    "billing_month",
    "is_demo_seed_month",
    "case_id",
    "case_code",
    "therapist_user_id",
    "therapist_id",
    "segment_start",
    "segment_end",
    "in_month_last_log",
    "calendar_days",
    "unclamped_pay_month_day",
    "class",
)


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def run_month(ym: str, out_dir: Path | None) -> dict[str, Any]:
    db = SessionLocal()
    try:
        classified = classify_outgoing_calendar_day_segments(db, ym)
        freeze = freeze_outgoing_clamp_scope(classified)
        snapshot = snapshot_calendar_day_money(db, ym)
    finally:
        db.close()

    report = {
        "billing_month": ym,
        "is_demo_seed_month": is_demo_calendar_seed_month(ym),
        "classified_count": len(classified),
        "frozen_count": len(freeze),
        "frozen": freeze,
        "merge_gate": (
            "dummy_seed_not_a_merge_gate"
            if is_demo_calendar_seed_month(ym)
            else "live_month_requires_finance_signoff"
        ),
    }
    if out_dir is not None:
        _write_csv(out_dir / f"outgoing_clamp_classify_{ym}.csv", classified, AUDIT_FIELDS)
        _write_csv(out_dir / f"outgoing_clamp_freeze_{ym}.csv", freeze, AUDIT_FIELDS)
        _write_json(out_dir / f"outgoing_clamp_freeze_{ym}.json", freeze)
        _write_json(out_dir / f"outgoing_clamp_snapshot_{ym}.json", snapshot)
        payout_fields = (
            "case_id",
            "case_code",
            "therapist_user_id",
            "segment_start",
            "segment_end",
            "calendar_days",
            "approved_sessions",
            "therapist_gross_inr",
            "client_amount_inr",
            "billing_type",
            "uses_calendar_day_pay",
        )
        client_fields = (
            "case_id",
            "case_code",
            "product_module",
            "billing_type",
            "uses_calendar_day_pay",
            "client_gross_inr",
            "calendar_days",
            "approved_sessions",
            "client_rate_per_session_inr",
            "package_amount_inr",
            "client_monthly_rate_inr",
        )
        _write_csv(out_dir / f"outgoing_clamp_payout_{ym}.csv", snapshot["payout_rows"], payout_fields)
        _write_csv(out_dir / f"outgoing_clamp_client_gross_{ym}.csv", snapshot["client_rows"], client_fields)
    return report


def run_diff(before_path: Path, after_path: Path, freeze_path: Path) -> dict[str, Any]:
    before = _load_json(before_path)
    after = _load_json(after_path)
    freeze = _load_json(freeze_path)
    if isinstance(freeze, dict):
        freeze = freeze.get("frozen") or freeze.get("rows") or []
    result = diff_calendar_day_clamp_snapshots(
        before,
        after,
        frozen_identities=freeze_payout_identities(freeze),
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--month", help="Billing month YYYY-MM")
    parser.add_argument("--out", type=Path, help="Directory for CSV/JSON extracts")
    parser.add_argument("--diff", nargs=2, metavar=("BEFORE", "AFTER"), help="Snapshot JSON pair")
    parser.add_argument("--freeze", type=Path, help="Frozen-scope JSON from classify")
    args = parser.parse_args()

    if args.diff:
        if args.freeze is None:
            parser.error("--diff requires --freeze")
        result = run_diff(Path(args.diff[0]), Path(args.diff[1]), args.freeze)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("ok") else 1

    if not args.month:
        parser.error("--month is required unless --diff is set")

    report = run_month(args.month, args.out)
    print(json.dumps(report, indent=2, default=str))
    if report["is_demo_seed_month"]:
        print(
            "NOTE: this month is demo seed. Do not use it as the production merge gate.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
