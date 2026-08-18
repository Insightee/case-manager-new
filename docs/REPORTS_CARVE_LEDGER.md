# Reports carve ledger

Tracks files carved from the staging archive onto `main`, and branch consolidation events.

## Branch consolidation 2026-08-18

Mirror backup: `~/backups/insighte-case-mirror-20260817.git` (~55 MB). Verified SHAs: `08953e6b` (main), `c3bafaf0` (staging), `9959bc6d`, `9e1c689e`, `9f205f15` (evidence), four therapist branch tips.

### Annotated tags created (`archive/*-20260817`)

| Tag | SHA preserved | Original branch | Why not merged |
|-----|---------------|-----------------|----------------|
| `archive/reports-staging-20260817` | `c3bafaf0` | `staging/stabilisation-pre-reports` | Live Railway staging fork; frozen, not deleted |
| `archive/integration-reports-safe-release-20260817` | `9959bc6d` | `integration/reports-safe-release` | Reports carve on stale base |
| `archive/report-overhaul-20260817` | `9e1c689e` | `report-overhaul` | Second reports engine risk |
| `archive/wip-local-preserve-20260817` | `69cd21b6` | `wip/local-preserve-20260803` | WIP preserve |
| `archive/billing-20260817` | `16fdc06e` | `billing` | Stale finance fork |
| `archive/current-supabase-version-20260817` | `234c86d7` | `current-supabase-version` | Pre-Postgres-stack leftover |
| `archive/parent-therapist-communication-20260817` | `477def11` | `feature/parent-therapist-communication` | Would create second Alembic head |
| `archive/therapist-statement-20260817` | `75babb7a` | `feat/therapist-statement` | Alembic revision-id collision; work on main via #27 |
| `archive/therapist-billing-dashboard-20260817` | `7a96d25f` | `feat/therapist-billing-dashboard` | Duplicate; redaction on main via #23 |
| `archive/therapist-monthly-statement-20260817` | `755b8af7` | `feat/therapist-monthly-statement` | Patch on main via #27; Alembic collision |
| `archive/therapist-mobile-session-leave-20260817` | `7b37d354` | `feat/therapist-mobile-session-leave` | Misnamed CORS/docs branch |

### Remote branches deleted (history preserved in tags above or on `main`)

- `integration/reports-safe-release`, `report-overhaul`, `wip/local-preserve-20260803`, `billing`, `current-supabase-version`, `feature/parent-therapist-communication`
- `feat/therapist-statement`, `feat/therapist-billing-dashboard`, `feat/therapist-monthly-statement`, `feat/therapist-mobile-session-leave`
- `cursor/reports-wip-carve-26b4` (identical to staging; reachable from `archive/reports-staging-20260817`)
- Merged/superseded: `feat/session-structured-evidence`, `feat/session-structured-evidence-rebased`, `fix/ci-trigger-dev`, `cursor/cto-handover-*-rebased`, `cursor/cto-handover-*-0d7e`, `cursor/prod-readonly-postgres-access-*`

### Surviving remote refs (2026-08-18)

- `main`, `dev`
- `staging/stabilisation-pre-reports` (live Railway environment — **retained, frozen**)
- `cursor/finance-confidence-helper-0d7e` (draft PR #18 — conflicting, needs owner)
- `fix/alembic-guardrails` (open PR #43)

### Slice 1 landed on main

| PR | What |
|----|------|
| #38 | Structured session evidence (flags off), Alembic `s4e5v6i7d8e9` |
| #40–#42 | Clinical reports, admin ops reports, RO Postgres handover docs |
| #39 | CI triggers on `dev` |
