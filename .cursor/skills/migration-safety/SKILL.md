---
name: migration-safety
description: Safe Alembic / Postgres schema changes for InsighteCase. Use whenever a change adds or edits files in backend/alembic/versions/, changes SQLAlchemy models, or needs a data backfill. Covers single head, the head-pin test, the Postgres migration proof registry, additive-only changes and deploy-time risk.
---

# Migration Safety (InsighteCase)

**Why this matters:** Railway runs `backend/scripts/start-production.sh` -> `scripts/migrate_production.py` on every deploy of `case-manager-new`. A merged migration runs against production Postgres immediately. Agents never run migrations against production or any Railway database.

## Rules

1. **One Alembic revision per PR**, generated with `alembic revision` (auto hex id). Hand-written mnemonic ids are banned (`CONTRIBUTING.md`).
2. **Rebase on `origin/main` first**, then set `down_revision` to the current single head. Two heads = broken deploy.
3. **Additive only by default:** new tables, nullable columns or columns with server defaults, new indexes. No renames of existing tables/enums (`.cursor/rules/insighte-billing.mdc`). Drops, type narrowing, `NOT NULL` on populated columns, and data deletes need the owner's explicit approval in the PR.
4. **Downgrade must work** and must only undo this revision.
5. **Backfills** are idempotent, batched, and never touch billing amounts, invoices or payouts without owner sign-off. Prefer a separate, reviewed script over hidden data writes in a schema migration.
6. Works on both SQLite (local tests) and Postgres (CI proof, production). Use `op.batch_alter_table` for SQLite-incompatible alters.

## Required updates when you add a head

- [ ] New file in `backend/alembic/versions/` with correct `down_revision`
- [ ] Head-pin test updated: `backend/app/tests/test_session_structured_evidence.py::test_alembic_single_head_is_goal_repository_repair` asserts the exact head id (`rg -n "assert heads ==" backend/app/tests` to find all pins)
- [ ] Proof registry entry in `backend/scripts/postgres_migration_proof_registry.py`: `register_head("<rev>", tables_added=[...], columns_added=[(table, col)], seed=_seed_<rev>)` with a seed that inserts at least one FK-backed row
- [ ] Model + Pydantic schema + every API/portal consumer updated (see `cross-portal-impact`)

## Verify (paste summary lines in the PR)

```bash
cd backend && PYTHONPATH=.:alembic python3 -m alembic heads            # exactly one (head)
cd backend && PYTHONPATH=.:alembic python3 scripts/check_alembic_integrity.py
cd backend && python3 -m pytest app/tests -q -k "alembic or migration"
./scripts/run-ci-parity-checks.sh                                       # full gate
```

The Postgres up/down/up proof (`app/tests/test_postgres_migration_proof.py`) runs in CI with `MIGRATION_PROOF_REQUIRED=1`. Locally it needs a disposable Postgres (`docker-compose.yml`); it refuses Railway URLs on purpose. Never point it at a Railway database.

## PR description must state

- Revision id and `down_revision`; tables/columns added
- Whether it is purely additive; any data written
- Lock/size risk on large tables (session logs, sessions, notifications)
- Rollback plan (downgrade safe? app code compatible with both schemas during deploy?)
- Order dependency with other open PRs that also add migrations (whoever merges second must rebase and re-point `down_revision`)
