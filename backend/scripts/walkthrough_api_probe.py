#!/usr/bin/env python3
"""API walkthrough probe — records actual numbers for findings report."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
MONTH = "2026-08"


def login(email: str) -> str:
    r = httpx.post(f"{BASE}/auth/login", json={"email": email, "password": "demo123"}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def get(path: str, token: str, **params):
    r = httpx.get(f"{BASE}{path}", headers={"Authorization": f"Bearer {token}"}, params=params, timeout=60)
    return r.status_code, r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text


def post(path: str, token: str, body: dict):
    r = httpx.post(f"{BASE}{path}", headers={"Authorization": f"Bearer {token}"}, json=body, timeout=60)
    try:
        data = r.json()
    except Exception:
        data = r.text
    return r.status_code, data


def main() -> int:
    out: dict = {"month": MONTH, "checks": []}

    fin = login("finance@demo.com")
    par = login("parent@demo.com")
    th = login("therapist@demo.com")

    # 1 Finance overview consistency
    sc, brief = get("/admin/finance-overview/monday-brief", fin, billing_month=MONTH)
    sc2, rec = get("/admin/client-billing/receivables", fin, month=MONTH)
    sc3, summary = get("/admin/client-billing/summary", fin, month=MONTH)
    sc4, payments = get("/admin/client-billing/payments", fin, status="PENDING_REVIEW")
    out["checks"].append(
        {
            "surface": "Finance Monday brief vs receivables",
            "brief_money_in": brief.get("moneyIn") if sc == 200 else brief,
            "receivables_totals": rec.get("totals") if sc2 == 200 else rec,
            "summary_outstanding": summary.get("totalOutstandingInr") if sc3 == 200 else summary,
            "pending_claims": len(payments) if isinstance(payments, list) else payments,
        }
    )

    # 2 Master sheet
    sc, sheet = get("/admin/finance-control-tower/billing-readiness-master-sheet", fin, billing_month=MONTH, limit=50)
    wk_rows = [r for r in (sheet.get("items") or []) if (r.get("caseCode") or "").startswith("IC-WK-")]
    out["checks"].append({"surface": "Master sheet WK rows", "count": len(wk_rows), "rows": wk_rows})

    # Spot-check composer vs engine for IC-WK-001
    if wk_rows:
        clean = next((r for r in wk_rows if r.get("caseCode") == "IC-WK-001"), wk_rows[0])
        cid = clean["caseId"]
        scp, preview = get("/admin/client-billing/composer-preview", fin, case_id=cid, billing_month=MONTH)
        out["checks"].append(
            {
                "surface": "Engine vs composer IC-WK-001",
                "master_engine": clean.get("engineAmountInr"),
                "composer_total": preview.get("overview", {}).get("total") if scp == 200 else preview,
                "raised": clean.get("reconciliation", {}).get("raisedInvoiceAmountInr"),
            }
        )

    # 3 Correct-and-reshare flows
    sess_mis = next((r for r in wk_rows if r.get("caseCode") == "IC-WK-002"), None)
    no_ratio = next((r for r in wk_rows if r.get("caseCode") == "IC-WK-006"), None)
    if sess_mis:
        scp, prev = post(
            "/admin/finance-writable/corrections/preview-correct-reshare",
            fin,
            {"case_id": sess_mis["caseId"], "billing_month": MONTH, "wrong_side": "INVOICE_WRONG"},
        )
        out["checks"].append({"surface": "Preview INVOICE_WRONG IC-WK-002", "status": scp, "body": prev})
        if scp == 200 and not prev.get("blocked"):
            sc_c, prop = post(
                "/admin/finance-writable/corrections/correct-reshare",
                fin,
                {
                    "case_id": sess_mis["caseId"],
                    "billing_month": MONTH,
                    "wrong_side": "INVOICE_WRONG",
                    "reason": "Walkthrough: invoice sessions overstated",
                },
            )
            out["checks"].append({"surface": "Propose INVOICE_WRONG", "status": sc_c, "confirm": prop.get("confirmScreen") if isinstance(prop, dict) else prop})
            if sc_c == 200 and isinstance(prop, dict):
                pid = prop.get("id")
                sc_a, approved = post(f"/admin/finance-writable/corrections/{pid}/approve", fin, {})
                out["checks"].append({"surface": "Approve INVOICE_WRONG", "status": sc_a, "result": approved})
    if no_ratio:
        sc_b, blocked = post(
            "/admin/finance-writable/corrections/linked-amount-edit",
            fin,
            {"case_id": no_ratio["caseId"], "billing_month": MONTH, "new_client_amount_inr": 1500, "reason": "should block"},
        )
        out["checks"].append({"surface": "No-ratio block", "status": sc_b, "body": blocked})

    leave_mis = next((r for r in wk_rows if r.get("caseCode") == "IC-WK-003"), None)
    if leave_mis:
        sc_r, rec_prev = post(
            "/admin/finance-writable/corrections/preview-correct-reshare",
            fin,
            {"case_id": leave_mis["caseId"], "billing_month": MONTH, "wrong_side": "RECORD_WRONG"},
        )
        out["checks"].append({"surface": "Preview RECORD_WRONG IC-WK-003", "status": sc_r, "body": rec_prev})

    # 4 Deduction after TDS
    if wk_rows:
        any_row = wk_rows[0]
        sc_d, ded = post(
            "/admin/finance-writable/deductions",
            fin,
            {
                "case_id": any_row["caseId"],
                "billing_month": MONTH,
                "therapist_user_id": any_row.get("therapistId") or 0,
                "amount_inr": 250,
                "direction": "DEDUCT",
                "reason": "Walkthrough deduction",
                "note_type": "DEDUCTION",
            },
        )
        sc_l, ded_list = get("/admin/finance-writable/deductions", fin, case_id=any_row["caseId"], billing_month=MONTH)
        out["checks"].append({"surface": "Deduction + ladder", "create_status": sc_d, "ladder": ded_list.get("payoutLadder") if sc_l == 200 else ded_list})

    # 5 Payment confirm/reject — find pending claim
    sc_p, plist = get("/admin/client-billing/payments", fin, status="PENDING_REVIEW")
    if isinstance(plist, list) and plist:
        pay_id = plist[0]["id"]
        inv_before = plist[0]
        sc_cf, confirmed = post(f"/admin/client-billing/payments/{pay_id}/confirm", fin, {"confirm_amount_inr": inv_before.get("amountInr")})
        out["checks"].append({"surface": "Confirm payment claim", "status": sc_cf, "payment_id": pay_id, "result": confirmed})

    # create another claim to reject
    sc_inv, invs = get("/admin/client-billing/invoices", fin, month=MONTH)
    claim_inv = next((i for i in (invs if isinstance(invs, list) else []) if i.get("invoiceNumber") == "INV-WK-009"), None)
    if claim_inv:
        # reject path needs existing pending - skip if already confirmed
        pass

    # 6 Dispute collectible
    sc_pd, pinv = get(f"/parent/billing/invoices/{claim_inv['id'] if claim_inv else 0}", par) if claim_inv else (0, {})
    dispute_inv = next((r for r in wk_rows if r.get("caseCode") == "IC-WK-005"), None)
    if dispute_inv:
        sc_di, inv_list = get("/admin/client-billing/invoices", fin, month=MONTH, search="INV-WK-005")
        inv5 = next((i for i in (inv_list if isinstance(inv_list, list) else []) if i.get("invoiceNumber") == "INV-WK-005"), None)
        if inv5:
            sc_pid, pdetail = get(f"/parent/billing/invoices/{inv5['id']}", par)
            out["checks"].append(
                {
                    "surface": "Dispute hold IC-WK-005",
                    "total": pdetail.get("totalInr") if sc_pid == 200 else None,
                    "held": pdetail.get("heldAmountInr") if sc_pid == 200 else None,
                    "collectible": pdetail.get("collectibleInr") if sc_pid == 200 else None,
                    "balance": pdetail.get("balanceInr") if sc_pid == 200 else None,
                }
            )

    # 7 Parent payload spot-check
    sc_pdash, pdash = get("/parent/billing/dashboard", par)
    parent_text = json.dumps(pdash).lower()
    out["checks"].append(
        {
            "surface": "Parent dashboard leak check",
            "invoice_count": len(pdash.get("invoices") or []) if sc_pdash == 200 else 0,
            "has_margin_leak": "margin" in parent_text and "estimatedmargin" in parent_text.replace("_", ""),
            "has_payout_leak": "payout" in parent_text or "therapistshare" in parent_text.replace("_", ""),
        }
    )

    # 8 Therapist view
    sc_tq, tqueue = get("/admin/therapist-payouts/queue", fin, month=MONTH)
    sc_tinv, tinvs = get("/invoices", th)
    therapist_text = json.dumps(tinvs).lower() if sc_tinv == 200 else ""
    out["checks"].append(
        {
            "surface": "Therapist invoices leak check",
            "invoice_count": len(tinvs) if isinstance(tinvs, list) else tinvs,
            "has_client_billing_leak": "clientinvoice" in therapist_text or "total_inr" in therapist_text,
            "queue_summary": tqueue if sc_tq == 200 else tqueue,
        }
    )

    Path("/opt/cursor/artifacts/walkthrough_probe.json").write_text(json.dumps(out, indent=2, default=str))
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
