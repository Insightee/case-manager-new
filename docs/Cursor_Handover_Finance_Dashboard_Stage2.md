# Cursor Handover — Finance Dashboard Stage 2 (Client Billing)

**Verdict:** `STAGE_2_READY_FOR_STAGING`

**Branch:** `cursor/feat-finance-dashboard-stage2-client-billing-0d7e`  
**Stacked on:** `feat/finance-dashboard-stage1` (PR #14 still unmerged to `main` at handoff)  
**Stage 2 tip SHA:** `b5c9bf0f8d9dd73f3f0ce7852c5329e0aff1e1b5` (probe cleanup `0439d352` + feature commit)  
**Scope:** Engine-aware invoice composer + Forest Light parent/composer reskin + Zoho stub seam + flag consolidation. No Finance Engine calc changes. No Stage 1 Control Tower feature changes beyond shared debug-probe cleanup. Staging-only, flag-gated, production-off. **Do not merge, deploy, cut over, or start Stage 3 from this PR alone.**

---

## What shipped

### Step 0 — Cleanup

Removed all `127.0.0.1:7284` / `#region agent log` probes from:

- `frontend/src/lib/apiClient.js`
- `frontend/src/components/invoices/InvoicesPage.jsx`
- `frontend/src/components/admin-portal/AdminTherapistPayoutsPage.jsx`
- `frontend/src/components/admin-portal/AdminInvoicesPage.jsx`

Repo grep shows zero live probe hosts (only negative assertions in Stage 2 tests).

### Step 2 — Flag model (final)

| Layer | Flag / source | Role |
|---|---|---|
| Visibility (parent + therapist) | `VITE_ENABLE_CLIENT_BILLING` with one-release fallback to `VITE_ENABLE_BILLING` | Show UI vs Coming soon; forced **off** on canonical production |
| Liveness | Backend `GET …/runtime-config` → `billingEnabled`, `cutoverComplete`, `provisional` | Live vs provisional confidence |
| Writes | `ledgerWritesEnabled` ∧ billing enabled ∧ `canWriteBilling` | Preview-only vs generate/send/post |
| Zoho | `zohoConfigured` from `ZOHO_BOOKS_API_KEY` | Chip only; never fake success |

Endpoints:

- `GET /api/v1/admin/client-billing/runtime-config` → `{ billingEnabled, ledgerWritesEnabled, cutoverComplete, zohoConfigured, provisional }`
- `GET /api/v1/parent/billing/runtime-config` → `{ cutoverComplete, provisional }` (no write/Zoho secrets)

Frontend: `useBillingRuntimeConfig()` + `isClientBillingVisible()` / `isBillingModuleEnabled()`.

### Step 3 — Engine-aware composer

Backend (`billing_composer_service.get_composer_preview`):

- `blockingExceptions[]` + `canBuild`
- `postableDraftCharges[]` (`PENDING_FINANCE` monthly/package rows; `requiresExplicitPost: true`)
- Overview `confidence` / `confidenceReason` — never `RECONCILED` when `FINANCE_CUTOVER_COMPLETE=false`
- Build-from-ledger and bulk build return **409** when open calc-exceptions exist

UI (`InvoiceComposer` + `InvoiceComposerPreviewPanel`):

- Blocked banner with exception codes + drill links; Build / manual / bulk disabled when `canBuild=false`
- `ConfidenceBadge` on Suggested total
- Explicit **Post charge** → existing ledger post-finance path (never auto-included by build-from-ledger)
- Preserved: queues, search/debounce, service filter, month picker, URL sync, multi-select bulk, include_pending, remind-therapist, preview tabs, refresh, `canWriteBilling`

### Zoho seam

- Adapter: `backend/app/services/zoho_client_sync.py`
- No key → `{ status: "not_configured" }`; dummy key → `{ status: "attempted" }` (stub, no HTTP)
- Invoked on build-from-ledger completion and notify-parent; UI shows “Sync not configured” chip
- Never fakes success; bulk/generate idempotency unchanged

### Steps 4–6 — Forest Light + copy + states

- `frontend/src/styles/finance-stage2.css` — tokens, reduced-motion, `:focus-visible`, composer + parent surfaces
- Parent billing: warm copy (“Your statements”), provisional banner, preserved mobile cards / disputes / offline proof / packages / PDF
- States: loading skeletons, empty queues, writes-disabled banner, provisional, Zoho-not-configured chip, permission gating, partial-failure messaging without blanking the page

---

## Behavior-preservation checklist

### Parent billing (`ParentBillingPage`)

| Behavior | Status |
|---|---|
| Invoice list (desktop table + mobile cards) | Preserved |
| Filters (month / child / service / payment tab) | Preserved |
| Due strip + summary stats | Preserved |
| Invoice detail dialog (scroll-lock, backdrop close) | Preserved |
| Per-line session drill | Preserved |
| Per-line dispute checkboxes + whole-invoice dispute | Preserved |
| Dispute submit (≥10 chars, `line_ids`) | Preserved |
| Payment history | Preserved |
| “I paid offline” FormData proof upload + proof view | Preserved |
| Package balances (table + mobile) | Preserved |
| PDF download | Preserved |
| Disputed-tab navigation | Preserved |
| “Pay online” disabled coming-soon | Preserved |
| No therapist payout / other-client / internal terms | Preserved (+ parent runtime-config omits write/Zoho secrets) |

### Invoice composer

| Behavior | Status |
|---|---|
| All queues, search/debounce, service filter, month picker, URL sync | Preserved |
| Case select (mobile detail + back) | Preserved |
| Multi-select + bulk build | Preserved (also blocked by open exceptions) |
| Build-from-ledger + include_pending | Preserved (blocked by exceptions) |
| Create-manual, remind-therapist | Preserved |
| Preview tabs overview/ledger/therapist/suggested | Preserved |
| Refresh + `canWriteBilling` gating | Preserved (+ runtime writes gate) |

### Therapist invoices

| Behavior | Status |
|---|---|
| Unchanged except probe removal + visibility flag rename/fallback | Preserved |

### Engine / Stage 1

| Surface | Status |
|---|---|
| Finance Calculation Engine | Untouched |
| Stage 1 Control Tower dashboard | Untouched (no feature edits; shared probe cleanup only on billing UI paths) |

---

## Tests + results

| Suite | Command | Result |
|---|---|---|
| Stage 2 backend | `PYTHONPATH=. APP_ENV=test python3 -m pytest app/tests/test_stage2_client_billing.py -q` | **8 passed** |
| Composer regression | `pytest app/tests/test_billing_composer.py -q` | **4 passed, 1 skipped** |
| Stage 2 frontend | `node --test src/lib/financeStage2ClientBilling.test.js` | **6 passed** |
| Probe grep | `rg '127.0.0.1:7284\|#region agent log'` | Clean (assertions only) |

Covered: runtime-config coherence, Zoho not_configured/attempted, blocking `canBuild=false`, build 409, explicit DRAFT/`PENDING_FINANCE` post list, parent isolation of payout fields, flag rename+fallback, ConfidenceBadge/guardrails/Forest Light/reduced-motion static contracts.

`frontend/package.json` `test:unit` includes `financeStage2ClientBilling.test.js`.

---

## What’s provisional until cutover

- All engine-derived composer amounts use `PARTIAL` / `INCOMPLETE` confidence — never `RECONCILED`
- Parent + composer provisional banners when `FINANCE_CUTOVER_COMPLETE=false`
- Ledger writes / generate / Post charge require `BILLING_LEDGER_WRITES` (+ billing enabled + permission)
- Zoho remains stub until a real Books key + later Collections stage
- Production visibility remains forced off via `isCanonicalProductionFrontend()`

---

## Stack / PR notes

1. Open Stage 2 PR with **base = `feat/finance-dashboard-stage1`** until PR #14 merges to `main`.
2. After #14 lands on `main`, retarget Stage 2 base to `main` (or rebase).
3. Do **not** enable `VITE_ENABLE_CLIENT_BILLING` / `ENABLE_BILLING` / `BILLING_LEDGER_WRITES` / `FINANCE_CUTOVER_COMPLETE` in production from this stage.
4. Do **not** proceed to Stage 3 from this handoff.

---

## Institution proof (brief)

1. **Structured knowledge:** Blocking exception codes, draft charge IDs, confidence markers, Zoho sync status — reusable signals, not prose.
2. **Reuse:** Runtime-config + Zoho adapter + draft-charge list feed composer, bulk, and later Exception Queue stages.
3. **Therapist/parent friction:** Warm copy, blocked-build clarity, explicit Post for DRAFT, mobile cards kept.
4. **Token economy:** No new LLM triggers; Layer 1/2 only.
5. **Scale:** SELECT-scoped exception/draft queries by `case_id` + `ledger_month`; no N+1 write loops.

---

`STAGE_2_READY_FOR_STAGING`
