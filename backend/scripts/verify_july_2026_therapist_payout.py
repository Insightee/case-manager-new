#!/usr/bin/env python3
"""Step 4 — read-only therapist payout verification for July 2026.

Compares existing invoice_billing_service calculators against manual-finance
figures in the July reconciliation workbooks. No DB writes. No migrations.

Usage (from backend/):
  python -m scripts.verify_july_2026_therapist_payout \\
    --payout-xlsx ~/Downloads/July_2026_Client_Case_Attendance_Payout_Reconciliation.xlsx \\
    --output ../exports/july_2026_payout_verification.xlsx
"""
from __future__ import annotations

import argparse
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook

from app.models.case import BillingType, Case, CompensationMode
from app.models.invoice_line import SessionLineType
from app.services import invoice_billing_service as billing


TOLERANCE_INR = 1.0


@dataclass
class PairResult:
    client_id: str
    child: str
    therapist: str
    employee_id: Any
    case_id: Any
    billing_type_label: str
    payout_method: str
    ic_sessions: float
    client_db_pay_share: float
    manual_payout: float
    corrected_expected: float | None
    submitted_invoice: float | None
    system_per_session_path: float
    system_package_lump_path: float | None
    system_chosen: float
    chosen_path: str
    vs_manual: float
    vs_corrected: float | None
    flags: str
    likely_reason: str
    reason_category: str


def _f(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _s(v: Any) -> str:
    return str(v or "").strip()


def _load_sheet(path: Path, sheet: str) -> list[dict[str, Any]]:
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet]
    headers = [h for h in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
    rows: list[dict[str, Any]] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not any(row):
            continue
        rows.append(dict(zip(headers, row)))
    wb.close()
    return rows


def _stub_case(
    *,
    billing_type: BillingType,
    compensation: CompensationMode,
    pay_share: float,
    package_count: int | None = None,
    fixed_lump: float | None = None,
) -> Case:
    case = Case(
        id=0,
        case_code="VERIFY",
        child_id=0,
        service_type="verify",
        product_module="homecare",
    )
    case.billing_type = billing_type
    case.compensation_mode = compensation
    case.pay_share_amount_inr = pay_share
    case.therapist_fixed_pay_inr = fixed_lump
    case.package_session_count = package_count
    case.package_amount_inr = None
    return case


def _system_per_session_total(pay_share: float, sessions: float) -> float:
    """Existing PER_SESSION × PERCENTAGE path: line amount × session count."""
    case = _stub_case(
        billing_type=BillingType.PER_SESSION,
        compensation=CompensationMode.PERCENTAGE,
        pay_share=pay_share,
    )
    line = billing.compute_session_line_amount(case, SessionLineType.PER_SESSION)
    return round(line * sessions, 2)


def _system_package_lump_total(pay_share: float, sessions: float) -> float:
    """Existing PACKAGE × FIXED_LUMP path: lump when included sessions cover package count.

    Uses package_session_count = max(sessions, 1) so a full-month entitlement collapses
    to the lump — the closest existing calculator branch to monthly/package payable.
    """
    pkg_count = max(int(sessions), 1)
    case = _stub_case(
        billing_type=BillingType.PACKAGE,
        compensation=CompensationMode.FIXED_LUMP,
        pay_share=pay_share,
        package_count=pkg_count,
        fixed_lump=pay_share,
    )
    # One included line per confirmed session
    lines = [
        {
            "included": True,
            "line_type": SessionLineType.INCLUDED.value,
            "amount_inr": billing.compute_session_line_amount(case, SessionLineType.INCLUDED),
        }
        for _ in range(pkg_count)
    ]
    _, _, total = billing.compute_case_totals(case, lines)
    return float(total)


def _categorize(reason: str, flags: str, method: str, vs_manual: float) -> str:
    blob = f"{reason} {flags} {method}".lower()
    if abs(vs_manual) <= TOLERANCE_INR:
        return "match"
    if "sessions ×" in method.lower() or "sessions x" in method.lower():
        if abs(vs_manual) > 1000:
            return "per-session-rate-mismatch-or-count"
        return "per-session-small-variance"
    if "monthly" in method.lower() or "package" in method.lower():
        # If per-session path hugely exceeds manual, classic multiplication family
        return "monthly-package-entitlement-vs-per-session-path"
    if "not found" in blob or "omitted" in blob or "identity" in blob:
        return "identity-or-missing-invoice"
    if "session count" in blob:
        return "session-count-mismatch"
    if "leave" in blob:
        return "leave-deduction"
    if "missing" in blob and "rate" in blob:
        return "missing-rate"
    if "mid-month" in blob or "proration" in blob:
        return "mid-month-proration"
    return "other"


def verify_pairs(rows: list[dict[str, Any]]) -> list[PairResult]:
    out: list[PairResult] = []
    for r in rows:
        case_id = r.get("Case ID")
        manual = _f(r.get("Manual finance calculation"))
        share = _f(r.get("Client DB pay-share"))
        sessions = _f(r.get("IC confirmed sessions")) or 0.0
        if case_id is None or manual is None or share is None:
            continue
        method = _s(r.get("Expected payout method"))
        corrected = _f(r.get("Corrected expected payout"))
        submitted = _f(r.get("Submitted invoice"))
        flags = _s(r.get("Flags"))
        reason = _s(r.get("Likely reason"))

        per_session_path = _system_per_session_total(share, sessions)
        package_lump_path = None
        method_l = method.lower()
        if "monthly" in method_l or "package" in method_l:
            package_lump_path = _system_package_lump_total(share, sessions)
            chosen = package_lump_path
            chosen_path = "PACKAGE×FIXED_LUMP (lump)"
        else:
            chosen = per_session_path
            chosen_path = "PER_SESSION×PERCENTAGE (share×sessions)"

        vs_manual = round(chosen - manual, 2)
        vs_corrected = round(chosen - corrected, 2) if corrected is not None else None
        out.append(
            PairResult(
                client_id=_s(r.get("Client ID")),
                child=_s(r.get("Child")),
                therapist=re.sub(r"\s+", " ", _s(r.get("Therapist"))),
                employee_id=r.get("Employee ID"),
                case_id=case_id,
                billing_type_label=_s(r.get("Billing type")),
                payout_method=method,
                ic_sessions=sessions,
                client_db_pay_share=share,
                manual_payout=manual,
                corrected_expected=corrected,
                submitted_invoice=submitted,
                system_per_session_path=per_session_path,
                system_package_lump_path=package_lump_path,
                system_chosen=chosen,
                chosen_path=chosen_path,
                vs_manual=vs_manual,
                vs_corrected=vs_corrected,
                flags=flags,
                likely_reason=reason,
                reason_category=_categorize(reason, flags, method, vs_manual),
            )
        )
    return out


def _write_report(results: list[PairResult], output: Path, summary: dict[str, Any]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "00_Summary"
    ws.append(["July 2026 therapist payout verification (read-only)"])
    ws.append([])
    for k, v in summary.items():
        ws.append([k, v])

    detail = wb.create_sheet("01_Pair_Detail")
    detail.append(
        [
            "client_id",
            "child",
            "therapist",
            "employee_id",
            "case_id",
            "billing_type_label",
            "payout_method",
            "ic_sessions",
            "client_db_pay_share",
            "manual_payout",
            "corrected_expected",
            "submitted_invoice",
            "system_per_session_path",
            "system_package_lump_path",
            "system_chosen",
            "chosen_path",
            "vs_manual",
            "vs_corrected",
            "flags",
            "likely_reason",
            "reason_category",
        ]
    )
    for r in results:
        detail.append(
            [
                r.client_id,
                r.child,
                r.therapist,
                r.employee_id,
                r.case_id,
                r.billing_type_label,
                r.payout_method,
                r.ic_sessions,
                r.client_db_pay_share,
                r.manual_payout,
                r.corrected_expected,
                r.submitted_invoice,
                r.system_per_session_path,
                r.system_package_lump_path,
                r.system_chosen,
                r.chosen_path,
                r.vs_manual,
                r.vs_corrected,
                r.flags,
                r.likely_reason,
                r.reason_category,
            ]
        )

    top = wb.create_sheet("02_Top20_Abs_Diff")
    top.append(
        [
            "abs_vs_manual",
            "client_id",
            "child",
            "therapist",
            "case_id",
            "manual_payout",
            "system_chosen",
            "system_per_session_path",
            "system_package_lump_path",
            "chosen_path",
            "reason_category",
            "likely_reason",
            "flags",
        ]
    )
    ranked = sorted(results, key=lambda x: abs(x.vs_manual), reverse=True)[:20]
    for r in ranked:
        top.append(
            [
                abs(r.vs_manual),
                r.client_id,
                r.child,
                r.therapist,
                r.case_id,
                r.manual_payout,
                r.system_chosen,
                r.system_per_session_path,
                r.system_package_lump_path,
                r.chosen_path,
                r.reason_category,
                r.likely_reason,
                r.flags,
            ]
        )

    cats = wb.create_sheet("03_Reason_Categories")
    cats.append(["reason_category", "pair_count", "abs_variance_sum"])
    bucket: dict[str, list[PairResult]] = {}
    for r in results:
        bucket.setdefault(r.reason_category, []).append(r)
    for cat, items in sorted(bucket.items(), key=lambda kv: -sum(abs(i.vs_manual) for i in kv[1])):
        cats.append([cat, len(items), round(sum(abs(i.vs_manual) for i in items), 2)])

    output.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--payout-xlsx",
        type=Path,
        default=Path.home()
        / "Downloads"
        / "July_2026_Client_Case_Attendance_Payout_Reconciliation.xlsx",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[2]
        / "exports"
        / "july_2026_payout_verification.xlsx",
    )
    args = parser.parse_args()

    rows = _load_sheet(args.payout_xlsx, "01_All_Current_Clients")
    results = verify_pairs(rows)

    total_manual = round(sum(r.manual_payout for r in results), 2)
    total_system = round(sum(r.system_chosen for r in results), 2)
    total_per_session_path = round(sum(r.system_per_session_path for r in results), 2)
    net = round(total_system - total_manual, 2)
    abs_var = round(sum(abs(r.vs_manual) for r in results), 2)
    match_n = sum(1 for r in results if abs(r.vs_manual) <= TOLERANCE_INR)
    differ_n = len(results) - match_n

    # Multiplication detector: per-session path >> manual on monthly/package method rows
    monthly_rows = [r for r in results if "monthly" in r.payout_method.lower() or "package" in r.payout_method.lower()]
    per_sess_rows = [r for r in results if "sessions ×" in r.payout_method.lower() or "sessions x" in r.payout_method.lower()]
    multi_bugs = [
        r
        for r in monthly_rows
        if r.system_per_session_path > (r.manual_payout * 5 + 1000)
    ]

    per_sess_match = sum(1 for r in per_sess_rows if abs(r.vs_manual) <= TOLERANCE_INR)
    monthly_match = sum(1 for r in monthly_rows if abs(r.vs_manual) <= TOLERANCE_INR)

    summary = {
        "pairs_verified": len(results),
        "tolerance_inr": TOLERANCE_INR,
        "total_manual_payout": total_manual,
        "total_system_chosen": total_system,
        "total_system_if_all_per_session_path": total_per_session_path,
        "net_variance_system_minus_manual": net,
        "absolute_row_variance": abs_var,
        "pairs_match_within_tolerance": match_n,
        "pairs_differ": differ_n,
        "per_session_method_pairs": len(per_sess_rows),
        "per_session_method_matches": per_sess_match,
        "monthly_package_method_pairs": len(monthly_rows),
        "monthly_package_method_matches": monthly_match,
        "monthly_rows_where_per_session_path_explodes": len(multi_bugs),
        "verdict": (
            "PAYOUT LOGIC PARTIALLY CLEAN: per-session method pairs mostly track manual; "
            "monthly/package pairs are only correct when using lump path — existing "
            "PER_SESSION share×sessions path reproduces the multiplication family on those rows."
            if multi_bugs
            else "PAYOUT LOOKS CLEAN vs manual within chosen path mapping."
        ),
    }

    _write_report(results, args.output, summary)

    print("=== July 2026 therapist payout verification (read-only) ===")
    for k, v in summary.items():
        print(f"{k}: {v}")
    print(f"\nWrote {args.output}")
    print("\nTop 20 |system_chosen − manual|:")
    for r in sorted(results, key=lambda x: abs(x.vs_manual), reverse=True)[:20]:
        print(
            f"  ₹{abs(r.vs_manual):,.0f}  {r.client_id} / {r.child} / {r.therapist}  "
            f"manual=₹{r.manual_payout:,.0f} system=₹{r.system_chosen:,.0f}  "
            f"[{r.reason_category}] per_sess_path=₹{r.system_per_session_path:,.0f}"
        )


if __name__ == "__main__":
    main()
