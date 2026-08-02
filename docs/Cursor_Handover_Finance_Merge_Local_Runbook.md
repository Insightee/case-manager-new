# Finance Merge + Local Test Runbook — Results

**Date:** 2026-08-02  
**Verdict:** `FINANCE_MERGE_LOCAL_RUNBOOK_GREEN`  
**main tip after merges:** `61439bb65cb59e5cf2b8655e790f234176dc7561` (#16); Stage 1 merge `85ca3613…` (#14)

Production was not touched. No report/voice/insights changes rode along.

---

## Step 1 — Diff guard

| Check | Result |
|---|---|
| Engine PR #13 on main | **PASS** — `4eeea857` Merge pull request #13 |
| #14 vs main finance-only | **PASS** — 29 files; billing/finance/docs/Forest Light/flags/tests only |
| #16 vs main (pre-rebase) finance-only | **PASS** — stacked Stage1+Stage2; no reports/voice/insights paths |
| Non-finance path scan | **PASS** |

---

## Step 2 — Merge stack (flags OFF defaults)

| Action | Result |
|---|---|
| Retarget #14 → `main` | **PASS** |
| Merge #14 | **PASS** → `85ca3613` |
| Rebase Stage 2 onto main | **PASS** — Stage 1 files dropped from #16 diff (25 files) |
| Retarget #16 → `main`, mark ready, merge | **PASS** → `61439bb6` |
| Defaults on main | `enable_billing=False`, `billing_ledger_writes=False`, `finance_cutover_complete=False`, Vite client billing / finance dashboard flags default off via `readClientModuleFlag` |

---

## Step 3 — Migration + ledger

| Check | Result |
|---|---|
| `alembic heads` | **`c2d3e4f5a6b7` only** |
| Upgrade on clone of `engine_premerge_main` | No-op at head |
| Probe aggregates | `n=3 amt=3520 tot=3520 pay=1800 mar=1720` (matches release-gate probe rows) |
| Local snap MD5 | `f806860a14bb03be17b79b398143b5d7` unchanged after upgrade + gated writer |
| `ensure_period_charges` flags off | `{skipped: True, reason: BILLING_LEDGER_WRITES_disabled}` |
| Historical string `7d3013ac…` | Probe **values** match release gate; exact prior hash formula not in-repo — used reproducible snap above |

---

## Step 4 — PASS 1 flags OFF

API:

- `/health` 200, `db_migration=c2d3e4f5a6b7`, redis ok  
- Billing + Control Tower routes **404** gated  
- Auth: `/me` 401 unauth / 200 with session  
- Cases list 200  

UI (Playwright token inject): **8/8**

- Parent `/parent/billing` → Coming soon  
- Therapist `/therapist/invoices` → Coming soon  
- Admin cases loads; Control Tower **not** live  
- No `127.0.0.1:7284` / agent-log console errors  

Screenshots: `/opt/cursor/artifacts/finance-runbook/pass1-*.png`

---

## Step 5 — PASS 2 flags ON, writes OFF

Config: `ENABLE_BILLING=true`, `BILLING_LEDGER_WRITES=false`, `FINANCE_CUTOVER_COMPLETE=false`, Vite client billing + finance dashboard **true**, no Zoho key.

API runtime-config: provisional, writes off, zoho false.  
Control Tower summary 200, `pageConfidence=INCOMPLETE`, provisional banner true.  
Composer preview case 1: `canBuild=false`, 1 blocking exception, 1 draft, confidence `INCOMPLETE`.

UI: Stage 1 tower, provisional, no RECONCILED; composer blocked banner, Zoho not configured, confidence, disabled build/post (2), DRAFT panel; parent Forest Light live (`.finance-stage2`), isolation OK, mobile OK; therapist blocked from admin tower.

Ledger verify DB snap **unchanged**. Host `client_invoices` count unchanged (2→2). Host ledger +1 = seeded PENDING_FINANCE probe only (not an invoice build).

Screenshots: `pass2-*.png`

---

## Step 6 — Optional PASS 3 (throwaway DB)

DB `finance_pass3_throwaway` (cloned, then dropped):

- Build-from-ledger → **201** DRAFT `CI-5F94A066`, `zohoSync.status=not_configured`  
- Re-run → **400** no remaining billable rows (no second invoice; count 2→3)  
- Throwaway dropped; production/shared DBs untouched  

---

## Artifacts

- `pass1-results.json`, `pass2-results.json`, `pass3-results.json`  
- `parent-live-debug.json`, `pass2-parent-live.json`  
- Screenshots under `/opt/cursor/artifacts/finance-runbook/`
