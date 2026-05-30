# Railway + Vercel configuration

**Complete env reference:** [ENVIRONMENT_VARIABLES.md](./ENVIRONMENT_VARIABLES.md)

Split deploy: **API on Railway** (project below), **UI on Vercel**. SMTP and secrets live on Railway only.

## Railway project

| Item | Value |
|------|--------|
| Project ID | `ead85fb6-1826-4eed-bad9-2513e89c4854` (dashboard name: truthful-blessing) |
| Monorepo API root | `backend/` (or repo root + root [`railway.toml`](../railway.toml)) |
| Health check | `GET /health` |
| Production API (current) | `https://case-manager-new-production.up.railway.app` |

CLI link (from `backend/`):

```bash
npx @railway/cli login
npx @railway/cli link --project ead85fb6-1826-4eed-bad9-2513e89c4854
```

Repo link file: [`.railway/config.json`](../.railway/config.json).

### Railway tokens (why `whoami` fails)

Railway has **different tokens for different jobs**. Using the wrong one looks like a “broken” token even when it is valid.

| Token | Created at | Export as | Works for |
|-------|------------|-----------|-----------|
| **Account** | [Account → Tokens](https://railway.com/account/tokens), **Workspace = No workspace** | `RAILWAY_API_TOKEN` | `whoami`, `link`, `variable set`, `list` |
| **Workspace-scoped account** | Account → Tokens, workspace selected | `RAILWAY_API_TOKEN` | GraphQL API often OK; **CLI rejects** → Unauthorized |
| **Project** | Project → Settings → Tokens | `RAILWAY_TOKEN` | `railway up`, CI deploy; **not** `whoami` / `link` |

Common mistakes:

1. **Project token + `whoami`** — Project tokens never authenticate account commands. That failure is expected.
2. **Workspace-scoped account token** — Pick **No workspace** when creating the token ([Railway CLI issue #845](https://github.com/railwayapp/cli/issues/845)).
3. **Both env vars set** — CLI prefers `RAILWAY_TOKEN`. For account work: `unset RAILWAY_TOKEN` and use only `RAILWAY_API_TOKEN`.
4. **Wrong variable name** — Account token must be `RAILWAY_API_TOKEN`, not `RAILWAY_TOKEN`.

Diagnose locally (does not print your full token):

```bash
export RAILWAY_API_TOKEN='...'   # or RAILWAY_TOKEN for project token test
cd backend && sh scripts/verify_railway_token.sh
```

Or use browser login: `npx @railway/cli login` (no token needed for local `link` / vars).

### Railway API environment variables (`case-manager-new` service)

| Variable | Required | Notes |
|----------|----------|--------|
| `APP_ENV` | yes | `production` |
| `SEED_DEMO_DATA` | yes | `false` or unset |
| `DATABASE_URL` | yes | `${{Postgres.DATABASE_URL}}` |
| `REDIS_URL` | yes | `${{Redis.REDIS_URL}}` — startup fails if missing/unreachable |
| `WEB_CONCURRENCY` | yes | `3` (use `2`–`4`); uvicorn workers in `start-production.sh` |
| `DB_POOL_SIZE` | yes | `10` per worker |
| `DB_MAX_OVERFLOW` | yes | `20` per worker; keep `WEB_CONCURRENCY × (DB_POOL_SIZE + DB_MAX_OVERFLOW)` below Postgres `max_connections` (default `3×30=90`) |
| `JWT_SECRET_KEY`, `JWT_REFRESH_SECRET_KEY` | yes | Strong unique values |
| `STORAGE_PROVIDER` | yes | `r2` + all `R2_*` vars |
| `FRONTEND_URL`, `CORS_ORIGINS` | yes | **Exact** Vercel production domain from Settings → Domains (e.g. `https://frontend-omega-eight-92.vercel.app`). Not localhost-only. |
| `EMAIL_PROVIDER`, `SMTP_*` | yes | ZeptoMail on Railway only |

Template: [`backend/env.railway.example`](../backend/env.railway.example).

### Vercel UI environment variables (`insightes-projects/frontend`)

| Variable | Required | Notes |
|----------|----------|--------|
| `VITE_API_URL` | yes | Railway API URL, no trailing slash |

Do **not** set backend vars on Vercel. Cleanup: [`scripts/vercel_clean_backend_env_api.py`](../scripts/vercel_clean_backend_env_api.py).

### Dashboard checklist (API service)

1. **Postgres** plugin → set `DATABASE_URL=${{Postgres.DATABASE_URL}}` on the API service.
2. **Redis** plugin → set `REDIS_URL=${{Redis.REDIS_URL}}` on the API service.
3. Copy variables from [`backend/env.railway.example`](../backend/env.railway.example) (JWT, SMTP, CORS, R2). R2 detail: [`CLOUDFLARE_R2.md`](CLOUDFLARE_R2.md).
4. **GitHub deploy** uses repo-root [`railway.toml`](../railway.toml) + [`Dockerfile`](../Dockerfile) (copies `backend/`). CLI/`docker-compose` use [`backend/Dockerfile`](../backend/Dockerfile) with context `backend/`.
5. **Start command:** `sh scripts/start-production.sh` (see [`backend/railway.toml`](../backend/railway.toml)).
6. **Networking** → generate public domain → use that URL as `VITE_API_URL` on Vercel.

### One-shot CLI (SMTP + CORS)

```bash
export SMTP_PASSWORD='your-zeptomail-token'
export VERCEL_URL='https://your-app.vercel.app'
cp backend/scripts/railway_link_and_configure.example.sh backend/scripts/railway_link_and_configure.sh
chmod +x backend/scripts/railway_link_and_configure.sh
./backend/scripts/railway_link_and_configure.sh
```

Legacy SMTP-only script: [`backend/scripts/railway_smtp_env.example.sh`](../backend/scripts/railway_smtp_env.example.sh).

Email/DNS detail: [`EMAIL_DNS.md`](EMAIL_DNS.md).

## Vercel (frontend)

> **Agent rule:** GitHub repo is `case-manager-new`, but the **Vercel project name is `frontend`**. Railway uses `case-manager-new`. Every `vercel` CLI command must include `--project frontend` (or link `.vercel` to that project). Do **not** create or target a Vercel project named `case-manager-new`.

InsightCase UI lives on team **`insightes-projects`**, project name **`frontend`** (not `case-manager-new`).

| Item | Value |
|------|--------|
| Project ID | `prj_ibo0tJpTFO1Y8d5cKiKicB7Yr6vN` |
| Team / scope | `insightes-projects` |
| Git repo | `Insightee/case-manager-new` (monorepo) |
| Env example | [`frontend/vercel-env.example`](../frontend/vercel-env.example) |

**Required variable (Production + Preview):**

| Name | Value |
|------|--------|
| `VITE_API_URL` | `https://case-manager-new-production.up.railway.app` (no trailing slash) |

Do **not** add `SMTP_*`, `DATABASE_URL`, `R2_*`, `JWT_*`, or `backend/.env.example` to Vercel.

If backend vars were copied to Vercel by mistake, run from repo root (targets **`frontend`** only):

```bash
export VERCEL_TOKEN=...
python3 scripts/vercel_clean_backend_env_api.py
```

Legacy shell loop (slow):


```bash
chmod +x scripts/vercel_clean_backend_env.sh
./scripts/vercel_clean_backend_env.sh
```

Only **`VITE_API_URL`** should remain on the frontend project.

### Vercel build settings (fix common 8–12s ERROR deploys)

Pick **one** layout — do not mix:

| Setting | Option A (recommended) | Option B |
|---------|----------------------|----------|
| **Root Directory** | *(empty — repo root)* | `frontend` |
| Config file | [`vercel.json`](../vercel.json) | [`frontend/vercel.json`](../frontend/vercel.json) |
| Install | `npm install --no-audit --no-fund --prefix frontend` | `npm ci` or `npm install` |
| Build | `npm run build --prefix frontend` | `npm run build` |
| Output | `frontend/dist` | `dist` |

If Root Directory is `frontend` but Install still uses `--prefix frontend`, the build looks for `frontend/frontend` and fails immediately.

After a green deploy, copy **Settings → Domains** production URL into Railway `FRONTEND_URL` and `CORS_ORIGINS`.

### CORS / “Cannot reach API” on Vercel

If login or invite shows **Cannot reach the API** but `curl …/health` works, the browser origin is usually **not allowed by CORS**.

| Symptom | Cause | Fix |
|---------|--------|-----|
| UI at `https://frontend-omega-eight-92.vercel.app` | That host was missing from `CORS_ORIGINS` | Set `FRONTEND_URL` and add the same URL to `CORS_ORIGINS` on Railway, redeploy API |
| Invite email opens a different host | `FRONTEND_URL` was wrong when email was sent | Update Railway `FRONTEND_URL`, redeploy API, **re-send invite** from Admin |
| Git preview URLs | `frontend-git-*-insightes-projects.vercel.app` | Allowed by API CORS regex after latest backend deploy (`frontend-*.vercel.app`) |

Quick CORS check (replace origin with your Vercel URL):

```bash
curl -sI -H "Origin: https://frontend-omega-eight-92.vercel.app" \
  https://case-manager-new-production.up.railway.app/health | grep -i access-control
```

Expect: `access-control-allow-origin: https://frontend-omega-eight-92.vercel.app`

Railway-only CORS update (no SMTP):

```bash
export VERCEL_URL='https://frontend-omega-eight-92.vercel.app'
cd backend && npx @railway/cli variable set \
  FRONTEND_URL="$VERCEL_URL" \
  CORS_ORIGINS="http://localhost:5173,${VERCEL_URL}"
```

CLI (link + env + deploy):

```bash
npx vercel login
chmod +x scripts/vercel_setup_frontend.sh
./scripts/vercel_setup_frontend.sh
npx vercel --prod --scope insightes-projects
```

Deleted duplicate Vercel project `case-manager-new` on this team is fine — use **`frontend`** only.

## Pairing matrix

| Variable | Railway API | Vercel |
|----------|-------------|--------|
| `SMTP_*` / `EMAIL_PROVIDER` | Yes | No |
| `FRONTEND_URL` | Yes (email links) | No |
| `CORS_ORIGINS` | Yes (include Vercel URL) | No |
| `VITE_API_URL` | No | Yes |
| `JWT_*` / `DATABASE_URL` | Yes | No |

After any change: **redeploy API** (Railway) and **redeploy frontend** (Vercel).

## Verify

```bash
curl -s https://case-manager-new-production.up.railway.app/health
curl -sI -H "Origin: https://frontend-omega-eight-92.vercel.app" \
  https://case-manager-new-production.up.railway.app/health | grep -i access-control
# Open https://frontend-omega-eight-92.vercel.app/login → sign in
# Open invite link on the same host (or re-send invite after FRONTEND_URL fix)
```
