# Production release checklist (controlled pilot)

Use before promoting a build to production or onboarding real client data. See also [`STAGING_SMOKE.md`](STAGING_SMOKE.md) for API-level import and session-log flows.

## Pre-deploy

- [ ] `cd backend && python3 -m pytest app/tests -q` — green
- [ ] `cd backend && PYTHONPATH=.:alembic python3 -m alembic heads` — exactly **one** `(head)`
- [ ] `cd frontend && npm run build` — green
- [ ] Railway API: `APP_ENV=production`, `SEED_DEMO_DATA=false`, Postgres `DATABASE_URL`, **`REDIS_URL=${{Redis.REDIS_URL}}`**, **`WEB_CONCURRENCY=3`**, **`DB_POOL_SIZE=10`**, **`DB_MAX_OVERFLOW=20`** (peak ~90 DB conns), JWT secrets (not dev defaults), `STORAGE_PROVIDER=r2` + `R2_*`, Zepto `SMTP_*`, `FRONTEND_URL` + `CORS_ORIGINS` (Vercel URL)
- [ ] Vercel UI: team **`insightes-projects`**, project **`frontend`** only — **`VITE_API_URL`** = Railway API URL (no trailing slash). No backend secrets on Vercel ([`scripts/vercel_clean_backend_env_api.py`](../scripts/vercel_clean_backend_env_api.py))
- [ ] Optional: `cd backend && python3 scripts/production_smoke.py` with production env loaded

## Deploy

- [ ] Push `main` → Railway builds API from [`railway.toml`](../railway.toml) + [`backend/Dockerfile`](../backend/Dockerfile)
- [ ] Startup logs: migrations run, **demo seed skipped**, `Starting API on port …`
- [ ] `curl -s https://YOUR-API/health` → `status":"ok"` and `db_migration` at Alembic head
- [ ] Redeploy Vercel **frontend** after env changes

## Manual smoke (pilot)

- [ ] **Login** — admin (`superadmin@demo.com` or imported staff), therapist, parent portals load
- [ ] **Therapist daily log** — submit session log for assigned case
- [ ] **CM approve** — pending log appears; approve/reject works
- [ ] **Parent visibility** — approved log visible on parent portal
- [ ] **Billing** — therapist invoice preview or admin billing view loads for a case (no payment gateway required)
- [ ] **File upload/download** — case document or ticket attachment upload; download via API (not public URL)
- [ ] **Calendar/scheduling** — therapist or admin calendar/slots view loads
- [ ] **Email** — forgot-password or invite returns 200 (Zepto senders verified)

## Post-deploy

- [ ] Rotate any secrets exposed during setup (tokens in chat, old Railway/Vercel keys)
- [ ] Confirm no `uploads/` PHI on Railway disk (R2 only for new files)
