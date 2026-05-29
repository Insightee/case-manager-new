# Email delivery diagnosis (2026-05-29)

## nickylalu@gmail.com

- **Local SQLite DB:** no `users`, `invite_tokens`, or `email_logs` rows (invite was not from this DB).
- **Likely cause for missing ZeptoMail log on local:** `SMTP_PASSWORD` was empty → `is_smtp_configured()` false → `email_logs.provider=noop`, no SMTP traffic.
- **Production:** new invite re-issued via API with `mode=invite`, `send_email=true` (invite_id 15). Invite URL on Vercel frontend.

## midhunnoble@gmail.com

- **Local:** `smtp_check.py` and `send_test_email.py --template portal_invite` succeeded.
- **Production:** therapist invite created (invite_id 14) with email enqueue on Railway API.

## Ops

- Rotate ZeptoMail token if it was exposed in chat; update Railway `SMTP_PASSWORD` and local `backend/.env` (gitignored).
- After deploy: `GET /health` → `smtp_configured: true` on API.
- Onboard API returns `email_delivery`: `queued` | `skipped_no_smtp` | `skipped_disabled` | `skipped_direct_mode`.
- Resend pending invites: `POST /api/v1/admin/invites/{id}/resend-email` or People UI **Resend email** (after deploy).
- Diagnose any address: `cd backend && python3 scripts/diagnose_invite_email.py <email>`
- Production API smoke (no local Postgres): `API_BASE_URL=https://case-manager-new-production.up.railway.app SMOKE_API_ONLY=1 SMOKE_TEST_EMAIL=you@example.com python3 scripts/production_smoke.py`
- Portal invite template test: `python3 scripts/send_test_email.py --to you@example.com --template portal_invite`

## Verification (2026-05-29)

- Local: `smtp_check.py` OK; `send_test_email.py --template portal_invite` → midhunnoble@gmail.com OK.
- Production API: pending invites for midhunnoble (id 14) and nickylalu (id 15); onboard smoke created invite id 17 with `send_email=true`.
- Production `/health` does not yet expose `smtp_configured` until Railway redeploys latest API.
