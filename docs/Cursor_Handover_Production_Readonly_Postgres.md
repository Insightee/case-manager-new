# Production read-only Postgres access — finance cutover / staging dashboard

**Date:** 2026-08-03  
**Status:** `BLOCKED_WAITING_FOR_CREDENTIAL_INJECTION`  
**Goal:** Let agents (and staging finance work) **read** real production finance/case data without write risk.

---

## Why this is needed

- Cutover sizing (`monthly_case_review` / estimate pack) needs **production** case + rate rows.  
- Finance dashboard staging validation needs realistic populations; local/demo DBs are empty of real finance volume.  
- App `DATABASE_URL` on Railway is a **read-write** role — not safe to hand to agents as-is.

---

## What we need (exact)

Inject into the **Cursor cloud agent / environment secrets** (do not paste in chat or PRs):

| Secret name | Value |
|---|---|
| `READONLY_DATABASE_URL` | `postgresql://insightcase_readonly:<password>@<prod-host>:<port>/<prod-db>?sslmode=require` |

Optional helpers (not required if URL is complete):

| Secret | Purpose |
|---|---|
| `RAILWAY_API_TOKEN` | Account token (Workspace = **No workspace**) so ops can fetch host/db name via CLI without pasting the RW URL into chat |

**Do not** set staging/production app `DATABASE_URL` to this agent secret. Staging API must keep its own DB; use RO only for SELECT probes / export → import.

---

## How to create the role (one-time, human/ops)

1. Railway → project `case-manager-new` / Postgres → **Connect** (or `railway connect Postgres`).  
2. Run [`docs/sql/create_production_readonly_role.sql`](./sql/create_production_readonly_role.sql) with a **strong password**.  
3. Confirm as the new role:
   - `SELECT` on `cases` works  
   - `INSERT` on `cases` fails  
   - `SHOW default_transaction_read_only` → `on`  
4. Put the RO URL into Cursor secrets as `READONLY_DATABASE_URL`.  
5. Re-run / resume the agent and ask for cutover sizing (or staging dashboard seed export).

### Railway token path (alternative to clicking Connect)

```bash
export RAILWAY_API_TOKEN='…'   # Account → Tokens, No workspace
cd backend && npx @railway/cli link --project ead85fb6-1826-4eed-bad9-2513e89c4854
# Then open a Postgres shell / copy public TCP proxy host for the RO URL
```

Project token (`RAILWAY_TOKEN`) alone is for deploy — it does **not** replace a Postgres RO role.

---

## Staging finance dashboard — safe use of prod data

| Approach | Use when | Risk |
|---|---|---|
| **A. RO queries only** (cutover sizing, row counts, rate exposure) | Numbers / gates | Lowest — no copy |
| **B. Sanitized dump → staging DB** | UI demos with real-ish volumes | Medium — PII handling; never copy secrets/hashes carelessly |
| **C. Point staging `DATABASE_URL` at prod** | Never | **Forbidden** — write path would hit production |

Recommended for dashboard build: **A** for sizing; **B** (anonymized subset of cases/invoices/ledger) if staging UI needs dense data.

---

## Agent checklist after injection

1. Connect with `READONLY_DATABASE_URL` only.  
2. Abort if role can `INSERT`/`UPDATE`/`DELETE` on `cases`.  
3. Identify DB (prod vs staging) via `current_database()` / host label — say which.  
4. Classify `monthly_case_review` situation **(a)/(b)/(c)**.  
5. Run sizing or estimate pack; report founder-readable N + ₹ exposure.  
6. Never print the connection string.

---

## Current agent VM (2026-08-03)

| Item | State |
|---|---|
| `READONLY_DATABASE_URL` | **Missing** |
| `RAILWAY_API_TOKEN` / `RAILWAY_TOKEN` | **Missing** |
| Local `DATABASE_URL` | `127.0.0.1` only — not production |

Until secrets are injected, cutover sizing and prod-backed staging finance work remain blocked.
