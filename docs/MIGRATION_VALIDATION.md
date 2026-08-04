# Migration validation process

## Rule: migrations are proven on Postgres, not SQLite

**Acceptance gate for billing (and finance) migrations:** prove `upgrade head` → `downgrade <parent>` → `upgrade head` on a **throwaway PostgreSQL** database (Docker Compose or CI Postgres service).

Do **not** treat any of the following as downgrade proof:

| Harness | Why it is insufficient |
|---------|-------------------------|
| `backend/app/tests/conftest.py` alembic bootstrap | Runs `upgrade head` once on a fresh per-process SQLite file; never exercises `downgrade`. |
| Empty SQLite `alembic upgrade head` (incremental path) | Pre-existing chain friction — see defect **HARNESS-002** below. |
| Greenfield Postgres `create_all` + stamp in `alembic/env.py` | First `upgrade head` on empty DB skips incremental revisions; downgrade/upgrade of the **latest** revision must still be run explicitly after stamp. |

### Recommended Postgres proof (client billing loop example)

```bash
# From repo root — Postgres only, not SQLite
docker compose up -d postgres
export DATABASE_URL=postgresql+psycopg2://insightcase:insightcase@127.0.0.1:5432/insightcase
export PYTHONPATH=backend:backend/alembic

cd backend
alembic upgrade head                                    # greenfield: create_all + stamp head
alembic downgrade m7n8o9p0q1r2                          # drops n8o9p0q1r2s3 objects
alembic upgrade head                                    # re-applies n8o9p0q1r2s3
# Optional: verify tables client_package_cycles, external_refs exist
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
| `n8o9p0q1r2s3` | `m7n8o9p0q1r2` | `client_package_cycles`, `external_refs`, gateway cols on `client_payments`, enum values `ISSUED`/`CLOSED` (Postgres `ALTER TYPE`) |

Downgrade drops new tables/columns; enum values remain on Postgres (documented, same as other finance migrations).
