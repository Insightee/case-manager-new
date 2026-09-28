# 13 — Third-Party Integrations

Credentials always **[REDACTED]** in docs. Access management locations noted.

---

## Railway

| | |
|--|--|
| **Purpose** | Host FastAPI, Postgres, Redis |
| **Project** | Documented ID `ead85fb6-1826-4eed-bad9-2513e89c4854` in [DEPLOY.md](../DEPLOY.md) |
| **Service name** | `case-manager-new` (API) |
| **Config** | `backend/railway.toml`, `backend/Dockerfile`, `scripts/start-production.sh` |
| **Env** | All backend vars — [05_ENVIRONMENT_VARIABLES.md](./05_ENVIRONMENT_VARIABLES.md) |
| **CLI tokens** | `RAILWAY_API_TOKEN` (account), `RAILWAY_TOKEN` (project deploy only) |
| **Failure** | API down → UI cannot reach `/api`; health check fails |
| **Access** | Railway project membership — **transfer on handover** |

---

## Vercel

| | |
|--|--|
| **Purpose** | Static frontend hosting + `/api` rewrite to Railway on production domains |
| **Project** | Team `insightes-projects`, project **`frontend`** (`prj_ibo0tJpTFO1Y8d5cKiKicB7Yr6vN` per AGENTS.md) |
| **Config** | Root `vercel.json`, `frontend/` as app root |
| **Env** | **`VITE_API_URL`** (+ optional `VITE_*` flags) |
| **Analytics** | `@vercel/analytics` in frontend |
| **Domains** | `www.insighte.org`, `insighte.org`, legacy `frontend-omega-eight-92.vercel.app` |
| **Retired** | Projects `case-manager-new` (UI), `insightecasestaging`, `insightecasetesting` — disconnect from Git |
| **Failure** | UI loads but API errors if rewrite/`VITE_API_URL` wrong |
| **Access** | Vercel team — **`VERCEL_TOKEN`** for scripts |

Detail: [RAILWAY_VERCEL.md](../RAILWAY_VERCEL.md).

---

## GitHub

| | |
|--|--|
| **Purpose** | Source control, CI, PRs |
| **Repo** | `Insightee/case-manager-new` |
| **CI** | `.github/workflows/ci.yml` |
| **Branch protection** | [GITHUB_SETUP.md](../GITHUB_SETUP.md) |

---

## Cloudflare

| | |
|--|--|
| **Purpose** | DNS (email), **R2 object storage** |
| **R2 config** | `R2_*` env vars, `STORAGE_PROVIDER=r2` |
| **Docs** | [CLOUDFLARE_R2.md](../CLOUDFLARE_R2.md) |
| **Failure** | Upload/download of report images and attachments fails in prod |
| **Access** | Cloudflare account — bucket tokens distinct from account token |

---

## ZeptoMail (Zoho)

| | |
|--|--|
| **Purpose** | Transactional SMTP (invites, reset, reports, billing mail) |
| **Config** | `SMTP_*`, `EMAIL_PROVIDER=zeptomail` on Railway only |
| **DNS** | [EMAIL_DNS.md](../EMAIL_DNS.md) — SPF/DKIM/DMARC on `insighte.in` |
| **Failure** | Falls back to log-only if SMTP unset; emails in `email_logs` only |
| **Diagnosis** | `scripts/smtp_check.py`, [reports/email-delivery-diagnosis.md](../reports/email-delivery-diagnosis.md) |

---

## Zoho Books

| | |
|--|--|
| **Purpose** | Optional client invoice sync (Stage 2 seam) |
| **Config** | `ZOHO_BOOKS_API_KEY`, `ZOHO_BOOKS_LIVE_PUSH` |
| **Failure** | Visible “not configured” — no fake success |
| **Access** | Zoho org admin — **UNKNOWN — VERIFY WITH TEAM** |

---

## Razorpay

| | |
|--|--|
| **Purpose** | Payout provider adapter (stub) |
| **Config** | `PAYOUT_PROVIDER=RAZORPAY`, `PAYOUT_PROVIDER_LIVE` |
| **Failure** | Mock provider used when not live |
| **Access** | **UNKNOWN — VERIFY WITH TEAM** |

---

## Policies clarification bot

| | |
|--|--|
| **Purpose** | External link from support UI |
| **Config** | `POLICIES_BOT_URL`, `VITE_POLICIES_BOT_URL` |
| **Failure** | Link hidden or fallback URL unused |

---

## Google Calendar

| | |
|--|--|
| **Purpose** | Meeting invite links (`MEETING_INVITE_CALENDAR_TIMEZONE`); calendar connections in DB |
| **Models** | `UserCalendarConnection`, `CalendarProvider` |
| **OAuth secrets** | **UNKNOWN — VERIFY WITH TEAM** (grep `calendar` in config) |

---

## Bitrix24 / Zoho Sign / WhatsApp

Listed in root README as **phased integrations** — **no active integration found in backend requirements** as of this handover. Treat as roadmap unless code added later.

---

## MCP (Model Context Protocol)

| | |
|--|--|
| **Purpose** | Remote read-only MCP over HTTP at `/mcp` |
| **Config** | `MCP_ENABLED`, `INTEGRATION_API_ENABLED` |
| **Docs** | [INTEGRATIONS_MCP.md](../INTEGRATIONS_MCP.md) |

---

## Hostinger / business email

[EMAIL_DNS.md](../EMAIL_DNS.md) notes preserving Hostinger MX for business mail while ZeptoMail handles transactional subdomain senders.

---

## Production Postgres read-only role

[Cursor_Handover_Production_Readonly_Postgres.md](../Cursor_Handover_Production_Readonly_Postgres.md) — finance/cutover SELECT role; not application runtime.

---

## Integration failure behavior summary

| Integration | Degraded mode |
|-------------|----------------|
| Redis (prod) | **Process refuses to start** |
| Redis (dev) | In-memory refresh fallback |
| SMTP | Noop logging |
| R2 (prod misconfig) | **Process refuses to start** |
| Zoho Books | Explicit not-configured status |
| External bot/calendar | Feature degraded, core app continues |
