# Railway + Vercel configuration

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

### Dashboard checklist (API service)

1. **Postgres** plugin → set `DATABASE_URL=${{Postgres.DATABASE_URL}}` on the API service.
2. Copy variables from [`backend/env.railway.example`](../backend/env.railway.example) (JWT, SMTP, CORS, R2). R2 detail: [`CLOUDFLARE_R2.md`](CLOUDFLARE_R2.md).
3. **Root directory** for GitHub deploy: `backend` *or* repo root with root `railway.toml` (Dockerfile `backend/Dockerfile`).
4. **Start command:** `sh scripts/start-production.sh` (see [`backend/railway.toml`](../backend/railway.toml)).
5. **Networking** → generate public domain → use that URL as `VITE_API_URL` on Vercel.

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

If backend vars were copied to Vercel by mistake, run from repo root (after `vercel link`):

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
# Open Vercel URL → login → forgot-password → check Railway logs / email_logs
```
