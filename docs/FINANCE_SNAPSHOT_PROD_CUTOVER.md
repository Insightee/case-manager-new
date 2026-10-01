# Finance snapshot — production cutover (insighte.org)

Read-only Stage 1 cutover: **Finance snapshot** on Client invoices → Tools → Snapshot, plus Control Tower summary APIs. No ledger writes, no client billing UI, no payout release.

**Applied:** 2026-08-28 (commit on `main` + run `./scripts/enable_finance_snapshot_prod.py` when tokens available).

---

## What gets enabled

| Surface | Behaviour |
|---------|-----------|
| **Client invoices → Tools → Snapshot** | Summary metrics + confidence badges (SUPER_ADMIN / FINANCE) |
| **Finance Control Tower APIs** | `GET /api/v1/admin/finance-control-tower/*` return 200 for authorised roles |
| **Provisional banner** | Still shown while `FINANCE_CUTOVER_COMPLETE=false` |

## What stays off (do not change in this cutover)

| Variable | Value | Why |
|----------|-------|-----|
| `BILLING_LEDGER_WRITES` | `false` | Blocks automatic ledger / invoice mutations |
| `FINANCE_CUTOVER_COMPLETE` | `false` | Never labels amounts RECONCILED pre-cutover |
| `VITE_ENABLE_CLIENT_BILLING` | unset/false | Parent/therapist billing UI stays gated on prod |
| `PAYOUT_EXPORT_ENABLED` / `PAYOUT_RELEASE_ENABLED` | `false` | No live payout release |

---

## One-command cutover (recommended)

From repo root, with tokens exported:

```bash
export RAILWAY_PROJECT_TOKEN='…'   # Railway → Project → Settings → Tokens
export VERCEL_TOKEN='…'            # Vercel → Account → Tokens

python3 scripts/enable_finance_snapshot_prod.py
```

Then **redeploy both**:

1. **Railway** — service `case-manager-new` (production environment)
2. **Vercel** — team `insightes-projects`, project **`frontend`** only (Production deployment)

Verify:

```bash
python3 scripts/enable_finance_snapshot_prod.py --verify-only
```

Manual UI: https://www.insighte.org → Super Admin → **Client invoices** → **Tools** → **Snapshot** → metrics load (not “environment gate” copy).

---

## Manual dashboard steps

### Railway (`case-manager-new` API service)

| Variable | Set to |
|----------|--------|
| `ENABLE_BILLING` | `true` |
| `BILLING_LEDGER_WRITES` | `false` *(confirm unchanged)* |
| `FINANCE_CUTOVER_COMPLETE` | `false` *(confirm unchanged)* |

CLI alternative (account token, `backend/` linked):

```bash
export RAILWAY_API_TOKEN='…'   # Account → Tokens, Workspace = **No workspace**
unset RAILWAY_TOKEN
cd backend
npx @railway/cli variable set \
  ENABLE_BILLING=true \
  BILLING_LEDGER_WRITES=false \
  FINANCE_CUTOVER_COMPLETE=false
```

Redeploy the API service.

### Vercel (`insightes-projects` / project `frontend`, **Production** target only)

| Variable | Set to |
|----------|--------|
| `VITE_ENABLE_FINANCE_DASHBOARD_V1` | `true` |
| `VITE_FINANCE_DASHBOARD_ALLOW_PROD` | `true` |

Both are required on canonical production (`insighte.org` / Vercel Production). See `frontend/src/lib/productFeatureFlags.js` → `readFinanceDashboardV1Flag()`.

CLI:

```bash
export VERCEL_TOKEN='…'
SCOPE="insightes-projects"
PROJECT="frontend"
VC="--scope $SCOPE --project $PROJECT"

printf '%s' "true" | npx vercel env add VITE_ENABLE_FINANCE_DASHBOARD_V1 production $VC --force
printf '%s' "true" | npx vercel env add VITE_FINANCE_DASHBOARD_ALLOW_PROD production $VC --force

npx vercel --prod --scope $SCOPE --project $PROJECT
```

**Do not** set backend secrets (`JWT_*`, `DATABASE_URL`, `SMTP_*`) on Vercel.

---

## Verification checklist

- [ ] `curl -s https://case-manager-new-production.up.railway.app/health` → `"status":"ok"`
- [ ] Unauthenticated `GET …/admin/finance-control-tower/summary` → **401/403**, not **404**
- [ ] Super Admin → Client invoices → Tools → Snapshot → summary grid loads
- [ ] `BILLING_LEDGER_WRITES` still `false` on Railway (no new ledger rows from session approve smoke)
- [ ] Finance lead sign-off on one billing month preview (read-only)

## Rollback

| Platform | Action |
|----------|--------|
| Railway | `ENABLE_BILLING=false` → redeploy API |
| Vercel Production | Remove or set `false`: `VITE_ENABLE_FINANCE_DASHBOARD_V1`, `VITE_FINANCE_DASHBOARD_ALLOW_PROD` → redeploy frontend |

---

## Related docs

- [ENVIRONMENT_VARIABLES.md](./ENVIRONMENT_VARIABLES.md) — flag reference
- [FINANCE_CUTOVER_RUNBOOK.md](./FINANCE_CUTOVER_RUNBOOK.md) — full money cutover (Steps 3+)
- [Cursor_Handover_Finance_Dashboard_Stage1.md](./Cursor_Handover_Finance_Dashboard_Stage1.md) — API surface
