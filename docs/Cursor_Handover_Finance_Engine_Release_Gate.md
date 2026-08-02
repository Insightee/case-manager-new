# Cursor Handover — Finance Engine Release Gate

**Date:** 2026-08-02  
**Branch:** `feat/billing-engine-steps-1-6` (worktree `/Users/midhunnoble/insighte-billing-engine-worktree`)  
**Base:** `origin/main` @ `1e85aa2f5a6a39f4f41075710cf59354f351a007`  
**Engine commit SHA:** `ead0821a760ebae941c129898f1fa64bebc803a2`  
**Working tree parent SHA before engine commits:** `1e85aa2f5a6a39f4f41075710cf59354f351a007`  
**Preserve snapshot:** `/Users/midhunnoble/insighte-billing-engine-preserve/20260802-211023/`  
**Billing WIP backup:** branch `backup/billing-engine-wip-20260802`, tag `backup/billing-engine-tree-20260802`  
**Staging alembic (unchanged by this isolation):** `a4b5c6d7e8f9`

---

## Clean branch and scope

Engine was **not** cherry-picked from `billing` tip. It was rebuilt on clean `origin/main` with surgical ports from the preserved Steps 1–6 working tree.

### Migration chain (single Alembic head)

`b1c2d3e4f5a6` (merge all prior main heads) → `y2z3a4b5c6d7` (Step 1 MONTHLY_FIXED + monthly_case_review) → `z3a4b5c6d7e8` (period charges / retainer flags) → `a4b5c6d7e8f9` (Step 6 windows/rates/add-ons) → `c2d3e4f5a6b7` (merge `tp_pending_sub_2606`).

`alembic heads` → **`c2d3e4f5a6b7` only**.

Additive schema only — no ledger amount rewrite migrations.

### Feature flags (defaults)

| Flag | Default | Effect |
|------|---------|--------|
| `ENABLE_BILLING` | `false` | 404s finance_ops, client_billing, ledger_billing routers |
| `BILLING_LEDGER_WRITES` | `false` | No-ops session/log ledger upserts (`sync_session_status`, approve, period charges, package consume) |
| `VITE_ENABLE_BILLING` | false / prod-forced-off | Frontend billing module |

Test/`APP_ENV=test` allows ledger writes so calculator tests stay green without flipping production defaults.

### Gaps closed in this branch

- Assignment-date payout attribution → `ASSIGNMENT_GAP` / `ASSIGNMENT_OVERLAP`
- Hard `MISSING_PACKAGE_COUNT` (removed `package_session_count or 1` in step6 + invoice package rate helpers)
- Add-on valuation wired into per-session ledger upsert; `MISSING_ADD_ON_RATE` on missing rate
- `BILLING_LEDGER_WRITES` gate on write entrypoints

---

## Files included (engine PR)

Working-tree paths currently dirty on the engine branch (pre-commit inventory):

```
CHANGELOG.md
backend/app/api/v1/daily_logs.py
backend/app/api/v1/ledger_billing.py
backend/app/api/v1/router.py
backend/app/core/billing_validation.py
backend/app/core/config.py
backend/app/models/__init__.py
backend/app/models/case.py
backend/app/models/ledger_billing.py
backend/app/models/session.py
backend/app/schemas/billing.py
backend/app/services/allotment_service.py
backend/app/services/billing_ledger_service.py
backend/app/services/invoice_billing_service.py
backend/app/services/session_service.py
docs/ENVIRONMENT_VARIABLES.md
frontend/src/components/admin-portal/AdminCaseAllotmentWizard.jsx
backend/alembic/versions/a4b5c6d7e8f9_step6_windows_rate_addon.py
backend/alembic/versions/b1c2d3e4f5a6_merge_main_heads_for_billing_engine.py
backend/alembic/versions/c2d3e4f5a6b7_merge_billing_engine_tp_pending.py
backend/alembic/versions/y2z3a4b5c6d7_case_monthly_billing_first_class.py
backend/alembic/versions/z3a4b5c6d7e8_period_charges_retainer_flags.py
backend/app/core/feature_flags.py
backend/app/models/billing_step6.py
backend/app/services/billing_step6_service.py
backend/app/tests/test_billing_eligibility_step5.py
backend/app/tests/test_billing_engine_release_gate.py
backend/app/tests/test_billing_step6.py
backend/app/tests/test_monthly_billing_rate_guard.py
backend/app/tests/test_period_charge_calculator.py
backend/scripts/staging_step5_eligibility_acceptance.py
backend/scripts/verify_july_2026_therapist_payout.py
docs/Finance_Engine_Dependency_Audit.md
```

## Files deliberately excluded

- Clinical/voice/insights WIP on `billing` branch
- Progress report UI/services
- Session voice V2 design assets
- July export xlsx/csv operational dumps (except docs references)
- Direct merge of `billing` tip (84 ahead / 20 behind main)

---

## Tests

Commands (from worktree `backend/`):

```bash
PYTHONPATH=. APP_ENV=test python -m pytest \
  app/tests/test_billing_engine_release_gate.py \
  app/tests/test_billing_step6.py \
  app/tests/test_billing_eligibility_step5.py \
  app/tests/test_monthly_billing_rate_guard.py \
  app/tests/test_period_charge_calculator.py \
  -k "test_" -q --tb=line
```

**Result:** **43 passed** (includes 17 release-gate scenarios).

Alembic: single head verified. Fresh SQLite `upgrade head` still hits **pre-existing** main-branch migration friction (`duplicate column name: phone`) unrelated to Steps 1–6; staging Postgres already runs `a4b5c6d7e8f9`. Production deploy path remains Postgres + Railway start migrate — treat full empty-SQLite upgrade as non-blocking for this gate, but require CI/Postgres migrate check before merge.

---

## Reproduce staging behaviour from clean main?

**Calculator / models / eligibility / Step 6 helpers:** Yes — unit suite green on main-based branch.  
**Staging DB data + prior `x1y2…` parent chain:** Not identical — `y2z3` now parents from `b1c2` merge instead of staging-only `x1y2`. Revision IDs for Steps 1–6 retained so staging that already applied `y2z3…a4b5` does not re-run those upgrades; new envs from main take the merge path.

## Safe additive migrations before cutover?

**Schema yes** if flags stay off — but **only after** `BILLING_LEDGER_WRITES=false` (default) is confirmed in production env. Merging code with writes gated is the intended “code without cutover” posture. Do **not** set writes true or classify `monthly_case_review` as part of merge.

## Remaining cutover prerequisites

1. Finance completes `monthly_case_review` classification  
2. Clean `package_session_count` for PACKAGE cases  
3. Explicit production cutover event (flags + optional July regenerate)  
4. Separate Stage 1 read-only dashboard work (not in this PR)

## PR merge recommendation

Open PR `feat/billing-engine-steps-1-6` → `main` with flags off. **Do not merge `billing` tip.** Do not enable production writes. Do not cut over July money.

---

## CI repair (2026-08-02) — date-sensitive suite failures

### Root causes (all **pre-existing on `main`**, environment-sensitive)

| Group | Failure | Classification | Fix |
|-------|---------|----------------|-----|
| Session absence (8) | `Child absence cannot be logged for a future date` — fixtures used `_FRESH_SESSION_BASE = 2099-01-01` | stale test fixture vs production validation | Schedule absence tests on `date.today()`; allocate sessions via DB + cancel same-day siblings for isolation |
| Leave policy (1) | Past leave `2026-08-01` blocked after `leave_migration_end_date=2026-07-31` | stale test fixture | Use `date.today() + 14 days` for self-service leave |
| Case close / slot (1) | Full-suite only: `Slot on … is booked for another case` when recurring Mon 10:00 collides | order-dependent state leak | Unique weekday + `06:35` single occurrence ~28 days ahead |

**Not changed:** future-date absence validation, leave migration window, engine calculation services, billing flags.

### Main vs engine comparison (same 10 tests, before fix)

| Test | Main | Engine (pre-fix) | Classification |
|------|------|-------------------|----------------|
| 8× session absence | fail | fail | pre-existing / environment-sensitive |
| `test_create_leave_single_request` | fail | fail | pre-existing / environment-sensitive |
| `test_admin_close_cancels_recurring_schedule_record` | pass alone / fail in full suite | same | order-dependent |

### Local verification (post-fix)

| Suite | Result |
|-------|--------|
| Finance engine release-gate (5 files) | **43 passed** |
| Full backend `python3 -m pytest app/tests -q` | **676 passed**, 17 skipped, **0 failed** (~47s) |

Safety defaults in `config.py` unchanged: `ENABLE_BILLING=false`, `BILLING_LEDGER_WRITES=false`. Hard `MISSING_PACKAGE_COUNT` still raises. Assignment-gap / add-on exception paths unchanged.

### Vercel checks

Statuses show **policy/access block**, not a build error:

- Description: `Deployment was blocked` / `Git author midhunnoble must have access to the project on Vercel to create deployments.`
- Projects: `frontend`, `insightecasestaging`, `insightecasetesting`
- GitHub CI jobs `frontend` + `vercel-monorepo-build` **pass** (code builds)

**Manual action required (no code change):** invite `midhunnoble` (or the commit author) to the Vercel team `insightes-projects`, or re-push with an authorized git author. Do not change production env settings for this.

### Files changed for CI repair

- `backend/app/tests/test_session_absence.py`
- `backend/app/tests/test_leave_policy.py`
- `backend/app/tests/test_case_close.py`
- `docs/Cursor_Handover_Finance_Engine_Release_Gate.md`

---

# Verdict

## ENGINE_PR_READY_TO_MARK_NON_DRAFT

Backend suite is green locally after date-fixture repairs; finance 43 still pass; billing flags remain off. **Do not auto-mark non-draft or merge from this agent.** Confirm GitHub `backend` check is green after push, then a human may mark the PR ready. Vercel deployment statuses may remain red until the team access policy is fixed — treat as repo/Vercel ACL, not an engine defect. This document does **not** authorize merge or cutover.
