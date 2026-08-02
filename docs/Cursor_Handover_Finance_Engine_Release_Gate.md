# Cursor Handover — Finance Engine Release Gate

**Date:** 2026-08-02  
**Branch:** `feat/billing-engine-steps-1-6`  
**PR:** https://github.com/Insightee/case-manager-new/pull/13 (draft; **do not merge from agent**)  
**Base:** `origin/main` @ `1e85aa2f5a6a39f4f41075710cf59354f351a007`  
**Implementation tip (code + PostgreSQL/safety evidence):** `b5fc27563c4df0c3aa1d15f8937c60c4ac340747`  
**Documentation tip (this gate writeup):**  (docs-only; no behavior change)  
**Latest green remote CI on implementation tip:** `b5fc27563c4df0c3aa1d15f8937c60c4ac340747` (`backend` / `frontend` / `vercel-monorepo-build` / `contributor-guards` SUCCESS)  
**Re-verify after docs tip:** finance **43 passed**; full backend **676 passed**, 17 skipped (local, post-docs)  
**Historical notes:** prior 43-test record `ead0821a…`; CI date-fixture tip `31d012bd…` / fix `19999f25…` superseded  
**Preserve snapshot:** `/Users/midhunnoble/insighte-billing-engine-preserve/20260802-211023/`  
**Billing WIP backup:** branch `backup/billing-engine-wip-20260802`, tag `backup/billing-engine-tree-20260802`  
**Staging alembic prior to this isolation:** `a4b5c6d7e8f9`

---

## Clean branch and scope

Engine was **not** cherry-picked from `billing` tip. It was rebuilt on clean `origin/main` with surgical ports from the preserved Steps 1–6 working tree.

### Migration chain (single Alembic head)

`b1c2d3e4f5a6` (merge all prior main heads) → `y2z3a4b5c6d7` (Step 1 MONTHLY_FIXED + monthly_case_review) → `z3a4b5c6d7e8` (period charges / retainer flags) → `a4b5c6d7e8f9` (Step 6 windows/rates/add-ons) → `c2d3e4f5a6b7` (merge `tp_pending_sub_2606`).

`alembic heads` → **`c2d3e4f5a6b7` only**.

Additive schema only — no ledger amount rewrite migrations.

### Feature flags (defaults at final PR head)

| Flag | Default at PR head | Effect |
|------|--------------------|--------|
| `ENABLE_BILLING` | `false` | 404s finance_ops, client_billing, ledger_billing routers |
| `BILLING_LEDGER_WRITES` | `false` | No-ops session/log ledger upserts |
| `FINANCE_CUTOVER_COMPLETE` | **absent on PR #13** | Not introduced by the engine PR; cutover remains incomplete |
| `VITE_ENABLE_BILLING` | unset/false; prod-forced-off via `readClientModuleFlag` | Frontend billing module |

Test/`APP_ENV=test` allows ledger writes so calculator tests stay green without flipping production defaults.

### Automatic writers gated by `BILLING_LEDGER_WRITES` (all five)

Confirmed gated in `billing_ledger_service.py` via `_ledger_writes_allowed()`:

1. `sync_session_status`
2. `upsert_from_session_event`
3. `upsert_from_daily_log_approved`
4. `ensure_period_charges`
5. `consume_package_session`

### Gaps closed in this branch

- Assignment-date payout attribution → `ASSIGNMENT_GAP` / `ASSIGNMENT_OVERLAP`
- Hard `MISSING_PACKAGE_COUNT` (removed `package_session_count or 1` in step6 + invoice package rate helpers)
- Add-on valuation wired into per-session ledger upsert; `MISSING_ADD_ON_RATE` on missing rate
- `BILLING_LEDGER_WRITES` gate on write entrypoints

---

## Files included (engine PR)

Committed on `feat/billing-engine-steps-1-6` / PR #13 (not a dirty working tree). Representative inventory:

```
CHANGELOG.md
backend/alembic/versions/a4b5c6d7e8f9_step6_windows_rate_addon.py
backend/alembic/versions/b1c2d3e4f5a6_merge_main_heads_for_billing_engine.py
backend/alembic/versions/c2d3e4f5a6b7_merge_billing_engine_tp_pending.py
backend/alembic/versions/y2z3a4b5c6d7_case_monthly_billing_first_class.py
backend/alembic/versions/z3a4b5c6d7e8_period_charges_retainer_flags.py
backend/app/api/v1/daily_logs.py
backend/app/api/v1/ledger_billing.py
backend/app/api/v1/router.py
backend/app/core/billing_validation.py
backend/app/core/config.py
backend/app/core/feature_flags.py
backend/app/models/__init__.py
backend/app/models/billing_step6.py
backend/app/models/case.py
backend/app/models/ledger_billing.py
backend/app/models/session.py
backend/app/schemas/billing.py
backend/app/services/allotment_service.py
backend/app/services/billing_ledger_service.py
backend/app/services/billing_step6_service.py
backend/app/services/invoice_billing_service.py
backend/app/services/session_service.py
backend/app/tests/test_billing_eligibility_step5.py
backend/app/tests/test_billing_engine_release_gate.py
backend/app/tests/test_billing_step6.py
backend/app/tests/test_monthly_billing_rate_guard.py
backend/app/tests/test_period_charge_calculator.py
backend/app/tests/test_case_close.py
backend/app/tests/test_leave_policy.py
backend/app/tests/test_session_absence.py
backend/scripts/staging_step5_eligibility_acceptance.py
backend/scripts/verify_july_2026_therapist_payout.py
docs/Cursor_Handover_Finance_Engine_Release_Gate.md
docs/ENVIRONMENT_VARIABLES.md
docs/Finance_Engine_Dependency_Audit.md
frontend/src/components/admin-portal/AdminCaseAllotmentWizard.jsx
```

## Files / scope deliberately excluded from PR #13

Confirmed absent from PR #13 diff (scope audit):

- Finance Dashboard Stage 1 / Control Tower (PR #14)
- Client invoice workflow expansion
- Therapist statement UI
- Exception resolution workflow UI
- Zoho
- RazorpayX
- Gateway payments
- Production cutover
- July recalculation execution
- Profitability / MIS

Also excluded historically: clinical/voice/insights WIP on `billing`, progress report UI, session voice V2 assets, direct merge of `billing` tip.

---

## Tests

Commands (from `backend/`):

```bash
PYTHONPATH=. APP_ENV=test python -m pytest \
  app/tests/test_billing_engine_release_gate.py \
  app/tests/test_billing_step6.py \
  app/tests/test_billing_eligibility_step5.py \
  app/tests/test_monthly_billing_rate_guard.py \
  app/tests/test_period_charge_calculator.py \
  -k "test_" -q --tb=line
```

**Latest local finance release-gate result:** **43 passed** (re-run after docs tip).

**Latest local full backend suite:** **676 passed**, 17 skipped, 0 failed (re-run after docs tip).

**Remote required checks on implementation tip `b5fc2756…`:** `backend`, `frontend`, `vercel-monorepo-build`, `contributor-guards` → **SUCCESS**. Docs-only tip advances after this writeup; behavior unchanged — confirm remote checks on the docs tip before human merge.

Alembic: single head verified. Fresh empty-SQLite `upgrade head` still hits **pre-existing** main-branch migration friction (`duplicate column name: phone`) unrelated to Steps 1–6. **Do not treat empty-SQLite as PostgreSQL proof** — see PostgreSQL validation below.

---

## Reproduce staging behaviour from clean main?

**Calculator / models / eligibility / Step 6 helpers:** Yes — unit suite green on main-based branch.  
**Staging DB data + prior `x1y2…` parent chain:** Not identical — `y2z3` now parents from `b1c2` merge instead of staging-only `x1y2`. Revision IDs for Steps 1–6 retained so staging that already applied `y2z3…a4b5` does not re-run those upgrades; new envs from main take the merge path.

## Safe additive migrations before cutover?

**Schema yes** if flags stay off — but **only after** `BILLING_LEDGER_WRITES=false` (default) is confirmed in production env. Merging code with writes gated is the intended “code without cutover” posture. Do **not** set writes true or classify `monthly_case_review` as part of merge.

## Remaining cutover prerequisites (post-merge; not this gate)

1. Finance completes `monthly_case_review` classification  
2. Clean `package_session_count` for PACKAGE cases  
3. Explicit production cutover event (flags + optional July regenerate)  
4. Separate Stage 1 read-only dashboard work (PR #14 — not in this PR)

---

## CI repair (2026-08-02) — date-sensitive suite failures

### Root causes (all **pre-existing on `main`**, environment-sensitive)

| Group | Failure | Classification | Fix |
|-------|---------|----------------|-----|
| Session absence (8) | `Child absence cannot be logged for a future date` — fixtures used `_FRESH_SESSION_BASE = 2099-01-01` | stale test fixture vs production validation | Schedule absence tests on `date.today()`; allocate sessions via DB + cancel same-day siblings for isolation |
| Leave policy (1) | Past leave `2026-08-01` blocked after `leave_migration_end_date=2026-07-31` | stale test fixture | Use `date.today() + 14 days` for self-service leave |
| Case close / slot (1) | Full-suite only: `Slot on … is booked for another case` when recurring Mon 10:00 collides | order-dependent state leak | Unique weekday + `06:35` single occurrence ~28 days ahead |

**Not changed:** future-date absence validation, leave migration window, engine calculation services, billing flags.

### Vercel checks

GitHub CI jobs `frontend` + `vercel-monorepo-build` **pass**. Some Vercel project-level preview deployments may still report author access policy blocks for individual Git authors; that is orthogonal to merge readiness of the engine code.

### Files changed for CI repair

- `backend/app/tests/test_session_absence.py`
- `backend/app/tests/test_leave_policy.py`
- `backend/app/tests/test_case_close.py`
- `docs/Cursor_Handover_Finance_Engine_Release_Gate.md`

---

## Final pre-merge gate (PostgreSQL + safety) — 2026-08-02

### Method

1. Disposable PostgreSQL **16.14** databases (`engine_premerge_main`, downgrade clone `engine_premerge_downgrade`).
2. Brought DB to **`origin/main`** tip revision `tp_pending_sub_2606` via main worktree greenfield `create_all` + stamp (empty Postgres path used by `alembic/env.py`; **not** empty-SQLite).
3. Inserted three probe `billing_ledger` money rows (ids `91001`–`91003`).
4. From engine PR head, ran:

```bash
DATABASE_URL='postgresql+psycopg2://insightcase:insightcase@127.0.0.1:5432/engine_premerge_main' \
PYTHONPATH=/workspace/backend:/workspace/backend/alembic \
alembic upgrade c2d3e4f5a6b7
```

### Upgrade result

| Check | Result |
|-------|--------|
| Upgrade completes | **PASS** — applied `b1c2…` → `y2z3…` → `z3a4…` → `a4b5…` → `c2d3…` |
| `alembic heads` | **`c2d3e4f5a6b7` only** |
| DB `alembic_version` | `c2d3e4f5a6b7` |
| App start (`APP_ENV=production`, flags off) | **PASS** — `/health` 200, `db_migration=c2d3e4f5a6b7`; billing routers 404 |
| New artifacts present | `cases.client_monthly_rate_inr`, retainer fields, `sessions.add_on_kind` / `parent_session_id`, tables `monthly_case_review`, `billing_period_flags`, `case_client_rate_periods`, `billing_calc_exceptions`, enum `PENDING_FINANCE` |
| Invoice / payout creation | **none** (`client_invoices=0`, `payouts=0`) |
| Auto billing calculation / session-log ledger writes with `BILLING_LEDGER_WRITES=false` | **none** |

### Before / after financial-row proof (`billing_ledger`)

| Metric | Before upgrade | After upgrade | After gated writer calls |
|--------|----------------|---------------|---------------------------|
| row count | 3 | 3 | 3 |
| sum `amount_inr` | 3520.00 | 3520.00 | 3520.00 |
| sum `total_inr` | 3520.00 | 3520.00 | 3520.00 |
| sum `payout_amount_inr` | 1800.00 | 1800.00 | 1800.00 |
| sum `insighte_margin_inr` | 1720.00 | 1720.00 | 1720.00 |
| money MD5 | `7d3013ac390d4bfe564449f486e21c56` | **identical** | **identical** |

Probe row values unchanged: `91001` 1500/1500/900/600; `91002` 1770/1770/900/870; `91003` 250/250/0/250.

### Safety flag confirmation at final head

```
ENABLE_BILLING=false
BILLING_LEDGER_WRITES=false
FINANCE_CUTOVER_COMPLETE=<not defined on PR #13>
VITE_ENABLE_BILLING=false (default / prod forced off)
```

Production-env proof: all five writers returned no-op (`None` or `{skipped: True, reason: BILLING_LEDGER_WRITES_disabled}`) with money MD5 unchanged.

### Downgrade result (clone DB)

| Step | Result |
|------|--------|
| `alembic downgrade tp_pending_sub_2606` from `c2d3…` | Undoes **merge stamp only** → dual heads `a4b5c6d7e8f9` + `tp_pending_sub_2606`; engine tables still present |
| Then `alembic downgrade b1c2d3e4f5a6` | Removes engine tables/columns (`monthly_case_review`, period flags, rate periods, calc exceptions, retainer/monthly columns, add-on columns) |
| Ledger money after full engine downgrade | **unchanged** MD5 `7d3013ac…` |

### Known migration limitations

1. **Empty-SQLite upgrade friction on main** (`duplicate column name: phone`) is **not** PostgreSQL proof and remains out of scope for this gate.
2. Greenfield empty Postgres uses `create_all` + stamp head (Railway/`env.py` path); this gate additionally exercised the **incremental** path from stamped `tp_pending_sub_2606` → `c2d3e4f5a6b7`.
3. **Postgres enum values are not removed on downgrade:** `MONTHLY_FIXED` on `billingtype` and `PENDING_FINANCE` on `billablestatus` remain after downgrade (documented in migration downgrade comments).
4. **`y2z3…` upgrade can rewrite case billing fields** for AUTO_MIGRATED `MONTHLY_FIXED` product-linked cases into `monthly_case_review` + `client_monthly_rate_inr`. It does **not** rewrite `billing_ledger` amounts. Downgrade restores AUTO_MIGRATED cases from the review table when present.
5. **Downgrade is not a safe undo after real financial cutover** if invoices, payouts, or ledger rows were produced under the new engine/rules. With flags off (merge posture), writers do not create those rows; still treat downgrade after live money movement as **unsafe**.
6. After undoing only the merge revision, Alembic reports **two heads** until the engine branch is also downgraded.

### Exact merge posture

- Merge **PR #13 only** with **all billing/ledger flags left off**.
- Do **not** enable `ENABLE_BILLING` / `BILLING_LEDGER_WRITES`.
- Do **not** perform production cutover or July recalculation.
- Do **not** merge or retarget PR #14 as part of this gate.
- Agent must **not** merge the PR.

---

# Verdict

## ENGINE_PR_APPROVED_TO_MERGE_WITH_FLAGS_OFF

Implementation tip `b5fc27563c4df0c3aa1d15f8937c60c4ac340747` matches green remote CI; post-docs local re-verify finance **43** and full backend **676**; PostgreSQL upgrade to `c2d3e4f5a6b7` succeeded with ledger money checksums unchanged; five automatic writers remain gated; PR scope excludes Stage 1 dashboard and payment cutover work. **Do not merge from this agent.** Human may merge with flags off when ready (after docs-tip CI is green).
)
