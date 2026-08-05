# Migration validation process

## Rule: migrations are proven on Postgres, not SQLite

**Acceptance gate for billing (and finance) migrations:** CI job **`postgres-migration-proof`** in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs on every PR (and via **workflow_dispatch**). It:

1. Starts **PostgreSQL 16** (matches `docker-compose.yml` / prod stack).
2. Sets `DATABASE_URL` to the service container.
3. Asserts **exactly one** Alembic head (`alembic heads`).
4. Runs **seeded up/down/up** via `backend/scripts/postgres_migration_up_down_up.py`:
   - `upgrade head` (greenfield `create_all` + stamp on empty DB)
   - `demo_seed` + `postgres_migration_proof_seed` (one row per head revision table)
   - `downgrade <parent of head>` — new tables/columns must drop; core tables (`users`, `cases`, `client_invoices`) stay
   - `upgrade head` twice (re-apply + idempotency)
5. Runs `app/tests/test_postgres_migration_proof.py` with `MIGRATION_PROOF_REQUIRED=1` (tests **execute**, never skip).

**Manual Postgres proof** (Docker Compose on a laptop) is a **fallback only** when CI is unavailable — not the primary gate.

Greenfield-empty downgrade **does not** meet the gate: it never exercises drops against live rows or FK dependencies.

Do **not** treat any of the following as downgrade proof:

| Harness | Why it is insufficient |
|---------|-------------------------|
| `backend/app/tests/conftest.py` alembic bootstrap | Runs `upgrade head` once on a fresh per-process SQLite file; never exercises `downgrade`. **Resolved-by-CI:** `postgres-migration-proof` job. |
| Empty SQLite `alembic upgrade head` (incremental path) | Pre-existing chain friction — see **HARNESS-002** below. **Resolved-by-CI:** proof runs on real Postgres. |
| Greenfield Postgres `create_all` + stamp in `alembic/env.py` | First `upgrade head` on empty DB skips incremental revisions; downgrade/upgrade of the **latest** revision must still be run explicitly after stamp (orchestrator does this). |
| Downgrade on empty new tables | No rows → FK/CASCADE and data-dependent drops are untested. |

### Enum idempotency (Postgres)

Billing migrations that extend Postgres enums **must** use guarded adds, e.g.:

```sql
ALTER TYPE clientinvoicestatus ADD VALUE IF NOT EXISTS 'ISSUED';
```

Re-running `upgrade head` after values already exist must succeed because of the guard — not because Alembic silently skipped the revision. CI runs a second `upgrade head` to enforce this.

### Manual fallback (when CI unavailable)

```bash
# From repo root — Postgres only, not SQLite; never Railway DATABASE_URL
docker compose up -d postgres
export DATABASE_URL=postgresql+psycopg2://insightcase:insightcase@127.0.0.1:5432/insightcase_migration
export MIGRATION_PROOF_REQUIRED=1
export PYTHONPATH=backend:backend/alembic

cd backend
python3 scripts/postgres_migration_up_down_up.py
python3 -m pytest app/tests/test_postgres_migration_proof.py -q
```

### Adding a new migration head

1. Author additive revision off the single head with `has_table` / `has_column` guards.
2. Register the head in `backend/scripts/postgres_migration_proof_registry.py`:
   - `tables_added` / `columns_added` for downgrade assertions
   - `seed()` inserting ≥1 FK-backed row per new table
3. Open PR — **`postgres-migration-proof` must go green**.

---

## Known harness defects (do not confuse with migration authorship)

### HARNESS-001 — pytest SQLite bootstrap (`conftest.py`) — **Resolved-by-CI**

- **Symptom:** Tests pass after schema change; downgrade never runs.
- **Impact:** Regressions in `downgrade()` only surface on Postgres proof or production.
- **Mitigation:** `postgres-migration-proof` CI job (seeded up/down/up on every PR).

### HARNESS-002 — empty SQLite incremental upgrade + `env.py` greenfield split — **Resolved-by-CI**

- **Symptom:** Fresh SQLite file with incremental `alembic upgrade head` (bypassing greenfield stamp) fails with e.g. `duplicate column name: phone` mid-chain.
- **Root cause:** Long migration history with overlapping column adds; SQLite has no `IF NOT EXISTS` on `ADD COLUMN` in older revisions. Empty Postgres uses `env.py` greenfield path (`create_all` + stamp head) and does not hit the same path.
- **Impact:** SQLite incremental upgrade is **not** a substitute for Postgres proof.
- **Mitigation:** CI Postgres job is the authoritative migration gate.

---

## Revision registry (examples)

| Revision | Parent | Adds | Seeder |
|----------|--------|------|--------|
| `n8o9p0q1r2s3` | `m7n8o9p0q1r2` | `client_package_cycles`, `external_refs`, gateway cols on `client_payments`, enum `ISSUED`/`CLOSED` | `postgres_migration_proof_registry._seed_n8o9p0q1r2s3` |
| `c9d0e1f2a3b5` | `b8c9d0e1f2a4` | `billing_month_closes`, `case_billing_period_snapshots`, `client_invoices.billing_snapshot` | `_seed_c9d0e1f2a3b5` |
| `d0e1f2a3b4c6` | `c9d0e1f2a3b5` | `billing_readiness_exception_rules` | `_seed_d0e1f2a3b4c6` (when head) |

Downgrade drops new tables/columns; enum values may remain on Postgres (documented). Orchestrator: `backend/scripts/postgres_migration_up_down_up.py`. Seed entrypoint: `backend/scripts/postgres_migration_proof_seed.py`.
