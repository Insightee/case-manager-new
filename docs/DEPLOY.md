# Deploying InsightCase for dev previews

This app is a **split deployment**: the React UI on Vercel and the FastAPI API on a host with Postgres (or SQLite for demos only).

## Readiness checklist

| Area | Status | Notes |
|------|--------|--------|
| Backend tests | Run `pytest` from `backend/` | Should be green before pushing |
| Frontend build | `cd frontend && npm run build` | Produces `frontend/dist/` |
| API URL | `VITE_API_URL` on Vercel | Must point to a **public** API base (no trailing slash) |
| CORS | `CORS_ORIGINS` on API | Include your Vercel preview URL(s), e.g. `https://your-app.vercel.app` |
| Database | Postgres recommended | SQLite is fine for local demo only |
| Secrets | `JWT_SECRET_KEY`, `JWT_REFRESH_SECRET_KEY` | Change from dev defaults in any shared environment |
| Demo data | `SEED_DEMO_DATA=true` only on staging | **Not** run on production by default |
| Migrations | `python scripts/migrate_production.py` | Single Alembic head required (`alembic heads`) |
| Object storage | `STORAGE_PROVIDER=r2` + R2 env vars | Required when `APP_ENV=production` |
| Redis | `REDIS_URL` on Railway API | **Required** in production (refresh tokens; startup fails without it) |
| Release gate | [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md) | Manual pilot smoke before go-live |

## Production migrations

- **Single head:** `cd backend && PYTHONPATH=.:alembic python3 -m alembic heads` must show exactly one `(head)`.
- **Railway startup:** [`backend/scripts/start-production.sh`](../backend/scripts/start-production.sh) runs [`migrate_production.py`](../backend/scripts/migrate_production.py) before uvicorn (Postgres only; no SQLite patching in production).
- **Manual repair (emergency):** use Railway Postgres `DATABASE_PUBLIC_URL` from your machine, then `python3 scripts/migrate_production.py`. Avoid stamping head unless a DBA confirms schema matches. See [`repair_production_schema.py`](../backend/scripts/repair_production_schema.py) only for known partial-failure recovery.
- **Health check:** `GET /health` → `db_migration` should match the Alembic head revision.

## 1. Deploy the API (required for Vercel UI)

Options: Railway (recommended below), Render, Fly.io, or your own VM.

### Railway (Postgres + Docker API)

**Project ID:** `ead85fb6-1826-4eed-bad9-2513e89c4854` — full SMTP/Vercel pairing: [`docs/RAILWAY_VERCEL.md`](RAILWAY_VERCEL.md), env template [`backend/env.railway.example`](../backend/env.railway.example).

1. In [Railway](https://railway.com), open that project (or **New Project** → **Deploy from GitHub repo** → `Insightee/case-manager-new`).
2. Add a **PostgreSQL** plugin to the project.
3. Create a **service** for the API:
   - **Root directory:** `backend` (monorepo — required)
   - Build uses [`backend/railway.toml`](../backend/railway.toml) + [`backend/Dockerfile`](../backend/Dockerfile)
   - Start command (set in `railway.toml`, or paste in the service **Start Command**):

     ```bash
     sh scripts/start-production.sh
     ```

     That script runs `python scripts/migrate_production.py`, optionally demo seed when `SEED_DEMO_DATA=true`, then `uvicorn` on `$PORT`.

4. **Variables** on the API service (reference Postgres plugin for `DATABASE_URL`):

   | Variable | Value |
   |----------|--------|
   | `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (Railway reference) — auto-normalized to `postgresql+psycopg2` |
   | `JWT_SECRET_KEY` | long random string |
   | `JWT_REFRESH_SECRET_KEY` | different long random string |
   | `APP_ENV` | `production` |
   | `CORS_ORIGINS` | Your Vercel production domain (e.g. `https://frontend-omega-eight-92.vercel.app`), plus `http://localhost:5173` |
   | `FRONTEND_URL` | Same Vercel production URL as in `CORS_ORIGINS` (invite/reset email links) |
   | `STORAGE_PROVIDER` | `r2` |
   | `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME` | Cloudflare R2 credentials |
   | `REDIS_URL` | `${{Redis.REDIS_URL}}` — **required** in production |
   | `EMAIL_PROVIDER` | `zeptomail` |
   | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL` | ZeptoMail (see [`EMAIL_DNS.md`](EMAIL_DNS.md)) |
   | `SEED_DEMO_DATA` | omit or `false` in production; `true` only for demo/staging |

   Without `REDIS_URL`, production startup fails (refresh tokens must not use in-memory storage).

5. **Networking** → **Generate domain** (e.g. `https://insightcase-api-production.up.railway.app`).
6. Verify: `curl https://YOUR-RAILWAY-DOMAIN/health` → `{"status":"ok",...}`.
7. **Vercel** → Project → Environment variables → `VITE_API_URL` = Railway URL (no trailing slash) → **Redeploy** frontend.

**CLI (optional):** Railway uses **two token types** (see [`docs/RAILWAY_VERCEL.md`](RAILWAY_VERCEL.md#railway-tokens-why-whoami-fails)):

| Goal | Where to create | Env var | `whoami`? |
|------|-----------------|---------|-----------|
| Set variables, `link`, `list` | Account → Tokens, **Workspace = No workspace** | `RAILWAY_API_TOKEN` | Yes |
| CI deploy only | Project → Settings → Tokens | `RAILWAY_TOKEN` | **No** (expected) |

```bash
export RAILWAY_API_TOKEN="<account-token-no-workspace>"
unset RAILWAY_TOKEN
cd backend
sh scripts/verify_railway_token.sh
npx @railway/cli link --project ead85fb6-1826-4eed-bad9-2513e89c4854
```

Do not commit tokens; revoke any token pasted into chat.

**Minimum env vars:**

```bash
DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/insightcase
JWT_SECRET_KEY=<long-random-string>
JWT_REFRESH_SECRET_KEY=<long-random-string>
CORS_ORIGINS=https://your-app.vercel.app,https://your-app-*.vercel.app
FRONTEND_URL=https://your-app.vercel.app
APP_ENV=production
STORAGE_PROVIDER=r2
# R2_* variables — see backend/.env.example
```

**Startup (example):**

```bash
cd backend
pip install -r requirements.txt
python scripts/migrate_production.py
# Optional demo accounts (staging only):
# SEED_DEMO_DATA=true python3 -m app.seed.demo_seed
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Verify: `GET https://your-api.example.com/health` returns `{"status":"ok",...}`.

## 2. Deploy the frontend on Vercel

**Vercel project:** team `insightes-projects`, project name **`frontend`** — not `case-manager-new` (that name is the Railway API service only). CLI: `vercel --scope insightes-projects --project frontend`.

1. Import the GitHub repo in Vercel.
2. **Root Directory:** either set to `frontend`, **or** leave the repo root and rely on root [`vercel.json`](../vercel.json) (`npm ci --prefix frontend` / `npm run build --prefix frontend`).  
   If you see `ENOENT ... package.json` at `/vercel/path0/`, Vercel is building the monorepo root without one of those fixes.  
   Do **not** point Vercel env at [`backend/.env.example`](../backend/.env.example) — use [`frontend/vercel-env.example`](../frontend/vercel-env.example) (`VITE_API_URL` only). Root [`.vercelignore`](../.vercelignore) excludes `backend/` from the frontend deployment bundle.
3. Framework preset: **Vite** (when Root Directory is `frontend`, `frontend/vercel.json` applies).
4. **Environment variables** (Production + Preview):

   | Name | Example |
   |------|---------|
   | `VITE_API_URL` | `https://your-api.example.com` |

5. Deploy. Open the preview URL and sign in with seeded accounts (`parent@demo.com` / `demo123`, etc.).

**SPA routing:** `frontend/vercel.json` rewrites non-asset paths to `index.html` so `/parent/book` and other routes work on refresh.

## 3. Local parity with production UI

```bash
# Terminal A — API
cd backend && uvicorn app.main:app --reload --port 8000

# Terminal B — UI pointing at API
cd frontend
echo 'VITE_API_URL=http://localhost:8000' > .env.local
npm run dev
```

Use http://localhost:5173 (Vite proxies `/api` when `VITE_API_URL` is empty; for production-like behavior set `VITE_API_URL` explicitly).

## 4. GitHub push

Before pushing:

```bash
cd backend && python3 -m pytest app/tests -q
cd ../frontend && npm run build
```

Do **not** commit `frontend/dist/` (listed in root `.gitignore`). Vercel builds from source.

Optional: add a GitHub Actions workflow (see `.github/workflows/ci.yml`) to run tests on push.

## 5. Demo accounts (after seed)

| Portal | Email | Password |
|--------|-------|----------|
| Admin | `superadmin@demo.com` | `demo123` |
| Therapist | `therapist@demo.com` | `demo123` |
| Parent | `parent@demo.com` | `demo123` |

Full matrix: [backend/README.md](../backend/README.md).

## Known limitations for preview hosts

- **Email/SMTP** — optional; booking notifications may log only if SMTP is unset.
- **File uploads** — production requires `STORAGE_PROVIDER=r2` (API refuses `local` when `APP_ENV=production`).
- **Redis** — optional for current MVP features.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Railway deploy fails health/network check; logs show `demo_seed` / `Therapist is not actively assigned` | Set **`SEED_DEMO_DATA=false`** (or remove it) on the API service. Redeploy from latest `main` so startup uses `scripts/start-production.sh` (skips seed by default). Do not use a custom start command that always runs `demo_seed`. |
| Logs repeat `Running migrations...` / `Seeding demo data` and never `Starting API on port` | Container exits during seed before uvicorn; fix `SEED_DEMO_DATA` and redeploy (see row above). |
| `Database already at head (a1b2c3d4e5f7)` but API features missing | API image is stale; trigger a fresh Railway deploy from GitHub `main` so migrations reach current head. |
| Login works locally but not on Vercel | Set `VITE_API_URL` to the public API; check browser Network tab |
| CORS error in browser | Add exact Vercel URL to `CORS_ORIGINS` on API; redeploy API |
| Blank page after refresh on `/parent/...` | Ensure `vercel.json` rewrites are deployed |

## Email retry cron (Railway)

Invite and password-reset emails retry transient SMTP failures via a **separate Railway Cron service** (not inside the API process):

1. Create a new Railway service in the same project, same repo, **root directory** `backend`.
2. **Cron schedule:** every 10 minutes (`*/10 * * * *`).
3. **Start command:**

   ```bash
   python scripts/run_email_jobs.py all
   ```

4. Copy **`DATABASE_URL`** and **`REDIS_URL`** from the API service (Redis lock prevents double retries across replicas).
5. Optional Phase 2: set `ZEPTOMAIL_LOG_SYNC_ENABLED=true` after validating Zepto log API credentials; `all` then runs `sync-zeptomail` as well.

PR1 runs **`retry-invites` only** when the Zepto flag is false (default).

## Current gaps (checklist)

| Item | Status | Action |
|------|--------|--------|
| GitHub `main` CI | Last pushed commit **green**; large local diff **not on GitHub** | Commit + push onboarding/R2/session-log work; CI should pass (307 tests, single Alembic head locally) |
| Vercel project | Case Manager UI: **`insightes-projects/frontend`** (`prj_ibo0tJpTFO1Y8d5cKiKicB7Yr6vN`); recent deploys **ERROR** | Fix Root Directory vs [`vercel.json`](../vercel.json) (see [`RAILWAY_VERCEL.md`](RAILWAY_VERCEL.md)); set `VITE_API_URL`; redeploy |
| Railway API code | `/health` OK but `db_migration` behind; `forgot-password` **404** | Redeploy API from GitHub after push so `start-production.sh` runs migrations to head |
| CORS / `FRONTEND_URL` | May point at `insighte-session-logger` (wrong app) | Set Railway to your **`frontend`** production domain from Vercel |

`midhuns-projects/insighte-session-logger` is a **different** payroll app — not InsightCase.
| API 500 on first request | Run migrations + seed; check `DATABASE_URL` |
