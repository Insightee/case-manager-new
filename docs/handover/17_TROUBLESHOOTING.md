# 17 — Troubleshooting

Format: **Problem → Symptoms → Cause → Diagnosis → Solution**

Mark **VERIFY BEFORE APPLYING** where repo docs do not confirm fix.

---

## Backend will not start (production)

**Symptoms:** Railway crash loop; logs mention production checks.

**Cause:** `validate_production_settings()` rejects unsafe config ([`production_checks.py`](../../backend/app/core/production_checks.py)).

**Diagnosis:** Read startup logs for explicit message (demo seed, JWT defaults, SQLite, local storage, Redis localhost, CORS/FRONTEND_URL, R2).

**Solution:** Set `APP_ENV=production` only with Postgres, strong JWT secrets, `REDIS_URL`, `STORAGE_PROVIDER=r2` + R2 vars, real `CORS_ORIGINS` and `FRONTEND_URL`, `SEED_DEMO_DATA=false`.

---

## Login works locally but fails in production

**Symptoms:** 401 or timeout from UI.

**Cause:** Wrong API URL, CORS, or Redis refresh failure.

**Diagnosis:**

- Browser devtools → network → API host and CORS errors  
- `curl https://<API>/health`  
- Check `VITE_API_URL` on Vercel vs same-origin rewrite on `insighte.org`  

**Solution:** Align CORS with UI origin; ensure Redis connected (`health` shows `redis: ok`); verify user exists in prod DB (no accidental empty DB).

---

## CORS error in browser

**Symptoms:** `Access-Control-Allow-Origin` missing.

**Cause:** UI origin not in `CORS_ORIGINS`.

**Solution:** Add exact origin (scheme + host, no path) to Railway API env; redeploy API. For preview URLs, add each preview domain or use regex if configured.

---

## Frontend API calls timeout (30s)

**Symptoms:** Slow spinner; `apiClient` timeout.

**Cause:** Backend not running, wrong proxy, or blocking SQLite patch on first request.

**Diagnosis:** `curl localhost:8000/health`; confirm Vite proxy when `VITE_API_URL` empty.

**Solution:** Start uvicorn; start Redis locally for faster login; restart backend after schema pull.

---

## Wrong portal after login

**Symptoms:** Redirect to login with portal mismatch message.

**Cause:** User role not allowed on selected portal (`portal_login_service`).

**Solution:** Use correct URL (`/therapistlogin`, `/adminlogin`, `/clientlogin`); fix user roles in admin People.

---

## Alembic multiple heads

**Symptoms:** CI fails `alembic heads`; migrate script errors.

**Cause:** Parallel migration branches on `main`.

**Solution:** Merge revisions into single head per [CONTRIBUTING.md](../../CONTRIBUTING.md); never hand-author duplicate revision IDs.

---

## Schema drift errors in logs

**Symptoms:** `product_billing_rule_id missing` or 500s after git pull.

**Cause:** SQLite patches not applied or Postgres migration not run.

**Diagnosis:** `GET /health` `db_migration`; local restart uvicorn; prod run `migrate_production.py`.

**Solution:** `PYTHONPATH=.:alembic alembic upgrade head` on Postgres; restart API on SQLite.

---

## Email not sent (invites/reset)

**Symptoms:** No mail; `email_logs` provider `noop`.

**Cause:** `SMTP_HOST` or `SMTP_PASSWORD` unset.

**Diagnosis:** `GET /health` → `smtp_configured`; run `python3 scripts/smtp_check.py`.

**Solution:** Configure ZeptoMail on Railway; verify DNS [EMAIL_DNS.md](../EMAIL_DNS.md).

---

## Upload fails (report image / attachment)

**Symptoms:** 413 or 500 on upload.

**Cause:** `MAX_UPLOAD_BYTES`, ticket limits, or R2 misconfiguration in prod.

**Diagnosis:** Check env sizes; API logs; R2 credentials.

**Solution:** Fix R2 vars; ensure `STORAGE_PROVIDER` matches environment.

---

## Billing/finance endpoints 404

**Symptoms:** Admin finance UI errors, API 404.

**Cause:** `ENABLE_BILLING=false` — routers not mounted.

**Solution:** Enable flag on API **and** matching Vite flags for UI; follow finance cutover runbook — do not enable ledger writes without review.

---

## Docker Compose API exits on migrate

**Symptoms:** `alembic upgrade head` failure in container.

**Cause:** Migration conflict or Postgres not healthy.

**Diagnosis:** `docker compose logs api postgres`.

**Solution:** Fix migration head; wipe volume **only on dev** if acceptable.

---

## Playwright E2E flaky

**Symptoms:** Intermittent login or timeout in CI/local.

**Cause:** Race on lazy routes or API not ready.

**Solution:** Run with backend up; use `test:e2e:ui` to debug; check playwright config base URL.

---

## PATCH requests fail on insighte.org

**Symptoms:** Body lost on case updates.

**Cause:** Apex domain redirect stripping body **(documented in apiClient)**.

**Solution:** Use `www.insighte.org`; apiClient already forces www for apex host.

---

## Demo login fails after DB change

**Symptoms:** Invalid credentials for demo users.

**Solution:** Re-run `python3 -m app.seed.demo_seed` on dev DB **VERIFY BEFORE APPLYING on shared staging**.

---

## Railway CLI `whoami` fails with project token

**Symptoms:** Auth error using `RAILWAY_TOKEN`.

**Cause:** Project tokens cannot run account commands ([RAILWAY_VERCEL.md](../RAILWAY_VERCEL.md)).

**Solution:** Use `RAILWAY_API_TOKEN` with workspace “No workspace” for link/variables.

---

## Integration MCP mount fails

**Symptoms:** Log `MCP init failed` on startup.

**Cause:** `MCP_ENABLED` without dependencies or integration flag off.

**Solution:** Set `INTEGRATION_API_ENABLED=true`; check logs; disable `MCP_ENABLED` if not needed.

---

## Further help

- [docs/REVIEW_FINDINGS.md](../REVIEW_FINDINGS.md)  
- [docs/reports/production-e2e-latest.md](../reports/production-e2e-latest.md)  
- OpenAPI `/docs` for contract debugging  
