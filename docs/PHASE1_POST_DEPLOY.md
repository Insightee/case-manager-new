# Phase 1 post-deploy verification and monitoring

Use after Phase 1A merge (session auto-close, absence, scoped leave) and Phase 1B follow-ups.

## Deploy checklist

### Backend (Railway `case-manager-new`)

- [ ] `GET https://api.insighte.org/health` → 200
- [ ] CORS allows `https://www.insighte.org` and `https://insighte.org`
- [ ] No new Alembic migrations required for session patch

### Cron service `session-day-end`

| Setting | Value |
|---------|--------|
| Root directory | `backend` |
| Config | `railway.session-day-end-cron.toml` |
| Command | `python scripts/auto_close_sessions_day_end.py` |
| Schedule | `30 16 * * *` UTC (22:00 IST) |
| Env | `DATABASE_URL=${{Postgres.DATABASE_URL}}` |

Setup helper: `python backend/scripts/railway_setup_session_day_end_cron.py` (requires Railway token).

### Frontend (Vercel `insightes-projects/frontend`)

Deploy after API is live:

```bash
cd frontend && npm run build
npx vercel deploy --prod --scope insightes-projects --project frontend
```

### One-time stale session cleanup (if needed)

Only if production has `IN_PROGRESS` sessions from **prior IST days** before the patch:

```bash
cd backend
INSIGHTECASE_DRY_RUN=1 python scripts/close_previous_day_open_sessions.py
python scripts/close_previous_day_open_sessions.py
```

## Production spot-checks (scenarios A–F)

| ID | Scenario | Expected |
|----|----------|----------|
| A | Case-scoped leave for one client | Other clients' slots still visible |
| B | Therapist-wide leave | Full day blocked |
| C | Child absence submit + duplicate | Success card; duplicate shows status not error |
| D | Same-day active session | Relogin shows active card; after end → Needs Log |
| E | Prior-day stale `IN_PROGRESS` | Stale banner; composer works; after cron → COMPLETED |
| F | Manual cron / staging | `auto_end_reason=day_end_10pm_ist`, no auto-created log |

## 48h monitoring

Run `backend/scripts/phase1_post_deploy_monitoring.sql` at **T+0**, **T+24h**, **T+48h** on production Postgres.

Watch application logs for:

- Cron: `[session_day_end]` / `closed N session(s)`
- Absence 409 duplicate rate (expected low)
- Leave overlap validation errors
- Frontend offline vs auth-expired messaging
- 401 spikes (should not correlate with brief network blips after auth audit)

Record baseline counts in your deploy notes; investigate if stale `IN_PROGRESS` prior-day count rises after cron is live.

### Baseline log template (T+0)

| Metric | T+0 | T+24h | T+48h |
|--------|-----|-------|-------|
| `stale_in_progress_prior_days` | | | |
| `completed_without_log` | | | |
| `auto_end_reason` top row | | | |
| Absence requests by status | | | |

**T+0 verified (automated):** API `https://api.insighte.org/health` → 200; CORS allows `https://www.insighte.org`.

**Frontend deploy:** skipped in this pass — push to GitHub; Vercel production deploy when ready.
