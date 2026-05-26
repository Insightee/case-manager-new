# InsightCase Backend

Case-centric healthcare operations API (FastAPI + SQLAlchemy + PostgreSQL/SQLite).

## Local setup

```bash
cd backend
python3 -m pip install -r requirements.txt
cp .env.example .env   # optional; defaults to SQLite for local dev
python3 -m app.seed.demo_seed
uvicorn app.main:app --reload --port 8000
```

With Docker (Postgres + Redis):

```bash
docker compose up --build
docker compose exec api python -m app.seed.demo_seed
```

## Demo accounts

| Email | Password | Role |
|-------|----------|------|
| therapist@demo.com | demo123 | THERAPIST |
| parent@demo.com | demo123 | PARENT |
| superadmin@demo.com | demo123 | SUPER_ADMIN |
| admin@demo.com | demo123 | MODULE_ADMIN (homecare only) |
| moduleadmin@demo.com | demo123 | MODULE_ADMIN (homecare + shadow + billing) |
| casemanager@demo.com | demo123 | CASE_MANAGER → `/admin/cm` |
| viewonly@demo.com | demo123 | CASE_MANAGER view-only → `/admin/cm` |
| shadowcm@demo.com | demo123 | CASE_MANAGER (shadow caseload) |
| support@demo.com | demo123 | MODULE_ADMIN (homecare + billing) |
| finance@demo.com | demo123 | FINANCE |

Re-run `python3 -m app.seed.demo_seed` to reset demo passwords if sign-in fails after DB changes.

### Staging / production: legacy staff roles

New invites cannot use legacy `ADMIN`, `VIEWER`, or `SUPERVISOR` (see RBAC catalog). Existing users may still have those roles until migrated:

```bash
cd backend
python3 -m scripts.migrate_staff_roles          # apply ADMIN → MODULE_ADMIN, VIEWER/SUPERVISOR → CASE_MANAGER
python3 -m scripts.migrate_staff_roles --dry-run  # preview only
```

Then verify sign-in and `/api/v1/admin/home` for affected accounts. Re-seed is an alternative for dev only.

## Schema and migrations

| Environment | How schema is applied |
|-------------|------------------------|
| **Postgres (staging/production)** | `python scripts/migrate_production.py` only (Alembic). Verify one head: `PYTHONPATH=.:alembic alembic heads` |
| **SQLite (local dev)** | `bootstrap_schema()` + `ensure_sqlite_schema_patches()` on API startup; Alembic is skipped |

**Core tables (case-centric):** `users`, `cases`, `case_assignments`, `children`, `sessions`, `daily_logs`, `invoices`, `client_billing_profiles`, `iep_plans`, `module_access_grants` (via user JSON / RBAC).

Legacy staff roles (`ADMIN`, `VIEWER`, `SUPERVISOR`) remain in the DB until `migrate_staff_roles.py` is run; new users use `MODULE_ADMIN` / `CASE_MANAGER` only.

## Tests

```bash
python3 -m pytest app/tests -q
PYTHONPATH=.:alembic alembic heads   # must show exactly one head
```

## API docs

- Health: `GET /health`
- Swagger: `http://localhost:8000/docs`

## Auth, Redis, and email (SMTP)

Copy [`backend/.env.example`](.env.example) to `.env` and set:

| Variable | Purpose |
|----------|---------|
| `JWT_SECRET_KEY` / `JWT_REFRESH_SECRET_KEY` | Sign access and refresh tokens (use long random values in production) |
| `FRONTEND_URL` | Base URL for invite and password-reset links in email |
| `CORS_ORIGINS` | Comma-separated browser origins allowed to call the API |
| `REDIS_URL` | Refresh-token storage (`redis://localhost:6379/0` locally; Upstash/Railway in prod) |
| `EMAIL_PROVIDER` | `zeptomail` or `smtp` (label only; sending uses SMTP below) |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` | Outbound mail transport |
| `SMTP_FROM_EMAIL` | General mail (`noreply@insighte.in`) — invites, reports |
| `SMTP_FROM_BILLING_EMAIL` | Billing mail (`billing.noreply@insighte.in`) |
| `SMTP_FROM_VERIFICATION_EMAIL` | Password reset (`verification.noreply@insighte.in`) |
| `SMTP_FROM_NAME` | Display name (e.g. `Insighte`) |
| `SMTP_FROM` | Optional legacy full From header (overrides default email when set) |
| `ADMIN_NOTIFICATION_EMAILS` | Comma-separated ops inboxes for some scheduling alerts |

When `SMTP_HOST` is unset, transactional email is **logged only** (no failure) — fine for local dev. Sent messages are recorded in the `email_logs` table when migrations are applied.

### ZeptoMail (production SMTP)

1. In [ZeptoMail](https://www.zoho.com/zeptomail/), verify domain `insighte.in` and create a **Send Mail** SMTP credential.
2. On Railway (API service only — never on Vercel frontend):

   | Variable | Example |
   |----------|---------|
   | `EMAIL_PROVIDER` | `zeptomail` |
   | `SMTP_HOST` | `smtp.zeptomail.com` |
   | `SMTP_PORT` | `587` |
   | `SMTP_USER` | `emailapikey` |
   | `SMTP_PASSWORD` | *(paste token in Railway secrets)* |
   | `SMTP_FROM_EMAIL` | `noreply@insighte.in` |
   | `SMTP_FROM_BILLING_EMAIL` | `billing.noreply@insighte.in` |
   | `SMTP_FROM_VERIFICATION_EMAIL` | `verification.noreply@insighte.in` |
   | `SMTP_FROM_NAME` | `Insighte` |
   | `SMTP_TLS` | `true` |

3. Add SPF/DKIM/DMARC in Cloudflare per ZeptoMail’s domain DNS page (see [`docs/EMAIL_DNS.md`](../docs/EMAIL_DNS.md)). Do not remove existing Hostinger MX records for business mail.
4. Redeploy API after `alembic upgrade head` so `email_logs` exists.

**Docker Compose:** `api` service sets `FRONTEND_URL`, `REDIS_URL`, and JWT vars; set `SMTP_*` in `.env` to send real mail.

**Railway / Vercel:** Set SMTP and JWT on the API service only; frontend needs `VITE_API_URL` pointing at the API.

**Password reset:** `POST /api/v1/auth/forgot-password`, `GET /api/v1/auth/reset-password/{token}/preview`, `POST /api/v1/auth/reset-password`. Frontend routes `/forgot-password` and `/reset-password/:token`.

## Support tickets (attachments & policies bot)

Optional environment variables:

| Variable | Description |
|----------|-------------|
| `POLICIES_BOT_URL` | External URL for the Policies clarification bot (opened from support pages) |
| `VITE_POLICIES_BOT_URL` | Frontend fallback if portal info is unavailable |

Ticket attachments: up to **3 files**, **5 MB** each (JPEG, PNG, WebP, PDF, plain text). Stored under `uploads/tickets/`. Staff and parents download via `GET /api/v1/tickets/attachments/{id}/download` when they have access to the ticket.

## Report image storage

Rich-text report images (monthly and observation) use a storage abstraction:

| `STORAGE_PROVIDER` | Behavior |
|--------------------|----------|
| `local` (default) | Files under `uploads/objects/{storage_prefix}/{environment}/report-images/...` |
| `r2` | Private Cloudflare R2 bucket via S3-compatible API; streamed through the API (no public URLs) |

Set `STORAGE_PREFIX`, `STORAGE_ENVIRONMENT`, and `MAX_UPLOAD_BYTES` (default 10 MB). For R2, configure `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, and optionally `R2_ENDPOINT_URL`. Allowed types: JPEG, PNG, WebP only.
