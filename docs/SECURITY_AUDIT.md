# InsighteCase — Security audit (code & configuration review)

| Field | Value |
|-------|--------|
| **Audit date** | 2026-10-06 |
| **Scope** | Monorepo: `backend/` (FastAPI), `frontend/` (Vite/React), deploy config (`vercel.json`, env templates) |
| **Method** | Static review of auth/RBAC, API surface, storage, headers, dependency advisories, and production guards. **Not** a penetration test, red-team exercise, or formal compliance assessment. |
| **Related docs** | [handover/19_SECURITY.md](./handover/19_SECURITY.md), [handover/10_AUTHENTICATION_AND_AUTHORIZATION.md](./handover/10_AUTHENTICATION_AND_AUTHORIZATION.md), [RBAC_SCOPE.md](./RBAC_SCOPE.md), [ENVIRONMENT_VARIABLES.md](./ENVIRONMENT_VARIABLES.md) |

---

## Executive summary

InsighteCase handles **child and family clinical data**. The backend has meaningful **production startup guards** (secrets, Postgres, Redis, R2, CORS) and **server-side RBAC** with case scoping on many sensitive paths. The largest practical risks in this review are:

1. **Browser token storage** (access/refresh JWTs in `localStorage`) — any XSS becomes full account compromise.
2. **Incomplete HTML sanitization** on some IEP preview surfaces — stored XSS if untrusted HTML reaches the DOM.
3. **Missing defense-in-depth headers** (CSP, HSTS, frame controls) on the Vercel UI.
4. **Authentication hardening gaps** — no login rate limiting and a **6-character minimum password**.
5. **Operational exposure** — public OpenAPI (`/docs`), verbose `/health`, and demo-oriented login routes shipped in the production frontend bundle.
6. **Dependency advisories** — frontend `npm audit` reports **31** issues (3 high), notably **TipTap** (rich-text editor used for clinical content).

No single finding in this review proves an unauthenticated remote takeover of production **by itself**, but combined XSS + token storage and weak credential policy are the highest-priority fix themes before scaling users or PHI volume.

---

## Severity scale

| Level | Meaning |
|-------|---------|
| **Critical** | Likely unauthenticated compromise of production data or systems, or trivial full-account takeover at scale. |
| **High** | Authenticated misuse, XSS → account takeover, or broad data exposure with realistic exploit path. |
| **Medium** | Defense gaps, information disclosure, or abuse that requires chaining or insider access. |
| **Low** | Hardening, hygiene, or latent risk with limited blast radius. |

---

## Findings summary

| ID | Severity | Area | Finding | Primary location |
|----|----------|------|---------|------------------|
| SEC-001 | High | Session | JWT access + refresh tokens stored in `localStorage` | `frontend/src/lib/apiClient.js` |
| SEC-002 | High | XSS | IEP preview renders server HTML via `dangerouslySetInnerHTML` without DOMPurify | `frontend/src/components/admin-portal/IepBuilderPanel.jsx` |
| SEC-003 | High | Headers | No CSP, HSTS, `X-Frame-Options`, or `Referrer-Policy` on UI deploy | `frontend/vercel.json` |
| SEC-004 | High | Auth | No rate limiting on `POST /auth/login` (credential stuffing / brute force) | `backend/app/api/v1/auth.py` |
| SEC-005 | High | Auth | Minimum password length **6** (admin set-password, reset, schemas) | `backend/app/schemas/user.py`, admin routes |
| SEC-006 | High | Supply chain | TipTap / `@tiptap/core` advisories (proto/DOM + ReDoS) | `frontend/package-lock.json` (`npm audit`) |
| SEC-007 | Medium | API surface | OpenAPI Swagger UI enabled at `/docs` (default FastAPI) | `backend/app/main.py` |
| SEC-008 | Medium | Disclosure | `/health` exposes DB migration revision, Redis ping, SMTP config flag | `backend/app/main.py` |
| SEC-009 | Medium | CORS | Production allows regex `frontend*.vercel.app` — any matching preview host | `backend/app/core/config.py` |
| SEC-010 | Medium | Disclosure | DB error technical details enabled for `staging` / `testing` env | `backend/app/core/config.py` |
| SEC-011 | Medium | Uploads | Ticket/incident uploads trust client `Content-Type` (no magic-byte check) | `ticket_attachment_service.py`, `incident_attachment_service.py` |
| SEC-012 | Medium | Integrations | Client-credentials token endpoint has no global brute-force limit | `backend/app/api/v1/integrations.py` |
| SEC-013 | Medium | Prod UX | `/devlogin` and `?demo=true` demo login affordances in production build | `frontend/src/routes/AppRoutes.jsx`, `LoginPage.jsx` |
| SEC-014 | Medium | Data at rest | Invite tokens stored **plaintext** in DB (unlike password-reset hashes) | `backend/app/models/user.py` (`InviteToken`) |
| SEC-015 | Low | Crypto docs | Handover mentions bcrypt; runtime uses **pbkdf2_sha256** (passlib) | `backend/app/core/security.py` |
| SEC-016 | Low | Integration | If integration secret unset, code falls back to user JWT secret (dev only; blocked when MCP enabled in prod) | `integration/auth_service.py`, `production_checks.py` |
| SEC-017 | Low | Abuse | `POST /auth/request-status-restore` accepts password + creates HR ticket (ticket spam if passwords known) | `backend/app/api/v1/auth.py` |

---

## Detailed findings and remediation

### SEC-001 — JWTs in `localStorage` (High)

**Risk:** Any XSS (including supply-chain or unsanitized HTML) can read `access_token` and `refresh_token` and exfiltrate them. Attacker obtains session-equivalent access until refresh revocation or password change.

**Evidence:** Tokens are read/written in `localStorage` (`access_token`, `refresh_token`) in `frontend/src/lib/apiClient.js`.

**Fix (choose one strategy; can be phased):**

1. **Short term:** Strict **Content-Security-Policy**, sanitize **all** HTML render paths (see SEC-002), upgrade TipTap (SEC-006), and run periodic **DOM XSS** checks on report/IEP flows.
2. **Medium term:** Move refresh token to **HttpOnly, Secure, SameSite** cookie; keep access token in memory only (or short-lived cookie). Adjust CORS/credentials and refresh route accordingly.
3. **Operational:** Shorter access TTL in production; monitor audit logs for anomalous `login` / geo / user-agent; optional step-up auth for admin/finance actions.

**Acceptance criteria:** Documented token strategy; CSP deployed; no unsanitized `dangerouslySetInnerHTML` on user-controlled HTML.

---

### SEC-002 — Unsanitized IEP preview HTML (High)

**Risk:** Stored XSS in admin/CM browser if report/IEP HTML contains scripts or event handlers.

**Evidence:** `ReportHtmlView` uses DOMPurify via `sanitizeReportHtml` / `hydrateReportImages` (`frontend/src/lib/reportHtml.js`). **IEP builder preview** sets `previewHtml` from API and renders:

```jsx
dangerouslySetInnerHTML={{ __html: previewHtml }}
```

without calling `sanitizeReportHtml` (`IepBuilderPanel.jsx`).

**Fix:**

1. Wrap all preview HTML with `sanitizeReportHtml(previewHtml)` before render (same config as reports).
2. **Server-side:** Optionally sanitize HTML on save/publish (defense in depth) using a vetted HTML cleaner on the API.
3. Add a regression test: payload `<img src=x onerror=alert(1)>` must not execute in preview.

---

### SEC-003 — Missing security headers on frontend (High)

**Risk:** Clickjacking, MIME sniffing, weak referrer leakage, and no CSP backstop for XSS.

**Evidence:** `frontend/vercel.json` only sets `Permissions-Policy: geolocation=(self)`.

**Fix (Vercel `headers` example — tune for your CDN/API proxy):**

| Header | Suggested starting value |
|--------|-------------------------|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains; preload` (after HTTPS confirmed everywhere) |
| `Content-Security-Policy` | default-src 'self'; script-src 'self'; connect-src 'self' https://api.insighte.org; img-src 'self' blob: data: https:; frame-ancestors 'none'; upgrade-insecure-requests |
| `X-Frame-Options` | `DENY` (or rely on CSP `frame-ancestors`) |
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |

Iterate CSP in **report-only** mode first if needed; allowlist TipTap/Vite inline requirements explicitly rather than `unsafe-inline` long term.

---

### SEC-004 — No login rate limiting (High)

**Risk:** Online password guessing and credential stuffing against known emails (therapists, parents, staff).

**Evidence:** `POST /api/v1/auth/login` authenticates immediately with no IP/email throttle (`backend/app/api/v1/auth.py`). Password reset **is** rate limited (`password_reset_service.py`).

**Fix:**

1. Add Redis-backed limits: e.g. **10 failures / 15 min / IP** and **5 failures / 15 min / email** (adjust for NAT/shared offices).
2. Return generic `401 Invalid credentials` (already done); optionally introduce increasing delay (connection-before-correction copy, not “locked out”).
3. Log audit events for repeated failures; alert on spikes.
4. Consider Cloudflare/WAF or Railway edge rate limits in front of `/api/v1/auth/*`.

---

### SEC-005 — Weak password policy (High)

**Risk:** Short or common passwords for accounts with access to PHI and finance.

**Evidence:** `Field(min_length=6)` on passwords; reset endpoint checks `len(payload.password) < 6`; admin UI prompt enforces 6 chars (`PeopleRowActions.jsx`).

**Fix:**

1. Raise minimum to **12+** characters (or NIST-style min 8 with breach check).
2. Enforce on: registration, reset, admin set-password, therapist onboarding.
3. Optional: integrate **Have I Been Pwned** k-anonymity API on password set (Layer 1, no LLM).
4. Require **MFA** for `SUPER_ADMIN`, `FINANCE`, and integration admin actions (roadmap).

---

### SEC-006 — Frontend dependency vulnerabilities (High)

**Risk:** Editor and toolchain CVEs can become XSS or DoS in the browser during report/IEP editing.

**Evidence:** On 2026-10-06, `npm audit` (frontend) reported **31 vulnerabilities (28 moderate, 3 high)**, including **@tiptap/core** GHSA-cp6q-959q-f8rh and GHSA-j95f-988m-3j2f.

**Fix:**

1. Run `npm audit` / `npm audit fix` in `frontend/`; upgrade TipTap to patched versions per advisory.
2. Add **`npm audit --audit-level=high`** (or OSV) to CI; block merges on high/critical unless documented exception.
3. Pin lockfile; review Dependabot/Renovate PRs weekly.

**Backend:** `pip audit` was unavailable in the audit environment; run in CI with `pip-audit` or GitHub Dependabot for Python.

---

### SEC-007 — Public OpenAPI `/docs` (Medium)

**Risk:** Attackers map all routes, schemas, and admin/integration endpoints without authentication.

**Evidence:** FastAPI app created without disabling docs; root JSON advertises `"docs": "/docs"` (`backend/app/main.py`).

**Fix:**

1. Production: `FastAPI(docs_url=None, redoc_url=None, openapi_url=None)` when `APP_ENV=production`, **or**
2. Protect `/docs` with network ACL, basic auth at reverse proxy, or VPN-only access.
3. Keep OpenAPI enabled in staging for developer productivity.

---

### SEC-008 — Verbose public `/health` (Medium)

**Risk:** Reconnaissance (Alembic revision, Redis reachability, email provider hints).

**Fix:**

1. Split **liveness** (`/health/live` → `{status: ok}`) vs **readiness** (auth or internal network only).
2. Remove migration revision from public responses; expose detailed checks on admin/metrics endpoint behind auth.

---

### SEC-009 — Broad CORS origin regex (Medium)

**Risk:** Any attacker-controlled Vercel project matching `frontend*.vercel.app` under the team pattern could theoretically host a malicious origin if combined with misconfiguration and credentialed requests.

**Evidence:** `cors_origin_regex_effective` in production (`backend/app/core/config.py`).

**Fix:**

1. Prefer explicit `CORS_ORIGINS` list (production + known preview patterns).
2. Narrow regex to exact project naming convention; avoid wildcard team previews in production API.
3. Review `allow_credentials=True` — required for cookie-based auth if adopted; with Bearer-only, credentials flag is less necessary but still increases CORS sensitivity.

---

### SEC-010 — Staging DB error detail exposure (Medium)

**Risk:** SQL fragments leak schema/table names to clients when `APP_ENV` is `staging` or `testing`.

**Evidence:** `expose_db_error_detail` returns true for those envs (`config.py`).

**Fix:** Default `expose_db_errors=false` everywhere except local dev; log full detail server-side only.

---

### SEC-011 — Upload MIME trust (Medium)

**Risk:** Malicious file uploaded as `image/jpeg` with executable content; depends on downstream handling (download, preview, support staff workstation).

**Evidence:** Allowlist checks `UploadFile.content_type` only (`ticket_attachment_service.py`).

**Fix:**

1. Validate magic bytes (`filetype` library or minimal signatures for JPEG/PNG/PDF).
2. Strip EXIF where not needed; serve downloads with `Content-Disposition: attachment` and correct `Content-Type` from detected type.
3. Optional: async malware scan for support attachments (ClamAV bucket trigger).

Object keys already use `safe_filename` + UUID (`backend/app/storage/keys.py`) — good path traversal control.

---

### SEC-012 — Integration token endpoint brute force (Medium)

**Risk:** When `INTEGRATION_API_ENABLED=true`, `/integrations/oauth/token` accepts client id/secret without global throttling (per-client limits apply **after** token issuance on other routes).

**Fix:**

1. Rate limit by IP + `client_id` on token endpoint (lockout/backoff).
2. Monitor `integration.token_issued` audit events; alert on failures.
3. Keep integration disabled in production until required ([INTEGRATIONS_MCP.md](./INTEGRATIONS_MCP.md)).

---

### SEC-013 — Demo login routes in production bundle (Medium)

**Risk:** `/devlogin` and `?demo=true` simplify discovery of demo workflows; dangerous if weak/default accounts exist in a misconfigured environment.

**Evidence:** Routes and demo UI in `AppRoutes.jsx` / `LoginPage.jsx`. Production blocks demo **seed** (`production_checks.py`) but imported users may still have weak passwords.

**Fix:**

1. Gate demo UI behind `import.meta.env.DEV` or explicit `VITE_ENABLE_DEMO_LOGIN=false` in production Vercel env (default off).
2. Remove or 404 `/devlogin` in production builds.
3. Enforce strong passwords on all production imports ([DATA_IMPORT.md](./DATA_IMPORT.md)).

---

### SEC-014 — Plaintext invite tokens (Medium)

**Risk:** DB backup leak or SQL injection (ORM makes this unlikely) exposes usable invite links.

**Fix:** Store `sha256(token)` like password reset; compare hash on accept; single-use + expiry already partially modeled.

---

### SEC-015 — Documentation vs hashing algorithm (Low)

Update [handover/19_SECURITY.md](./handover/19_SECURITY.md) to state **pbkdf2_sha256** via passlib (`security.py`), not bcrypt, unless migrated intentionally.

---

### SEC-016 — Integration JWT secret fallback (Low)

**Fix:** Remove fallback to `jwt_secret_key` in `_integration_secret()`; require explicit `INTEGRATION_JWT_SECRET_KEY` whenever integration routes are mounted (production check already partial).

---

### SEC-017 — Status restore ticket creation (Low)

**Fix:** Rate limit by IP; CAPTCHA only if abuse observed; require employment block code match before ticket creation.

---

## Controls working well (keep and extend)

| Control | Notes |
|---------|--------|
| **Production startup guards** | JWT defaults, SQLite, local storage, Redis, CORS, R2 validation (`production_checks.py`) |
| **Refresh token rotation + Redis revocation** | Logout and refresh invalidate prior JTIs (`security.py`, `auth.py`) |
| **Portal-scoped login** | Reduces cross-portal token reuse (`portal_login_service.py`) |
| **Password reset** | Hashed tokens, expiry, per-email rate limit |
| **Case/ticket/incident access checks** | Download paths check scope (`case_scope_check`, attachment services) |
| **Private object storage** | R2 keys; API-mediated download (not public buckets) |
| **Structured RBAC + module write guards** | `module_write.py`, `require_mutation_permission` |
| **Audit logging** | Login and many mutations logged |
| **Parent API data minimization** | Internal fields stripped in parent serializers (see handover security doc) |
| **Forgot-password response** | Uniform response reduces email enumeration (verify `request_password_reset` always returns success message) |

---

## Remediation roadmap (recommended order)

### Phase 0 — Quick wins (1–2 weeks)

- [ ] Sanitize IEP preview HTML (SEC-002).
- [ ] Add baseline security headers on Vercel (SEC-003); iterate CSP.
- [ ] Upgrade TipTap / run `npm audit fix` (SEC-006); add CI audit gate.
- [ ] Disable or protect `/docs` in production (SEC-007).
- [ ] Trim public `/health` fields (SEC-008).
- [ ] Hide demo/dev login in production builds (SEC-013).

### Phase 1 — Authentication hardening (2–4 weeks)

- [ ] Login rate limiting (SEC-004).
- [ ] Password policy ≥ 12 chars + common-password block (SEC-005).
- [ ] Integration token endpoint rate limits (SEC-012).
- [ ] Upload magic-byte validation (SEC-011).

### Phase 2 — Session & XSS architecture (4–8 weeks)

- [ ] CSP hardened; audit all `dangerouslySetInnerHTML` usages.
- [ ] Evaluate HttpOnly refresh cookie + in-memory access token (SEC-001).
- [ ] Hash invite tokens at rest (SEC-014).
- [ ] MFA for privileged roles (finance, super admin, integration admins).

### Phase 3 — Assurance & compliance (ongoing)

- [ ] Third-party penetration test focused on IDOR, XSS, and auth.
- [ ] Dependency scanning for Python (`pip-audit`) and npm in CI.
- [ ] Secret rotation runbook (JWT, integration, R2, SMTP).
- [ ] Formal data protection impact assessment for child/family PHI (legal/compliance — out of scope for this doc).

---

## Testing & verification checklist

After remediations:

1. Attempt XSS payloads in IEP preview and published report views (should not execute).
2. Verify `/docs` returns 404 or requires auth in production.
3. Run automated RBAC tests: `cd backend && python -m pytest app/tests/test_rbac_access.py app/tests/test_comprehensive_review.py -q`.
4. Confirm login throttle returns friendly messages without revealing account existence.
5. Scan production response headers (securityheaders.com or curl).
6. Re-run `npm audit` until high/critical resolved or waived with ticket reference.

---

## RBAC and IDOR notes

Automated tests cover many role combinations ([REVIEW_FINDINGS.md](./REVIEW_FINDINGS.md)), but **authorization is never “done”**:

- Any new router must use `require_permission`, `case_scope_check`, or module write guards.
- UI hiding alone is insufficient ([RBAC_SCOPE.md](./RBAC_SCOPE.md)).
- Recommended: add periodic **IDOR fuzz tests** (therapist A cannot read therapist B case by ID; parent cannot access other families’ cases).

---

## Compliance & data classification

The product processes **sensitive personal data about children and families**. This audit does **not** certify HIPAA, ISO 27001, or Indian DPDP compliance. Minimum operational expectations:

- Access logging and least-privilege roles.
- Encryption in transit (HTTPS) and at rest (Postgres/R2 provider defaults).
- Incident response process for suspected breach.
- Data retention and deletion aligned with contracts (case delete flows exist — verify backups and R2 lifecycle).

Confirm formal compliance targets with legal counsel.

---

## Document maintenance

| When | Action |
|------|--------|
| Major auth/RBAC change | Re-read SEC-001, SEC-004, SEC-005 |
| New HTML editor or report renderer | Re-read SEC-002, SEC-006 |
| New public route or integration | Re-read SEC-007, SEC-012 |
| Before production release | Run Phase 0 checklist + [RELEASE_CHECKLIST.md](./RELEASE_CHECKLIST.md) |

**Owner:** Engineering + security champion (assign in [TEAM_OWNERSHIP.md](./TEAM_OWNERSHIP.md)).

---

*This document supersedes informal security notes for vulnerability tracking; implementation details remain in [handover/19_SECURITY.md](./handover/19_SECURITY.md).*
