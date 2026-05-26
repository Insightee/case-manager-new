# Railway + Vercel configuration

Split deploy: **API on Railway** (project below), **UI on Vercel**. SMTP and secrets live on Railway only.

## Railway project

| Item | Value |
|------|--------|
| Project ID | `b5944bdb-23e6-4d32-bf7e-f2eeb9494ca4` |
| Monorepo API root | `backend/` (or repo root + root [`railway.toml`](../railway.toml)) |
| Health check | `GET /health` |
| Production API (current) | `https://case-manager-new-production.up.railway.app` |

CLI link (from `backend/`):

```bash
npx @railway/cli login
npx @railway/cli link --project b5944bdb-23e6-4d32-bf7e-f2eeb9494ca4
```

Repo link file: [`.railway/config.json`](../.railway/config.json).

### Dashboard checklist (API service)

1. **Postgres** plugin → set `DATABASE_URL=${{Postgres.DATABASE_URL}}` on the API service.
2. Copy variables from [`backend/env.railway.example`](../backend/env.railway.example) (JWT, SMTP, CORS, R2).
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

| Item | Value |
|------|--------|
| Build | Root [`vercel.json`](../vercel.json) *or* Root Directory = `frontend` |
| Env example | [`frontend/vercel-env.example`](../frontend/vercel-env.example) |

**Required variable (Production + Preview):**

| Name | Value |
|------|--------|
| `VITE_API_URL` | Railway public API URL, **no trailing slash** |

Do **not** add `SMTP_*`, `DATABASE_URL`, or `backend/.env.example` to Vercel.

CLI (from `frontend/`):

```bash
npx vercel login
npx vercel link
export API_URL=https://case-manager-new-production.up.railway.app
cp scripts/vercel_env.example.sh scripts/vercel_env.sh
chmod +x scripts/vercel_env.sh && ./scripts/vercel_env.sh
npx vercel --prod
```

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
