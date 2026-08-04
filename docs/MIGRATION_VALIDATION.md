# Migration validation process

## Rule: migrations are proven on Postgres, not SQLite

**Acceptance gate for billing (and finance) migrations:** prove on a **throwaway PostgreSQL** database (Docker Compose or local Postgres):

1. `upgrade head` (greenfield stamp or incremental)
2. **Seed at least one row** into every new/affected table (FK-backed data — not an empty schema)
3. `downgrade <parent>`
4. `upgrade head` (must succeed again — enum adds must be idempotent)

Greenfield-empty downgrade **does not** meet the gate: it never exercises drops against live rows or FK dependencies.

Do **not** treat any of the following as downgrade proof:

| Harness | Why it is insufficient |
|---------|-------------------------|
| `backend/app/tests/conftest.py` alembic bootstrap | Runs `upgrade head` once on a fresh per-process SQLite file; never exercises `downgrade`. |
| Empty SQLite `alembic upgrade head` (incremental path) | Pre-existing chain friction — see defect **HARNESS-002** below. |
| Greenfield Postgres `create_all` + stamp in `alembic/env.py` | First `upgrade head` on empty DB skips incremental revisions; downgrade/upgrade of the **latest** revision must still be run explicitly after stamp. |
| Downgrade on empty new tables | No rows → FK/CASCADE and data-dependent drops are untested. |

### Enum idempotency (Postgres)

Billing migrations that extend Postgres enums **must** use guarded adds, e.g.:

```sql
ALTER TYPE clientinvoicestatus ADD VALUE IF NOT EXISTS 'ISSUED';
```

Re-running `upgrade head` after values already exist must succeed because of the guard — not because Alembic silently skipped the revision. Verify with `\dT+ clientinvoicestatus` or `pg_enum` before and after the second upgrade.

### Recommended Postgres proof (client billing loop example)

```bash
# From repo root — Postgres only, not SQLite; never Railway DATABASE_URL
docker compose up -d postgres   # or local pg_ctl cluster
export DATABASE_URL=postgresql+psycopg2://insightcase:insightcase@127.0.0.1:5432/insightcase_migration
export PYTHONPATH=backend:backend/alembic

cd backend
alembic upgrade head                                    # greenfield: create_all + stamp head
alembic downgrade m7n8o9p0q1r2                          # exit stamp so next upgrade runs incremental n8o9p0q1r2s3
alembic upgrade head                                    # creates client_package_cycles, external_refs, gateway cols
python3 -m app.seed.demo_seed                           # base FK rows (cases, invoices, …)
python3 -m scripts.postgres_migration_proof_seed        # one row each: client_package_cycles, external_refs, client_payments (gateway cols)

# Confirm seeded rows exist before downgrade
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM client_package_cycles;"
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM external_refs;"
psql "$DATABASE_URL" -c "SELECT gateway_provider FROM client_payments WHERE gateway_provider IS NOT NULL LIMIT 1;"

alembic downgrade m7n8o9p0q1r2                          # drops n8o9p0q1r2s3 objects (with data)
alembic upgrade head                                    # re-applies n8o9p0q1r2s3 (enum IF NOT EXISTS)
alembic upgrade head                                    # second pass: revision no-op; enum guard already proven

# Optional: verify enum labels include ISSUED, CLOSED
psql "$DATABASE_URL" -c "SELECT enumlabel FROM pg_enum e JOIN pg_type t ON e.enumtypid=t.oid WHERE t.typname='clientinvoicestatus' ORDER BY 1;"
```

Record command output in the PR or handover doc. CI may add a dedicated Postgres job later; until then this is a **manual gate** before merge.

---

## Known harness defects (do not confuse with migration authorship)

### HARNESS-001 — pytest SQLite bootstrap (`conftest.py`)

- **Symptom:** Tests pass after schema change; downgrade never runs.
- **Impact:** Regressions in `downgrade()` only surface on Postgres proof or production.
- **Mitigation:** Postgres up/down/up gate above for every additive migration.

### HARNESS-002 — empty SQLite incremental upgrade + `env.py` greenfield split

- **Symptom:** Fresh SQLite file with incremental `alembic upgrade head` (bypassing greenfield stamp) fails with e.g. `duplicate column name: phone` mid-chain.
- **Root cause:** Long migration history with overlapping column adds; SQLite has no `IF NOT EXISTS` on `ADD COLUMN` in older revisions. Empty Postgres uses `env.py` greenfield path (`create_all` + stamp head) and does not hit the same path.
- **Impact:** SQLite incremental upgrade is **not** a substitute for Postgres proof. Do not “fix” by editing `env.py` without a dedicated platform ticket.
- **Tracking:** Same class as finance engine release gate note in `docs/Cursor_Handover_Finance_Engine_Release_Gate.md` § PostgreSQL validation. File follow-up platform work if we need incremental SQLite CI (out of scope for billing loop).

---

## Client billing loop revision

| Revision | Parent | Adds |
|----------|--------|------|
| `n8o9p0q1r2s3` | `m7n8o9p0q1r2` | `client_package_cycles`, `external_refs`, gateway cols on `client_payments`, enum values `ISSUED`/`CLOSED` (Postgres `ALTER TYPE … ADD VALUE IF NOT EXISTS`) |

**Enum guard:** `_pg_enum_value()` in the revision executes `ADD VALUE IF NOT EXISTS` per label — re-upgrade is idempotent by design, not by skip.

Downgrade drops new tables/columns; enum values remain on Postgres (documented, same as other finance migrations). Seed script: `backend/scripts/postgres_migration_proof_seed.py`.
