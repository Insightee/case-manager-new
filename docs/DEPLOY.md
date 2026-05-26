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

## 1. Deploy the API (required for Vercel UI)

Options: Railway (recommended below), Render, Fly.io, or your own VM.

### Railway (Postgres + Docker API)

1. In [Railway](https://railway.com), **New Project** → **Deploy from GitHub repo** → `Insightee/case-manager-new`.
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
   | `CORS_ORIGINS` | `https://frontend-omega-eight-92.vercel.app` (add every Vercel preview URL you use) |
   | `FRONTEND_URL` | `https://frontend-omega-eight-92.vercel.app` |
   | `STORAGE_PROVIDER` | `r2` |
   | `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME` | Cloudflare R2 credentials |
   | `REDIS_URL` | `${{Redis.REDIS_URL}}` or Upstash URL (recommended for refresh tokens) |
   | `SEED_DEMO_DATA` | omit or `false` in production; `true` only for demo/staging |

   Redis is strongly recommended in production; without it, refresh tokens are in-memory (single replica only).

5. **Networking** → **Generate domain** (e.g. `https://insightcase-api-production.up.railway.app`).
6. Verify: `curl https://YOUR-RAILWAY-DOMAIN/health` → `{"status":"ok",...}`.
7. **Vercel** → Project → Environment variables → `VITE_API_URL` = Railway URL (no trailing slash) → **Redeploy** frontend.

**CLI (optional):** create a token at Railway → Account → Tokens, then:

```bash
export RAILWAY_TOKEN="<your-token>"
cd backend
npx @railway/cli link          # pick project
npx @railway/cli up --detach
npx @railway/cli domain
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

1. Import the GitHub repo in Vercel.
2. Set **Root Directory** to `frontend`.
3. Framework preset: **Vite** (or use `frontend/vercel.json`).
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
| Login works locally but not on Vercel | Set `VITE_API_URL` to the public API; check browser Network tab |
| CORS error in browser | Add exact Vercel URL to `CORS_ORIGINS` on API; redeploy API |
| Blank page after refresh on `/parent/...` | Ensure `vercel.json` rewrites are deployed |
| API 500 on first request | Run migrations + seed; check `DATABASE_URL` |
