# Finance Cutover Sizing — `monthly_case_review` + package gate

**Date:** 2026-08-02  
**Mode:** Read-only fact-finding  
**Verdict:** `CUTOVER_SIZING_BLOCKED_NO_STAGING_DATA`

---

## Founder / finance summary (plain English)

We tried to answer: **how many cases still need a human finance decision before cutover?**

**What we found locally:** the review table exists on probe DBs but contains **zero rows**. Demo/local seed is not a cutover population. Without a staging or production **read-only** database (or a CSV export from ops), we cannot yet say whether this is a dozen-row sheet or a hundreds-row work package.

**What that means for the timeline:** we are still planning blind on volume. The next unblock is one of:

1. Staging/prod read-only `DATABASE_URL`, or  
2. A dump/CSV of `monthly_case_review` + package-missing cases from staging.

Until then: **do not schedule cutover.** Run the SQL pack below against the real DB and paste results back into this doc.

---

## Local empty-state proof (2026-08-02)

| Database | `monthly_case_review` | Rows | PACKAGE missing `package_session_count` |
|---|---|---:|---:|
| `engine_premerge_main` | present | **0** | 0 |
| `finance_merge_verify` | present | **0** | 0 |
| `finance_local_host` | absent (greenfield stamp path) | — | 0 |

Artifact: `/opt/cursor/artifacts/cutover-sizing/local_empty_state_proof.txt`

---

## What the table means (so the numbers make sense)

| Bucket | Meaning | Finance action |
|---|---|---|
| `AUTO_MIGRATED` | Engine already moved the case to monthly; `finance_decision='AUTO'` | None (already done) |
| `NEEDS_REVIEW` | Could not auto-classify; case **not** mutated; `finance_decision` usually null | Human decision required |

Typical `review_reason` values from the migration:

- `Missing product_billing_rule_id`
- `Non-monthly product rule with monthly-looking rate` (rate threshold ₹8000)

**Rate column caveat:** `previous_client_rate_per_session_inr` on `NEEDS_REVIEW` is **rate exposure**, not booked monthly revenue. Sum it as “₹ at stake on the decision,” not “₹ monthly billings.”

Second gate (independent of the review table): active `PACKAGE` cases with `package_session_count` null or ≤ 0 → `MISSING_PACKAGE_COUNT` blocks clean billing.

---

## Query pack (run read-only on staging/prod)

See [`docs/sql/monthly_case_review_cutover_sizing.sql`](./sql/monthly_case_review_cutover_sizing.sql).

Fill in after run:

| Metric | Value |
|---|---|
| Total `monthly_case_review` rows | _TBD_ |
| `AUTO_MIGRATED` | _TBD_ |
| `NEEDS_REVIEW` | _TBD_ |
| `NEEDS_REVIEW` with `finance_decision` null | _TBD_ |
| Top review reasons | _TBD_ |
| Rate exposure min / median / max / sum | _TBD_ |
| Active PACKAGE missing session count | _TBD_ |
| Of those, with sessions in last 60 days | _TBD_ |

### Timeline implication (once numbers land)

| `NEEDS_REVIEW` untouched | Implication |
|---|---|
| ~dozen | Finance clears on a sheet; cutover can be near |
| tens–low hundreds | Dedicated review pass / simple admin queue |
| hundreds+ | Real work-package + review tool; cutover extends |

---

## CSV for finance (when data exists)

Export `NEEDS_REVIEW` rows with: `case_id`, `client_name`, `service_type`, `review_reason`, `previous_client_rate_per_session_inr`, `finance_decision`.

Placeholder path once available: `/opt/cursor/artifacts/cutover-sizing/needs_review_worklist.csv`

---

## Writes / production

**None.** No migration, no row updates, no production mutation from this workstream.
