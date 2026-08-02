# Finance Cutover Sizing — `monthly_case_review` + package gate

**Date:** 2026-08-02  
**Mode:** Read-only fact-finding  
**Verdict:** `CUTOVER_SIZING_BLOCKED_NO_REAL_RO_DB`

---

## Founder / finance summary (plain English)

We tried to answer: **how many cases still need a human finance decision before cutover?**

**Which DB:** This agent only has **local** Postgres (`127.0.0.1` / `finance_local_host` and empty clones). **Not staging. Not production.**

**Read-only check:** The local credential is **writable** (can INSERT/UPDATE/DELETE). Per safety rules we **stopped** rather than treating it as a real RO probe of production data. No migration and no writes were run.

**Situation (a / b / c):** **None of the three apply to a real environment** — we never reached a staging or production database.

| Situation | Meaning | Are we here? |
|---|---|---|
| **(a)** Real migrated `monthly_case_review` rows | Report the real NEEDS_REVIEW count | **No** — no real DB |
| **(b)** Only STEP1-FIX-* fixtures | Real population not here | **No** — no real DB |
| **(c)** Table empty/absent; Step 1 not run | Estimate from case/rate data | **No** — local only; not a real estimate |

**Live count / estimate:** **Unavailable.** Do not use local empty-state (0 review rows / 1–2 cases) as a cutover number.

**One plain sentence:** Finance needs to make roughly **N** case-by-case decisions before cutover — **N unknown until a true read-only staging or production connection (or CSV export) is provided.**

**What that means for the timeline:** still planning blind on volume. Unblock with one of:

1. Inject `READONLY_DATABASE_URL` (true SELECT-only role) pointing at staging or production into this agent, or  
2. Ops runs the SQL packs below and pastes results / CSV back.

Until then: **do not schedule cutover.**

Artifact: `/opt/cursor/artifacts/cutover-sizing/REAL_DB_PROBE_STATUS.md`

---

## Local empty-state proof (2026-08-02)

| Database | `monthly_case_review` | Rows | Cases | Notes |
|---|---|---:|---:|---|
| `finance_local_host` | absent | — | 2 | greenfield; **writable** role |
| `engine_premerge_main` | present | **0** | 1 | clone, not real population |
| `finance_merge_verify` | present | **0** | 1 | clone, not real population |

---

## What the table means (so the numbers make sense)

| Bucket | Meaning | Finance action |
|---|---|---|
| `AUTO_MIGRATED` | Engine already moved the case to monthly; `finance_decision='AUTO'` | None (already done) |
| `NEEDS_REVIEW` | Could not auto-classify; case **not** mutated; `finance_decision` usually null | Human decision required |

Typical `review_reason` values from the migration (`y2z3a4b5c6d7`):

- `Missing product_billing_rule_id` — only when rate **> ₹8000**
- `Non-monthly product rule with monthly-looking rate` — rate **> ₹8000**

**Rate column caveat:** treat rate fields as **rate exposure**, not booked monthly revenue.

Second gate (independent): active `PACKAGE` cases with `package_session_count` null or ≤ 0 → `MISSING_PACKAGE_COUNT`.

---

## Query packs (run read-only on staging/prod)

1. If `monthly_case_review` has **real** rows → [`docs/sql/monthly_case_review_cutover_sizing.sql`](./sql/monthly_case_review_cutover_sizing.sql)  
2. If table empty/absent or fixture-only → [`docs/sql/monthly_case_review_cutover_estimate.sql`](./sql/monthly_case_review_cutover_estimate.sql) (labeled **estimate**, mirrors migration classification without running it)

### Fill in after a real RO run

| Metric | Value |
|---|---|
| DB environment (staging / production) | _TBD_ |
| Situation (a / b / c) | _TBD_ |
| Total `monthly_case_review` rows (real vs fixture) | _TBD_ |
| `AUTO_MIGRATED` / would auto-migrate | _TBD_ |
| `NEEDS_REVIEW` / would need review | _TBD_ |
| `NEEDS_REVIEW` with `finance_decision` null | _TBD_ |
| Top review reasons | _TBD_ |
| Rate exposure min / median / max / sum | _TBD_ |
| Active PACKAGE missing session count | _TBD_ |

### Timeline implication (once numbers land)

| `NEEDS_REVIEW` untouched | Implication |
|---|---|
| ~dozen | Finance clears on a sheet; cutover can be near |
| tens–low hundreds | Dedicated review pass / simple admin queue |
| hundreds+ | Real work-package + review tool; cutover extends |

---

## Writes / production

**None.** No migration, no row updates, no production mutation from this workstream.  
If a provided credential is writable, **stop and flag** — do not proceed against it for sizing.
