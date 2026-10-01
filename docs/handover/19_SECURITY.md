# 19 — Security

Documents **current implementation** — not a penetration test.

---

## Authentication

- Passwords hashed with bcrypt (passlib).  
- Access JWT (HS256) short-lived; refresh JWT separate secret.  
- Refresh tokens stored in Redis with revocation on logout.  
- Production **requires** Redis — prevents cross-worker refresh forgery and satisfies startup guard.  
- Portal-specific login reduces cross-portal token use.  
- Inactive employment blocks login with HR restore path.

---

## Authorization

- Server-side permission checks via `require_permission` and case/module scoping.  
- **Do not rely on UI hiding alone** — partial module write enforcement noted in RBAC docs.  
- Super Admin bypass explicit.  
- Integration API uses separate JWT secret and client credentials.

---

## Secrets management

- Secrets in Railway (API), not Vercel UI project.  
- Templates: `.env.example` — gitignored filled `.env`.  
- Deploy tokens (`RAILWAY_*`, `VERCEL_TOKEN`) for CLI only — not runtime.  
- Document values as **[REDACTED]** in handover.

---

## Transport

- HTTPS assumed for production UI and API.  
- SMTP STARTTLS on port 587 (`SMTP_TLS`).

---

## CORS

- Allowlist in `CORS_ORIGINS`; optional regex for Vercel preview patterns.  
- Production startup rejects localhost-only CORS when `APP_ENV=production`.

---

## Input validation

- Pydantic schemas on API inputs.  
- SQLAlchemy ORM parameterized queries — SQL injection risk low for ORM paths; raw SQL rare — audit any `text()` usage.  
- File uploads: size caps, MIME allowlists for tickets and report images.  
- Rich text: DOMPurify on frontend for rendered HTML — verify all render paths.

---

## XSS considerations

- TipTap editor content and report HTML — sanitize on display.  
- Avoid `dangerouslySetInnerHTML` without sanitizer (grep during changes).

---

## CSRF

- API uses Bearer tokens, not cookie session auth — classic CSRF less relevant.  
- If session cookies introduced, add CSRF tokens.

---

## File upload security

- Ticket attachments: count/size/type limits; stored under `uploads/tickets/` or R2 private keys.  
- Downloads authorized via ticket/case access checks on download endpoints.  
- R2 objects not public — streamed through API.

---

## API security

- OpenAPI exposed at `/docs` — **consider restricting in production** (not verified if disabled).  
- Integration rate limits when enabled (`INTEGRATION_DEFAULT_RATE_LIMIT_PER_MINUTE`).  
- Password reset rate limit per email per hour.

---

## Sensitive data

- Incidents and internal log fields excluded from parent APIs.  
- POSH/POCSO-style routing — role checks on incident endpoints.  
- Audit events for login and many mutations.  
- Avoid logging passwords or tokens — grep logging in auth paths when changing.

---

## Production startup guards

[`production_checks.py`](../../backend/app/core/production_checks.py) blocks:

- Demo seed on production  
- Default JWT secrets  
- SQLite database  
- Local storage provider  
- Missing/non-production Redis  
- Localhost CORS/frontend URL  
- Invalid R2 configuration  

---

## Areas requiring periodic review

| Area | Action |
|------|--------|
| JWT secret rotation | Process **UNKNOWN — VERIFY WITH TEAM** |
| RBAC partial enforcement | Complete ROLE_MODEL phases |
| `/docs` public exposure | Network or auth gateway |
| Dependency CVEs | npm/pip audit |
| R2 token scope | Minimum privilege keys |
| Email suppression list | `email_suppressions` table hygiene |
| Finance flags | Prevent accidental ledger writes |

---

## Compliance notes

- Product handles child and family data — treat as sensitive PII; access logging via audit tables.  
- Formal compliance certifications (HIPAA, etc.) — **UNKNOWN — VERIFY WITH TEAM**.
