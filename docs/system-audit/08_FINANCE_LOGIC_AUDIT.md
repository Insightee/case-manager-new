# Finance forensic audit

**Highest severity domain.** Silent errors become real money.

Two rails must never be added together as if they were one:

| Rail | Tables | Question it answers |
| --- | --- | --- |
| Money **in** | `client_invoices`, `client_invoice_lines`, `client_payments`, `billing_disputes`, `care_packages`, `billing_ledger` | What the family owes / paid |
| Money **out** | `invoices`, `invoice_case_lines`, `invoice_session_lines`, `invoice_manual_lines`, payout batches/transfers | What we owe the therapist |

Doctrine (`docs/billing-architecture.md`) says ledger is SSOT for client amounts. **Practice:** ledger writes default **off**; therapist pay is a separate live engine.

---

## Money IN — lineage

```text
Service product / product_billing_rules
        ↓ (copied / overridden)
cases.client_rate_*, package_*, billing_type, client_billing_mode, product_billing_rule_id
        ↓ (optional history)
case_billing_rate_changes (as-of)
        ↓
Eligible event: log approve / absence / (intended) ledger upsert
        ↓
care_packages.used_sessions  AND/OR  billing_ledger.amount_inr
        ↓
client_invoices (draft from ledger OR from case defaults)
        ↓
client_payments PENDING_REVIEW → CONFIRMED
        ↓
amount_paid_inr / outstanding
```

| Step | Where the number originates | Flag / caveat |
| --- | --- | --- |
| Catalog default | `product_billing_rules` via `service_products` | Settings → service categories |
| Case commercial | `cases` columns at allotment | CASE-015 |
| As-of rate | `resolve_client_amount_as_of` | Aug 29; else live case |
| Package remaining (parent screen) | `total_sessions - used_sessions` in `client_billing_service.list_packages` | **Not** cycles |
| Package remaining (readiness / rollover) | may use `client_package_cycles` | **Stale** if consume-only path used |
| Ledger event amount | `upsert_from_session_event` | No-op if `billing_ledger_writes=false` |
| Invoice total | `client_invoices.total_inr` snapshot + lines | Can be created **without** ledger |
| Collected | Sum of **confirmed** `client_payments` | Claims do not move balance until confirm |
| Outstanding | total − paid − held dispute lines | Invoice not globally DISPUTED |
| Parent leftover | `parent_billing_statements.amount_inr` (**integer**) | Do not use |

**Prepaid vs postpaid:** `cases.client_billing_mode`. Package therapist billing defaults prepaid at allotment; per-session defaults postpaid (docs + allotment). Consume on **approve log** for prepaid (`daily_logs.py` → `consume_package_session`), and on some child-absent paths.

---

## Money OUT — lineage

```text
cases.therapist_fixed_pay_inr (lump; PERCENTAGE coerced)
        ↓ as-of / assignment.billing_snapshot
resolve_therapist_pay / resolve_therapist_pay_as_of
        ↓
Eligible work: invoice_billing_service month preview
   (session lines + calendar-day branch + leave deduction)
        ↓
submit_invoice_from_preview → stored snapshots
        ↓
recalculate: subtotal, leave_deduction, adjustment, TDS, net_payable
        ↓
finance approve → payout_settlement_service
        ↓
therapist_payout_batches (export flagged) → transfers (release flagged, MOCK)
```

| Step | Origin | Caveat |
| --- | --- | --- |
| Lump pay | `therapist_fixed_pay_inr` preferred; form also writes `pay_share_amount_inr` | PERCENTAGE leftover |
| Per-session unit | lump ÷ `package_session_count` for PACKAGE | Missing package count is an **exception** in step 6 (never guess `or 1`) — good |
| Calendar-day | share/30 × (days − unpaid leave) | Shadow/B2B |
| Leave deduction | `invoice_attendance_service.compute_leave_deduction_inr` | Not HR credit formula |
| Therapist UI exclude | `invoiceUtils.applyLocalExcludes` | **Not stored** until submit |
| TDS | default 10% `finance_default_tds_rate_percent` | Profile override possible |
| Statement dispute | `therapist_statement_disputes` | Flips QUERIED; **not** line math; blocks export |

Older `payouts` table (PENDING/APPROVED/PAID) is leftover vs batches.

---

## Reconcile in vs out

There is **no single function** that proves:

```text
sum(client billable) − sum(therapist payable) = Insighte margin
```

Ledger rows **can** store `payout_amount_inr` and `insighte_margin_inr`, but:

- writes often off  
- therapist invoice may ignore those columns and recompute  

Control Tower compares/flags; it is **not** a closed general ledger. `finance_cutover_complete=false` means do not label RECONCILED.

Low-margin approval (₹5,000) runs at **allotment**, not continuously.

---

## Dashboard number → origin (how to audit a figure)

| Screen number | Trace |
| --- | --- |
| Parent “remaining sessions” | API `remainingSessions` ← `care_packages` |
| Admin packages tab | Same |
| Billing readiness consumed | Cycle `consumed_sessions` **if present**, else `used_sessions` — **can disagree** |
| Therapist invoice preview total | `build_month_preview` / `predicted_subtotal_inr` — live |
| Submitted invoice net | `invoices.net_payable_inr` + stored lines |
| Control Tower KPI | Composed receivables source (changed twice 4–5 Aug) — **provisional** |
| Payout queue | Settlement on submitted invoices, minus deductions |
| Zoho | Not a source of truth |

---

## Flags (production money safety)

| Flag | Default | Meaning |
| --- | --- | --- |
| `enable_billing` | false | Routers 404 |
| `billing_ledger_writes` | false | Ledger silent no-op |
| `billing_ledger_drafts` | true | Can draft from ledger if billing on |
| `finance_cutover_complete` | false | Banner; no reconciled label |
| `payout_export_enabled` | false | Export 403 |
| `payout_release_enabled` | false | Live pay 403 |
| `payout_provider_live` | false | MOCK |
| `zoho_books_live_push` | false | No-op |
| `billing_dispute_legacy_adjustment` | false | Blocks free-field dispute INR |
| Frontend client billing | off on canonical prod | UI |

**CONFIRMED:** code is designed so **merge ≠ silent production money writes**. **STRONG INFERENCE:** if Railway has turned flags on, this safety is gone — verify env before trusting.

---

## Flagged finance risks (severity)

| Risk | Class | Severity |
| --- | --- | --- |
| Dual rails + env flags | J, B | **Critical** |
| Package vs cycle | B, J | **Critical** |
| Invoice without ledger | A, D | **High** |
| Dead financial-effect resolver | C, M | **Critical if wired** |
| FE exclude math | F, J | **High** |
| Payout vs billing rule divergence | A, J | **High** |
| `date.today()` vs IST | Time | **Medium** |
| Retrospective edits after submit | J | **Medium** (snapshots help) |
| Manual payment confirm / no refunds module | J | **Medium** |
| PERCENTAGE leftover rows | C, D | **Medium** |
| parent_billing_statements | C | **Medium** |
| Hardcoded transition pay 500/350 | M | **Medium** |
| Negative margin after rate change | J | **Medium** (allotment gate only) |

Refunds/credits: dispute hold + `adjustment_inr` + finance corrections. **No first-class refund state machine** found.

---

## What Finance can trust today (conditions)

**Yes, with conditions:**

1. A **submitted, approved** therapist invoice and its **stored** lines — for “what we agreed to pay this month.”  
2. A **confirmed** client payment row — for “cash we recorded.”  
3. Case commercial fields + rate-change table — for “what we meant to charge,” if as-of is used.

**Not yet:**

- Control Tower as the books  
- Package cycles for remaining  
- Ledger totals unless writes proven on  
- Any Zoho balance  
- Live therapist preview after local excludes  

---

## Tests (finance)

Strong: `test_invoice_billing.py`, `test_invoice_attendance.py`, `test_ledger_billing.py`, `test_billing_step6.py`, `test_billing_asof_invoice_paths.py`, `test_billing_period_snapshots.py`, `test_client_billing_loop.py`, `test_therapist_payout_settlement.py`, `test_billing_engine_release_gate.py`, `test_finance_consistency.py`, `test_parent_billing.py`.

Missing: consume↔cycle sync; wiring of `resolve_session_financial_effect`; exclusive ledger-only invoice create; golden path session→both rails.
