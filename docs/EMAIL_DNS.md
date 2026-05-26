# Transactional email — DNS, Railway, and Vercel (test/staging)

## Sender addresses (Insighte)

| Address | Used for |
|---------|----------|
| `noreply@insighte.in` | Portal invites, reports, booking, leave, general alerts |
| `billing.noreply@insighte.in` | Invoices, payment reminders |
| `verification.noreply@insighte.in` | Password reset, security / OTP (future) |

Add all three as allowed senders in **ZeptoMail → Domains → insighte.in** (or they will bounce).

Backend env (Railway API only):

```env
SMTP_FROM_EMAIL=noreply@insighte.in
SMTP_FROM_BILLING_EMAIL=billing.noreply@insighte.in
SMTP_FROM_VERIFICATION_EMAIL=verification.noreply@insighte.in
SMTP_FROM_NAME=Insighte
```

## Security

- Store `SMTP_PASSWORD` only in Railway (or local `.env`, never committed).
- Rotate ZeptoMail send tokens if they were exposed.
- Do **not** set SMTP variables on Vercel (frontend).

## Manual setup checklist

### 1. ZeptoMail

- [ ] Domain `insighte.in` verified
- [ ] SMTP credential created (`smtp.zeptomail.com`, port `587`, user `emailapikey`)
- [ ] All three sender addresses authorized in the console
- [ ] Send a test from ZeptoMail UI to confirm DNS

### 2. Cloudflare (`insighte.in`)

Copy records from **ZeptoMail → Domains → insighte.in → DNS**.

| Step | Type | Name | Notes |
|------|------|------|--------|
| 1 | TXT | `@` | SPF include from ZeptoMail — **add** alongside existing SPF; do not delete Hostinger business mail SPF/MX without a migration plan |
| 2 | CNAME/TXT | DKIM host | ZeptoMail DKIM value |
| 3 | TXT | `_dmarc` | e.g. `v=DMARC1; p=none; rua=mailto:dmarc@insighte.in` |
| 4 | CNAME | Bounce/MAIL FROM | If ZeptoMail provides one |

### 3. Railway (FastAPI API)

| Variable | Example (test/staging) |
|----------|-------------------------|
| `APP_ENV` | `production` |
| `EMAIL_PROVIDER` | `zeptomail` |
| `SMTP_HOST` | `smtp.zeptomail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | `emailapikey` |
| `SMTP_PASSWORD` | *(secret — rotated token)* |
| `SMTP_TLS` | `true` |
| `SMTP_FROM_EMAIL` | `noreply@insighte.in` |
| `SMTP_FROM_BILLING_EMAIL` | `billing.noreply@insighte.in` |
| `SMTP_FROM_VERIFICATION_EMAIL` | `verification.noreply@insighte.in` |
| `SMTP_FROM_NAME` | `Insighte` |
| `FRONTEND_URL` | Your **Vercel test URL**, e.g. `https://your-app.vercel.app` (no trailing slash) |
| `CORS_ORIGINS` | Same Vercel URL + `http://localhost:5173` for local dev |

After env is set:

1. Deploy / redeploy API
2. Confirm migration: `email_logs` table exists (`alembic upgrade head`)
3. `curl https://YOUR-RAILWAY-API/health`

### 4. Vercel (React frontend)

| Variable | Value |
|----------|--------|
| `VITE_API_URL` | Public Railway API URL (no trailing slash) |

No SMTP keys on Vercel.

Redeploy frontend after changing `VITE_API_URL`.

## Product flows (already in app)

| Flow | UI | API | From address |
|------|-----|-----|----------------|
| Sign in | `/login` | `POST /api/v1/auth/login` | — |
| Forgot password | `/login` → Forgot password → `/forgot-password` | `POST /api/v1/auth/forgot-password` | `verification.noreply@insighte.in` |
| Reset password | Email link → `/reset-password/:token` | `POST /api/v1/auth/reset-password` | — |
| Staff invite | Admin/HR onboard or invite | `POST /api/v1/admin/therapists/onboard`, `POST /api/v1/admin/therapists/invite` | `noreply@insighte.in` |
| Accept invite | `/invite/:token` | `POST /api/v1/auth/accept-invite` | — |
| Parent invoice | Admin notify | `POST .../invoices/{id}/notify-parent` | `billing.noreply@insighte.in` |

Invite emails send when `send_email: true` (default on admin invite/onboard).

## Local SMTP test script (no secrets in repo)

From `backend/` after exporting `SMTP_*` vars (or Railway `railway run`):

```bash
python3 scripts/send_test_email.py --to your@inbox.com --template password_reset
python3 scripts/send_test_email.py --to your@inbox.com --from-email verification.noreply@insighte.in --template portal_invite
```

Railway variable batch (project `b5944bdb-23e6-4d32-bf7e-f2eeb9494ca4`): see [`docs/RAILWAY_VERCEL.md`](RAILWAY_VERCEL.md), [`backend/scripts/railway_link_and_configure.example.sh`](../backend/scripts/railway_link_and_configure.example.sh), or [`backend/scripts/railway_smtp_env.example.sh`](../backend/scripts/railway_smtp_env.example.sh).

## Verify mail is working

1. **API health:** `GET /health` on Railway → `ok` (current prod: `https://case-manager-new-production.up.railway.app/health`)
2. **Forgot password:** Use a real user email on the Vercel test site → check inbox from `verification.noreply@insighte.in` → link must open `https://YOUR-VERCEL-APP/reset-password/...`
3. **Invite:** Admin → onboard therapist with “send email” → inbox from `noreply@insighte.in` → `/invite/...` on Vercel
4. **Database:** On Railway Postgres, `SELECT event_type, recipient_email, status, error_message FROM email_logs ORDER BY id DESC LIMIT 10;`
   - `sent` = delivered or noop (SMTP unset)
   - `failed` = check `error_message` and Railway logs
5. **Local dev without SMTP:** API logs `[email] noop delivery...` and `email_logs.provider = noop`

## Common failures

| Symptom | Fix |
|---------|-----|
| CORS error on login | Add Vercel URL to Railway `CORS_ORIGINS` |
| Reset link goes to localhost | Set Railway `FRONTEND_URL` to Vercel test URL |
| 401 / network on frontend | Set Vercel `VITE_API_URL` to Railway API |
| Email not received, log `failed` | Wrong SMTP password, unverified sender, or DNS not propagated |
| Email “sent” in logs but not inbox | Check spam; verify DKIM/SPF in ZeptoMail domain status |

## MCP / CLI limits (what agents cannot do here)

| Platform | Automated from Cursor | You do manually |
|----------|----------------------|-----------------|
| **ZeptoMail** | — | Domain + senders (you completed) |
| **Cloudflare** | No DNS MCP in workspace | SPF/DKIM if not already green in ZeptoMail |
| **Railway** | `railway login` required | Set env vars via dashboard or `railway_smtp_env.example.sh` |
| **Vercel** | List projects only | `VITE_API_URL` + redeploy for `frontend-omega-eight-92` (or your test project) |

**Production API note:** Deployed Railway build may lag the repo (e.g. no `/forgot-password` until latest backend is deployed). After deploy, run `alembic upgrade head` for `email_logs`.

## Deployment summary

| Layer | Action |
|-------|--------|
| Code | Deploy backend with email package + migration |
| Postgres | `alembic upgrade head` |
| Railway | SMTP + `FRONTEND_URL` + `CORS_ORIGINS` |
| Cloudflare | ZeptoMail SPF/DKIM/DMARC (additive) |
| Vercel | `VITE_API_URL` only |
