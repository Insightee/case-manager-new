# 05 — Environment Variables

**Canonical extended reference:** [docs/ENVIRONMENT_VARIABLES.md](../ENVIRONMENT_VARIABLES.md)  
**Never commit secrets.** Use `[REDACTED]` in ops docs; store values in Railway/Vercel/local `.env` only.

Legend:

- **Required** — production startup fails or feature broken without it (per `production_checks.py` or feature docs)  
- **Local / Dev / Staging / Prod** — typical placement (staging specifics: **UNKNOWN — VERIFY WITH TEAM**)

---

## Frontend (Vite — prefix `VITE_`)

| Variable | Required | Purpose | Used by | Example |
|----------|----------|---------|---------|---------|
| `VITE_API_URL` | Vercel: yes; local: no | Public API base URL, no trailing slash. Empty local → Vite proxy | `apiClient.js`, CI build | `https://case-manager-new-production.up.railway.app` or empty |
| `VITE_POLICIES_BOT_URL` | no | Fallback policies bot URL | Support pages | `https://...` |
| `VITE_HIDE_THERAPIST_LEAVE_CREDITS_UI` | no | Hides leave credit UI for therapists | Leave page | `true` (default behavior unless `false`) |
| `VITE_ENABLE_STRUCTURED_EVIDENCE` | no | Session log IEP evidence taps | Session log forms | `false` |
| `VITE_ENABLE_CLIENT_BILLING` | no | Parent/therapist billing UI (Stage 2) | Billing pages | `false` |
| `VITE_ENABLE_BILLING` | no | Legacy alias for client billing flag | Billing | `false` |
| `VITE_ENABLE_FINANCE_DASHBOARD_V1` | no | Finance Control Tower UI | Admin finance | unset → on in non-prod |
| `VITE_FINANCE_DASHBOARD_ALLOW_PROD` | no | Opt-in prod finance dashboard | Admin finance | `false` |
| `VITE_REPORTS_REVAMP` | no | Therapist reports dashboard revamp | Reports | on unless `false` |

**Rule:** Do **not** set backend secrets on Vercel.

---

## Backend — core runtime

| Variable | Required | Purpose | Used by | Example |
|----------|----------|---------|---------|---------|
| `APP_ENV` | prod: yes | `development` \| `test` \| `production` | `config.py`, production guards | `development` |
| `DATABASE_URL` | prod: yes | SQLAlchemy URL | `database.py` | `postgresql+psycopg2://...` or SQLite path |
| `REDIS_URL` | prod: yes | Refresh tokens | `security.py` | `redis://localhost:6379/0` |
| `SEED_DEMO_DATA` | prod: must be false | Auto demo seed on startup | `main.py` bootstrap | `false` |
| `DB_POOL_SIZE` | prod recommended | SQLAlchemy pool per worker | engine config | `10` |
| `DB_MAX_OVERFLOW` | prod recommended | Extra connections | engine config | `20` |
| `WEB_CONCURRENCY` | prod recommended | Uvicorn workers | `start-production.sh` | `2` |
| `LAZY_SQLITE_PATCHES` | no | Defer SQLite patches | SQLite bootstrap | `true` |
| `EXPOSE_DB_ERRORS` | no | Return DB errors to client | exception handlers | `false` |

---

## Auth (JWT)

| Variable | Required | Purpose | Used by | Example |
|----------|----------|---------|---------|---------|
| `JWT_SECRET_KEY` | prod: yes | Access token HMAC secret | `security.py` | `[REDACTED]` |
| `JWT_REFRESH_SECRET_KEY` | prod: yes | Refresh token secret | `security.py` | `[REDACTED]` |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | no | Access TTL | config | `30` |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | no | Refresh TTL | config | `7` |
| `JWT_REFRESH_REMEMBER_DAYS` | no | Extended refresh | config | `90` |

---

## CORS & links

| Variable | Required | Purpose | Used by | Example |
|----------|----------|---------|---------|---------|
| `CORS_ORIGINS` | prod: yes | Allowed browser origins (comma-separated) | CORS middleware | `https://www.insighte.org,...` |
| `CORS_ORIGIN_REGEX` | no | Extra origin regex | CORS | auto in prod if unset |
| `FRONTEND_URL` | prod: yes | Invite/reset email links | email templates | `https://www.insighte.org` |

---

## Email (SMTP)

| Variable | Required | Purpose | Used by | Example |
|----------|----------|---------|---------|---------|
| `EMAIL_PROVIDER` | prod | Label (`zeptomail`) | email service | `zeptomail` |
| `SMTP_HOST` | prod for send | SMTP server | mail transport | `smtp.zeptomail.com` |
| `SMTP_PORT` | no | Port | mail | `587` |
| `SMTP_USER` | prod | SMTP auth user | mail | `emailapikey` |
| `SMTP_PASSWORD` | prod | SMTP token | mail | `[REDACTED]` |
| `SMTP_TLS` / `SMTP_SSL` | no | Transport security | mail | `true` / `false` |
| `SMTP_FROM_EMAIL` | no | Default From | mail | `noreply@insighte.in` |
| `SMTP_FROM_NAME` | no | Display name | mail | `Insighte` |
| `SMTP_FROM_BILLING_EMAIL` | no | Billing From | mail | `billing.noreply@insighte.in` |
| `SMTP_FROM_VERIFICATION_EMAIL` | no | Reset From | mail | `verification.noreply@insighte.in` |
| `SMTP_FROM` | no | Legacy full From header | mail | — |
| `ADMIN_NOTIFICATION_EMAILS` | no | Ops alert inboxes | scheduling alerts | comma-separated |
| `PASSWORD_RESET_EXPIRE_HOURS` | no | Reset token TTL | password reset | `1` |
| `PASSWORD_RESET_RATE_LIMIT_PER_HOUR` | no | Forgot-password rate limit | auth | `3` |

---

## Storage (R2 / local)

| Variable | Required | Purpose | Used by | Example |
|----------|----------|---------|---------|---------|
| `STORAGE_PROVIDER` | prod: `r2` | `local` or `r2` | storage layer | `local` |
| `STORAGE_PREFIX` | no | Key prefix | storage keys | `insightcase` |
| `STORAGE_ENVIRONMENT` | no | Path segment | storage keys | `development` |
| `MAX_UPLOAD_BYTES` | no | Upload cap | uploads | `10485760` |
| `R2_ACCOUNT_ID` | prod (r2) | Cloudflare account | boto3 client | `[REDACTED]` |
| `R2_ACCESS_KEY_ID` | prod (r2) | R2 API key id | boto3 | `[REDACTED]` |
| `R2_SECRET_ACCESS_KEY` | prod (r2) | R2 secret | boto3 | `[REDACTED]` |
| `R2_BUCKET_NAME` | prod (r2) | Bucket | boto3 | `[REDACTED]` |
| `R2_ENDPOINT_URL` | prod (r2) | S3 endpoint | boto3 | `https://<account>.r2.cloudflarestorage.com` |

---

## Billing / finance flags

| Variable | Default | Purpose |
|----------|---------|---------|
| `ENABLE_BILLING` | `false` | Mount billing/finance routers |
| `BILLING_LEDGER_WRITES` | `false` | Ledger upserts from sessions/logs |
| `BILLING_LEDGER_DRAFTS` | `true` | Draft ledger behavior |
| `FINANCE_CUTOVER_COMPLETE` | `false` | Control Tower reconciled labeling |
| `BILLING_APPROVAL_APPROVER_EMAIL` | configured email | Low-margin approval routing |
| `BILLING_MINIMUM_PROFIT_INR` | `5000` | Margin approval threshold |
| `ZOHO_BOOKS_API_KEY` | empty | Zoho sync seam |
| `ZOHO_BOOKS_LIVE_PUSH` | `false` | Live Zoho push |
| `PAYOUT_EXPORT_ENABLED` | `false` | Payout batch export |
| `PAYOUT_RELEASE_ENABLED` | `false` | Mark payouts paid |
| `PAYOUT_PROVIDER` | `MOCK` | `MOCK` or `RAZORPAY` |
| `PAYOUT_PROVIDER_LIVE` | `false` | Live Razorpay adapter |
| `FINANCE_DEFAULT_TDS_RATE_PERCENT` | `10` | TDS default |
| `BILLING_DISPUTE_LEGACY_ADJUSTMENT` | `false` | Legacy dispute adjustment field |
| `INVOICE_COMPANY_*` | Insighte defaults | PDF letterhead |
| `ENABLE_STRUCTURED_EVIDENCE` | `false` | IEP registry writes on session log |
| `ENABLE_CLINICAL_REPORTS_ENGINE` | `false` local; prod true | Clinical report API |
| `IEP_REVIEW_SUGGESTIONS_ENABLED` | `false` | IEP suggestions feature |
| `ACCEPTANCE_GATING_ENABLED` | `false` | Parent assignment acceptance gating |

---

## Integration API / MCP

| Variable | Required | Purpose |
|----------|----------|---------|
| `INTEGRATION_API_ENABLED` | no | Enable `/integrations` |
| `MCP_ENABLED` | no | Mount `/mcp` |
| `INTEGRATION_JWT_SECRET_KEY` | when integration on | Integration token signing |
| `INTEGRATION_ACCESS_TOKEN_MINUTES` | no | Integration access TTL |
| `INTEGRATION_DEFAULT_RATE_LIMIT_PER_MINUTE` | no | Rate limit |
| `INTEGRATION_MAX_PAGE_SIZE` | no | Page cap |
| `INTEGRATION_CREDENTIAL_DEFAULT_TTL_DAYS` | no | Credential TTL |

---

## Support / tickets / scheduling

| Variable | Purpose |
|----------|---------|
| `POLICIES_BOT_URL` | External bot link |
| `SUPPORT_CONTACT_EMAIL`, `SUPPORT_OFFICE_ADDRESS`, `GRIEVANCE_POLICY_URL`, `SUPPORT_PHONE` | Support UI copy |
| `TICKET_ATTACHMENT_MAX_BYTES`, `TICKET_ATTACHMENT_MAX_FILES` | Ticket uploads |
| `CASE_DOCUMENT_MAX_BYTES` | Case document uploads |
| `TICKET_FINANCE_ASSIGNEE_EMAIL`, `TICKET_HR_ASSIGNEE_EMAILS` | Ticket routing |
| `MEETING_INVITE_CALENDAR_TIMEZONE` | Calendar invites (`Asia/Kolkata`) |
| `SCHEDULING_WEEKENDS_ENABLED` | Weekend availability default |
| `SESSION_VOID_WINDOW_HOURS` | Void completed session without log |
| `LEAVE_MIGRATION_END_DATE` | Therapist leave backfill cutoff |

---

## Docker Compose (injected on `api` service)

See [docker-compose.yml](../../docker-compose.yml): `APP_ENV`, `DATABASE_URL`, `REDIS_URL`, JWT placeholders, `CORS_ORIGINS`, `FRONTEND_URL`, `ENABLE_CLINICAL_REPORTS_ENGINE`.

Postgres container: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` = `insightcase`.

---

## CI / smoke (not app runtime)

| Variable | Where | Purpose |
|----------|-------|---------|
| `DATABASE_URL` | pytest conftest | Per-worker SQLite |
| `APP_ENV=test` | CI | Test mode |
| `MIGRATION_PROOF_REQUIRED` | CI postgres job | Migration gate |
| `API_BASE_URL`, `SMOKE_*` | smoke scripts | Production smoke |
| `RAILWAY_API_TOKEN`, `RAILWAY_TOKEN`, `VERCEL_TOKEN` | deploy scripts | CLI auth `[REDACTED]` |

---

## Environment placement summary

| Class | Where to set |
|-------|----------------|
| **Local backend** | `backend/.env` |
| **Local frontend** | `frontend/.env.local` |
| **Production API** | Railway service variables |
| **Production UI** | Vercel project `frontend` — **`VITE_API_URL` only** (plus optional `VITE_*` flags) |
| **Staging** | **UNKNOWN — VERIFY WITH TEAM** (likely separate Railway/Vercel preview + flags doc in FINANCE staging docs) |
