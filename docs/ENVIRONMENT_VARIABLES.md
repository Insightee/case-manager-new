# Environment variables reference

Single reference for **all** configuration used by InsightCase. **Never commit secrets** — use `.env` locally (gitignored), Railway for production API secrets, and Vercel for frontend build vars only.

## Quick pairing (deploy)

| Platform | Project / service | What to set |
|----------|-------------------|-------------|
| **Railway** | `case-manager-new` (API) | All backend vars below except `VITE_*` |
| **Vercel** | `insightes-projects/frontend` | **`VITE_API_URL` only** |
| **Local** | `backend/.env` + optional `frontend/.env.local` | See templates below |

Detail: [RAILWAY_VERCEL.md](./RAILWAY_VERCEL.md) · Deploy checklist: [DEPLOY.md](./DEPLOY.md)

### Template files (copy, do not commit filled secrets)

| File | Use |
|------|-----|
| [`backend/.env.example`](../backend/.env.example) | Local / Docker API |
| [`backend/env.railway.example`](../backend/env.railway.example) | Railway production API |
| [`frontend/.env.example`](../frontend/.env.example) | Local Vite |
| [`frontend/vercel-env.example`](../frontend/vercel-env.example) | Vercel UI |

---

## Frontend (Vite / Vercel)

| Variable | Required | Default | Where | Description |
|----------|----------|---------|-------|-------------|
| `VITE_API_URL` | Vercel yes; local optional | *(empty)* | Vercel only | Public API base URL, **no trailing slash**. Local dev: leave empty to proxy `/api` → `http://localhost:8000`. |
| `VITE_POLICIES_BOT_URL` | no | — | Frontend | Fallback policies-bot URL if `/api/v1/support/info` does not return one. |

**Do not** set on Vercel: `DATABASE_URL`, `JWT_*`, `SMTP_*`, `R2_*`, or any backend-only var.

---

## Backend — core runtime

Loaded from environment via [`backend/app/core/config.py`](../backend/app/core/config.py) (`Settings`). Names are case-insensitive; use **UPPER_SNAKE** in `.env` and Railway.

### Application & database

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `APP_ENV` | yes (prod) | `development` | `development` \| `test` \| `production`. Production triggers startup guards in [`production_checks.py`](../backend/app/core/production_checks.py). |
| `SEED_DEMO_DATA` | prod: must be false | `false` | If true, demo seed may run on startup — **never** on shared production. |
| `DATABASE_URL` | yes (prod) | SQLite file under `backend/` | Postgres locally: `postgresql+psycopg2://user:pass@host:5432/db`. Railway: `${{Postgres.DATABASE_URL}}`. |
| `REDIS_URL` | yes (prod) | `redis://localhost:6379/0` | Refresh tokens / rate limits. Railway: `${{Redis.REDIS_URL}}`. |
| `DB_POOL_SIZE` | prod recommended | `10` | SQLAlchemy pool size **per worker**. |
| `DB_MAX_OVERFLOW` | prod recommended | `20` | Extra connections per worker. Keep `WEB_CONCURRENCY × (DB_POOL_SIZE + DB_MAX_OVERFLOW)` below Postgres `max_connections`. |
| `WEB_CONCURRENCY` | prod recommended | `2` | Uvicorn workers in [`start-production.sh`](../backend/scripts/start-production.sh). Not read by `Settings`. |

### Auth (JWT)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `JWT_SECRET_KEY` | yes (prod) | dev placeholder | Access token signing secret. |
| `JWT_REFRESH_SECRET_KEY` | yes (prod) | dev placeholder | Refresh token signing secret. |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | no | `30` | Access token TTL. |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | no | `7` | Refresh token TTL. |

### CORS & frontend links

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CORS_ORIGINS` | yes (prod) | `http://localhost:5173,...` | Comma-separated browser origins allowed for API calls. Include production Vercel URL. |
| `CORS_ORIGIN_REGEX` | no | auto in prod | Optional regex for extra origins (e.g. Vercel previews). If unset in production, defaults to `https://frontend-*.vercel.app`. |
| `FRONTEND_URL` | yes (prod) | `http://localhost:5173` | Base URL for invite links, password reset, booking emails — must match Vercel production domain. |

### Email (SMTP / ZeptoMail)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `EMAIL_PROVIDER` | prod | `smtp` | Use `zeptomail` in production. |
| `SMTP_HOST` | prod | — | e.g. `smtp.zeptomail.com`. Unset = log-only locally. |
| `SMTP_PORT` | no | `587` | SMTP port. |
| `SMTP_USER` | prod (ZeptoMail) | — | ZeptoMail: `emailapikey`. **Do not use `SMTP_USERNAME`.** |
| `SMTP_PASSWORD` | prod (ZeptoMail) | — | ZeptoMail send token. |
| `SMTP_TLS` | no | `true` | STARTTLS on port 587. |
| `SMTP_SSL` | no | `false` | Implicit SSL (port 465). |
| `SMTP_FROM_EMAIL` | no | `noreply@insighte.in` | Default sender address. |
| `SMTP_FROM_NAME` | no | `Insighte` | Display name in From header. |
| `SMTP_FROM` | no | — | Legacy full From header (overrides email+name when set). |
| `SMTP_FROM_BILLING_EMAIL` | no | — | Optional billing sender (must be verified in ZeptoMail). |
| `SMTP_FROM_VERIFICATION_EMAIL` | no | — | Optional verification sender. |
| `ADMIN_NOTIFICATION_EMAILS` | no | — | Comma-separated inboxes for walk-in / scheduling alerts. |

DNS / deliverability: [EMAIL_DNS.md](./EMAIL_DNS.md)

### Password reset

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PASSWORD_RESET_EXPIRE_HOURS` | no | `1` | Reset link lifetime. |
| `PASSWORD_RESET_RATE_LIMIT_PER_HOUR` | no | `3` | Max forgot-password requests per email per hour. |

### Object storage

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `STORAGE_PROVIDER` | yes (prod) | `local` | `local` (dev) or `r2` (production). |
| `STORAGE_PREFIX` | no | `insightcase` | Key prefix in bucket / local paths. |
| `STORAGE_ENVIRONMENT` | no | `development` | Logical env label for storage paths. |
| `MAX_UPLOAD_BYTES` | no | `10485760` | Max upload size (10 MiB). |
| `R2_ACCOUNT_ID` | prod (r2) | — | Cloudflare account ID. |
| `R2_ACCESS_KEY_ID` | prod (r2) | — | R2 API token access key (not Cloudflare account token). |
| `R2_SECRET_ACCESS_KEY` | prod (r2) | — | R2 secret key. |
| `R2_BUCKET_NAME` | prod (r2) | — | Bucket name. |
| `R2_ENDPOINT_URL` | prod (r2) | — | `https://<account_id>.r2.cloudflarestorage.com` |

Setup: [CLOUDFLARE_R2.md](./CLOUDFLARE_R2.md)

### Support portal (optional overrides)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `POLICIES_BOT_URL` | no | — | External policies clarification bot URL. |
| `SUPPORT_CONTACT_EMAIL` | no | `support@insighte.com` | Shown on support pages. |
| `SUPPORT_OFFICE_ADDRESS` | no | Koramangala address | Shown on support pages. |
| `GRIEVANCE_POLICY_URL` | no | insighte.com URL | Grievance policy link. |
| `SUPPORT_PHONE` | no | placeholder | Support phone display. |

### Product / feature flags

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BILLING_LEDGER_DRAFTS` | no | `true` | Billing ledger draft mode. |
| `ACCEPTANCE_GATING_ENABLED` | no | `false` | When false, parent assignment acceptance is informational only (pilot default). |
| `TICKET_ATTACHMENT_MAX_BYTES` | no | 5 MiB | Max size per ticket attachment. |
| `TICKET_ATTACHMENT_MAX_FILES` | no | `3` | Max attachments per ticket. |
| `CASE_DOCUMENT_MAX_BYTES` | no | 5 MiB | Max case document upload size. |
| `MEETING_INVITE_CALENDAR_TIMEZONE` | no | `Asia/Kolkata` | Google Calendar `ctz` for CM meeting invites. |

### SQLite dev-only

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LAZY_SQLITE_PATCHES` | no | `true` | Defer SQLite schema patches until first request (local/test). |

---

## Docker Compose (local stack)

[`docker-compose.yml`](../docker-compose.yml) sets these on the `api` service (override with `backend/.env`):

| Variable | Value in compose |
|----------|------------------|
| `APP_ENV` | `development` |
| `DATABASE_URL` | `postgresql+psycopg2://insightcase:insightcase@postgres:5432/insightcase` |
| `REDIS_URL` | `redis://redis:6379/0` |
| `JWT_SECRET_KEY` / `JWT_REFRESH_SECRET_KEY` | dev placeholders |
| `FRONTEND_URL` | `http://localhost:5173` |
| `CORS_ORIGINS` | localhost origins |

Postgres container: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` = `insightcase`.

---

## CI & automated tests

| Variable | Where | Description |
|----------|-------|-------------|
| `DATABASE_URL` | `backend/app/tests/conftest.py` | Per-process SQLite test DB (set before imports). |
| `APP_ENV` | conftest | `test` |
| `STORAGE_PROVIDER` | conftest | `local` |
| `VITE_API_URL` | [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) | Production API URL for frontend build in CI. |

---

## Smoke / ops scripts (optional)

Used by [`backend/scripts/production_smoke.py`](../backend/scripts/production_smoke.py) and [`production_api_flow_smoke.py`](../backend/scripts/production_api_flow_smoke.py):

| Variable | Description |
|----------|-------------|
| `API_BASE_URL` / `PUBLIC_API_URL` | Target API for smoke tests |
| `SMOKE_TEST_EMAIL` | Recipient for email smoke |
| `SMOKE_SKIP_EMAIL` | Skip email checks when `true` |
| `SMOKE_API_ONLY` | API-only smoke mode |
| `SMOKE_TEST_PASSWORD` | Login password (default `demo123`) |
| `SMOKE_ADMIN_EMAIL` | Admin login (default `superadmin@demo.com`) |
| `SMOKE_CM_EMAIL` | Case manager login |
| `RAILWAY_REPLICA_ID` | Set on Railway replicas (internal) |

---

## Deploy CLI tokens (not app runtime)

| Variable | Used for |
|----------|----------|
| `RAILWAY_API_TOKEN` | Account token — `railway link`, `variable set`, `whoami` (**Workspace = No workspace**) |
| `RAILWAY_TOKEN` | Project token — CI deploy only; **not** for `whoami` / `link` |
| `RAILWAY_PROJECT_ID` | Optional override in shell scripts |
| `VERCEL_TOKEN` | Vercel API / cleanup scripts |
| `VERCEL_URL` | Helper in Railway CORS scripts — production frontend URL |
| `VERCEL_SCOPE` / `VERCEL_PROJECT` | [`scripts/vercel_setup_frontend.sh`](../scripts/vercel_setup_frontend.sh) |

---

## Production validation

When `APP_ENV=production`, the API refuses to start if:

- Demo seed enabled, default JWT secrets, SQLite DB, local storage, missing/localhost Redis, localhost-only CORS/frontend URL, or invalid R2 config.

See [`backend/app/core/production_checks.py`](../backend/app/core/production_checks.py).

---

## Related documentation

- [RAILWAY_VERCEL.md](./RAILWAY_VERCEL.md) — step-by-step Railway + Vercel pairing
- [DEPLOY.md](./DEPLOY.md) — deploy checklist
- [CLOUDFLARE_R2.md](./CLOUDFLARE_R2.md) — R2 bucket and tokens
- [EMAIL_DNS.md](./EMAIL_DNS.md) — ZeptoMail and DNS
- [AGENTS.md](../AGENTS.md) — agent deploy rules (project names)
