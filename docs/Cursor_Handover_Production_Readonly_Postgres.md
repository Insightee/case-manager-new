# Production read-only Postgres access — finance cutover / staging dashboard

**Date:** 2026-08-03  
**Status:** `RO_ROLE_CREATED_ON_PRODUCTION` · cutover sizing **done** (situation **a**)  
**Goal:** Let agents (and staging finance work) **read** real production finance/case data without write risk.

---

## Done this session

1. Valid Railway **account** token authenticated as `techsupport@insighte.org`.  
2. Linked project `truthful-blessing` → environment **production** → service **Postgres**.  
3. Created Postgres role **`insightcase_readonly`** with `GRANT SELECT` on `public` + `default_transaction_read_only=on`.  
4. Verified: SELECT on `cases` yes; INSERT/UPDATE/DELETE no; write txn blocked.  
5. Ran cutover sizing **as RO** — see founder results below / artifact.

### Security (do now)

- Railway Postgres **superuser password was exposed in agent tooling** — **rotate it** in Railway.  
- Reset `insightcase_readonly` password (you do not have the session-generated secret after scrub):

```sql
ALTER ROLE insightcase_readonly PASSWORD '<new-strong-password>';
```

- Inject into Cursor secrets (not chat):

`READONLY_DATABASE_URL=postgresql://insightcase_readonly:<new-password>@<public-proxy-host>:<port>/railway?sslmode=require`

- **Revoke/rotate** any Railway token pasted in chat.

---

## Cutover sizing — production result (2026-08-03)

| Field | Value |
|---|---|
| Environment | **production** (`railway` DB) |
| Situation | **(a)** real `monthly_case_review` rows |
| Cases | 408 |
| MCR rows | 8 real / 0 fixtures |
| AUTO_MIGRATED | 0 |
| NEEDS_REVIEW (untouched) | **8** — all `Missing product_billing_rule_id` |
| Rate exposure sum | **₹2,32,300** (min 25,300 · median 30,000 · max 30,000) |
| PACKAGE missing session count | 0 |
| Alembic | `c2d3e4f5a6b7` |

**Finance needs to make roughly 8 case-by-case decisions before cutover** (real).

Artifacts: `/opt/cursor/artifacts/cutover-sizing/PRODUCTION_SIZING_FOUNDER.md`, `needs_review_worklist.csv`.

---

## Staging finance dashboard

| Approach | Guidance |
|---|---|
| RO queries | Use `READONLY_DATABASE_URL` for counts / sizing only |
| Dense UI data | Prefer sanitized dump → staging DB — **never** point staging app `DATABASE_URL` at production |

---

## SQL reference

[`docs/sql/create_production_readonly_role.sql`](./sql/create_production_readonly_role.sql) — role already applied on production; keep for rebuilds / other envs.
