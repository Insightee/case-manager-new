# Cursor Handover — Finance Control Tower Stage 1

**Verdict:** `STAGE_1_READY_FOR_STAGING`

**Branch:** `feat/finance-dashboard-stage1` (from `feat/billing-engine-steps-1-6`)  
**Base engine SHA at branch point:** `cdacb6dff31fc3967a99b808e0ea7174e3f870ab`  
**Scope:** Read-only Finance Control Tower on `/admin/invoices?tab=overview`. No engine calc changes, no money writes, no Zoho/RazorpayX, no merge/deploy of cutover.

---

## What shipped

### Backend (GET-only)

| Method + path | Purpose |
|---|---|
| `GET /api/v1/admin/finance-control-tower/summary?billing_month=` | Header meta, action queue, finance MoneyValues, readiness funnel, page confidence |
| `GET /api/v1/admin/finance-control-tower/exceptions?billing_month=&code=&queue=&limit=` | Exception preview (calc + period + eligibility + disputes) |
| `GET /api/v1/admin/finance-control-tower/billing-readiness?billing_month=&limit=` | Per-case readiness rows |
| `GET /api/v1/admin/finance-control-tower/payout-readiness?billing_month=&limit=` | Therapist payout readiness |

- Service: `backend/app/services/finance_control_tower_service.py` — SELECT/aggregate only; never calls `ensure_period_charges` / ledger upsert / invoice create.
- Router: `backend/app/api/v1/finance_control_tower.py`, mounted behind `Depends(require_billing)`.
- Role gate: `require_finance_control_tower_read()` → roles ∈ `{SUPER_ADMIN, FINANCE}` only (Founder/COO → SUPER_ADMIN). CASE_MANAGER / ADMIN / THERAPIST / PARENT blocked even if they hold `invoice.approve` elsewhere.
- Config: `FINANCE_CUTOVER_COMPLETE` default `false` → provisional banner; engine amounts never labelled `RECONCILED` pre-cutover.
- `BILLING_LEDGER_WRITES=false` does **not** block these reads.

### Frontend

- Flag: `VITE_ENABLE_FINANCE_DASHBOARD_V1` via `readClientModuleFlag` / `isFinanceDashboardV1Enabled()` (default off; forced off on canonical production).
- When flag off: calm feature-disabled empty state on Overview tab; other invoice tabs unchanged.
- When flag on: Control Tower layout in `AdminFinanceOverviewTab.jsx` — action queue, finance summary, readiness funnel, exception / billing / payout tables, drill-down via `?tab=overview&queue=&month=`.
- `ConfidenceBadge` + `financeConfidence.js` helpers (downgrade-only; never invent `RECONCILED`).
- Forest Light: `forest-light-theme.css` + scoped `finance-control-tower.css` on Control Tower root only; Manrope / Inter / JetBrains Mono wired in `index.html`.

### MoneyValue contract

```json
{
  "value": 420000,
  "currency": "INR",
  "confidence": "PARTIAL",
  "confidenceReason": "…",
  "recordCount": 83,
  "sourcePeriod": "2026-07",
  "asOf": "2026-08-02T15:00:00Z"
}
```

Count-only cards omit `value` (do not invent ₹). Contribution margin / profitability omitted.

---

## APIs reused (drill-down / deep links only)

Existing zero-write GETs remain available for list detail and composer/dispute/payout deep links (finance overview summary links, ledger lists, client invoices, therapist invoices). Control Tower KPIs use the new thin aggregation GETs only — not `finance-reports/margin-by-case` or reconciliation totals as summary KPIs.

---

## Zero-write proof

`app/tests/test_finance_control_tower_stage1.py` snapshots row counts + amount checksums on `billing_ledger`, `client_invoices`, `client_payments`, and therapist `invoices` **before and after** each of the four Control Tower GETs. Snapshots must be identical. Service source scan bans `ensure_period_charges`, `db.add`/`commit`/`delete`, and `billing_ledger_service` imports.

---

## Confidence rules (Stage 1)

| Level | When |
|---|---|
| `RECONCILED` | Never pre-cutover. `money_value()` downgrades to `PARTIAL` when `FINANCE_CUTOVER_COMPLETE=false`. |
| `PARTIAL` | Persisted ledger / invoice / payment rows exist but not production-reconciled. |
| `ESTIMATED` | Incomplete bases (therapist payable still partly log-gated; outstanding without ageing). |
| `INCOMPLETE` | Material source missing (no ledger rows, missing package count, blocking calc exception). |

Frontend may downgrade on partial load; never upgrade; missing metadata → `INCOMPLETE` if material source missing else `ESTIMATED`.

---

## RBAC

| Role | Control Tower GETs |
|---|---|
| SUPER_ADMIN | Allow |
| FINANCE (+ billing module for other finance surfaces) | Allow |
| CASE_MANAGER / ADMIN / MODULE_ADMIN / HR / THERAPIST / PARENT / CRM | 403 |

Staging needs `ENABLE_BILLING=true` for routers to mount. Prod keeps `ENABLE_BILLING=false` until cutover.

---

## Tests

| Suite | Coverage |
|---|---|
| `backend/app/tests/test_finance_control_tower_stage1.py` | Perm matrix (1–4, 19, 22); before/after zero-write (6–8); confidence never RECONCILED (12, 14); month filter (20); select-only service (23) |
| `frontend/src/lib/financeConfidence.test.js` | Downgrade / lowest / aggregate / formatInr (10, 11, 13, 15–16) |
| `frontend/src/lib/financeControlTowerStage1.test.js` | No mutating methods (5); cards from API (9); badge (11); drills (17); partial failure (18); no profitability (21); no resolve/assign (24); provisional banner (25); flag + Forest scope |

Run:

```bash
cd backend && python3 -m pytest app/tests/test_finance_control_tower_stage1.py -q
cd frontend && node --test src/lib/financeConfidence.test.js src/lib/financeControlTowerStage1.test.js
```

---

## Staging enablement (manual; not done by this PR)

1. Railway: `ENABLE_BILLING=true`, keep `BILLING_LEDGER_WRITES=false` for read-only tower verification, `FINANCE_CUTOVER_COMPLETE=false`.
2. Vercel preview/staging: `VITE_ENABLE_FINANCE_DASHBOARD_V1=true` (never on canonical production).
3. Sign in as `finance@demo.com` or Super Admin → `/admin/invoices?tab=overview`.
4. Confirm provisional banner, ConfidenceBadge text+tooltip, section-level failure isolation, no invent ₹ on count-only cards.

---

## Known gaps until cutover / Stage 2

- No engine amount may be `RECONCILED` until `FINANCE_CUTOVER_COMPLETE=true` **and** explicit recon match.
- Exception ownership/resolve absent → owner always `Unassigned`; no resolve UI.
- Therapist payable still partly log-gated → `ESTIMATED`.
- Missing package / assignment / leave KPIs reflect **persisted** exceptions + case fields only; empty until `ensure_period_charges` was run offline — Stage 1 must not trigger it.
- Ageing buckets, contribution margin, Zoho/RazorpayX — out of scope.
- CASE_MANAGER retains `invoice.approve` for other tabs; Control Tower deliberately tighter.

---

## Institution checklist

1. **Structured knowledge:** Month-scoped action-queue counts, MoneyValues with confidence metadata, readiness funnel markers, exception/readiness row structures — reusable IDs + flags over prose.
2. **Reuse:** Same aggregations serve staging ops review and future Stage 2 without re-entry; deep links reuse existing composer/dispute/payout surfaces.
3. **Therapist friction:** Stage 1 is admin/finance-only; no new therapist screens; therapists never see cross-therapist payouts.
4. **Token economy:** Pure Layer-1 SQL aggregates; no LLM / embedding calls.
5. **Scale:** Count/sum queries with month filters and list limits (≤500); no write amplification on read.

---

## Final verdict

**`STAGE_1_READY_FOR_STAGING`**

Do not merge to production cutover. Do not enable `VITE_ENABLE_FINANCE_DASHBOARD_V1` or `FINANCE_CUTOVER_COMPLETE` on canonical production from this PR. Stage 2 is out of scope.
