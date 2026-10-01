# 02 — Architecture

Facts below are derived from `backend/app/main.py`, `backend/app/api/v1/router.py`, `frontend/src/lib/apiClient.js`, `vercel.json`, and [docs/ARCHITECTURE.md](../ARCHITECTURE.md).

---

## High-level system architecture

```mermaid
flowchart TB
  subgraph browsers [Browser clients]
    TH[Therapist SPA]
    AD[Admin / CM / Finance / HR SPA]
    PA[Parent SPA]
  end

  subgraph vercel [Vercel - frontend project only]
    UI[Static Vite build]
    RW["/api rewrite → Railway"]
  end

  subgraph railway [Railway - case-manager-new API]
    API[FastAPI Uvicorn]
    MW[CORS + Request ID middleware]
    RBAC[Auth deps + RBAC + module gates]
  end

  subgraph data [Data & infra]
    PG[(PostgreSQL)]
    RD[(Redis)]
    R2[(Cloudflare R2)]
    SMTP[ZeptoMail SMTP]
  end

  TH --> UI
  AD --> UI
  PA --> UI
  UI --> RW
  RW --> API
  TH -->|local dev proxy| API
  API --> MW --> RBAC
  RBAC --> PG
  RBAC --> RD
  RBAC --> R2
  RBAC --> SMTP
```

**Inference:** On `www.insighte.org`, the browser often calls **same-origin** `/api/...`; Vercel rewrites to the Railway API. Locally, Vite dev server proxies `/api` and `/health` to `localhost:8000` when `VITE_API_URL` is empty.

---

## Application tiers

### Frontend (single SPA, multiple portals)

- **Entry:** `frontend/src/main.jsx` → `AppRoutes.jsx`  
- **Portals:** `therapist`, `admin` (includes CM/finance/HR routes), `parent`  
- **State:** React Context (`AuthContext`), TanStack Query for server state  
- **API:** `apiFetch()` in `frontend/src/lib/apiClient.js` — Bearer access token, refresh flow, 30s timeout  

### Backend (monolithic FastAPI)

- **Entry:** `backend/app/main.py` — lifespan bootstrap, exception handlers, CORS  
- **Routes:** Aggregated in `backend/app/api/v1/router.py` under prefix **`/api/v1`**  
- **Layers:** Routers → services (`backend/app/services/*`) → SQLAlchemy models → Postgres/SQLite  
- **Cross-cutting:** `app/core/security.py`, `app/core/permissions.py`, `app/core/module_access.py`, audit via `app/core/audit.py`  

### Database

- **ORM:** SQLAlchemy 2.0 declarative models in `backend/app/models/`  
- **Migrations:** Alembic in `backend/alembic/versions/` (many revisions; CI enforces **single head**)  
- **Local SQLite:** `bootstrap_schema()` + `ensure_sqlite_schema_patches()` on startup  

### Optional subsystems

| Subsystem | When active | Mount point |
|-----------|-------------|-------------|
| Integration API | `INTEGRATION_API_ENABLED=true` | `/api/v1/integrations/*` |
| MCP server | `MCP_ENABLED=true` + integration on | `/mcp` (Streamable HTTP) |
| Clinical reports | `ENABLE_CLINICAL_REPORTS_ENGINE=true` | clinical report routers |
| Billing routers | `ENABLE_BILLING=true` | finance_ops, ledger_billing, client_billing, etc. |

---

## Request / response flow (typical authenticated call)

```mermaid
sequenceDiagram
  participant UI as React
  participant API as FastAPI
  participant Dep as get_current_user
  participant Svc as Service layer
  participant DB as SQLAlchemy / DB

  UI->>API: HTTP /api/v1/... Authorization Bearer
  API->>Dep: Validate JWT access token
  Dep->>DB: Load User + roles
  API->>API: Permission / module / case scope checks
  API->>Svc: Business logic
  Svc->>DB: Query / commit
  Svc-->>API: Result or domain error
  API-->>UI: JSON response
```

**Example trace (therapist submits log):**

1. `POST /api/v1/daily-logs` — `daily_logs.py` router  
2. `get_current_user` + therapist case access check  
3. `session_log_service` / related services persist `DailyLog`, link to `TherapySession`  
4. Audit event optional via `log_audit`  
5. Response schema from `app/schemas/`  

---

## Authentication flow

```mermaid
sequenceDiagram
  participant U as User browser
  participant UI as LoginPage
  participant API as /api/v1/auth
  participant R as Redis

  U->>UI: email + password + portal
  UI->>API: POST /auth/login
  API->>API: authenticate + portal allowlist
  API->>R: Store refresh token metadata
  API-->>UI: access_token + refresh_token + user
  UI->>UI: Persist tokens (memory/localStorage per AuthContext)
  Note over UI,API: Subsequent calls: Authorization header
  UI->>API: POST /auth/refresh when access expires
  API->>R: Validate refresh
  API-->>UI: New access (+ refresh rotation per implementation)
```

Logout revokes refresh in Redis (`revoke_refresh_token`). Production **requires** Redis; dev may use in-memory fallback after ~2s probe ([backend/README.md](../../backend/README.md)).

---

## Data flow (case-centric)

```mermaid
flowchart LR
  Case[Case]
  Assign[CaseAssignment / CaseService]
  Sess[TherapySession]
  Log[DailyLog]
  Rep[MonthlyReport]
  Inv[Invoice / ClientInvoice]
  Parent[Parent-visible APIs]

  Case --> Assign
  Assign --> Sess
  Sess --> Log
  Log --> Rep
  Log --> Inv
  Log -->|approve + visibility| Parent
  Rep -->|publish| Parent
```

Clinical parallel path: `CaseClinicalProfile`, `IepPlan`, `ClinicalReport`, `CaseDocument` — see [06_DATABASE.md](./06_DATABASE.md).

---

## Deployment architecture

```mermaid
flowchart LR
  GH[GitHub main branch]
  CI[GitHub Actions CI]
  VR[Vercel frontend deploy]
  RW[Railway API deploy]
  PG[(Railway Postgres)]
  RS[(Railway Redis)]

  GH --> CI
  GH --> VR
  GH --> RW
  RW --> PG
  RW --> RS
  VR -->|VITE_API_URL or rewrite| RW
```

- **Frontend build:** `npm run build` in `frontend/` (or monorepo root `vercel.json`).  
- **API build:** Docker `backend/Dockerfile`; start `scripts/start-production.sh` (migrate + uvicorn workers).  
- **Staging/testing:** **UNKNOWN — VERIFY WITH TEAM** for dedicated hostnames; repo references retired Vercel apps `insightecasestaging` / `insightecasetesting` that should be disconnected from Git.

---

## External services (summary)

| Service | Role |
|---------|------|
| Railway | API hosting, Postgres, Redis |
| Vercel | Frontend hosting, optional Analytics (`@vercel/analytics`) |
| Cloudflare R2 | Private object storage (report images, attachments) |
| ZeptoMail | Transactional email SMTP |
| Zoho Books | Optional invoice sync seam (`ZOHO_BOOKS_*` flags) |
| Razorpay | Payout provider stub (`PAYOUT_PROVIDER=RAZORPAY`) |
| Policies bot | External URL (`POLICIES_BOT_URL`) linked from support UI |
| Google Calendar | `ctz` and calendar connection models — invite links |

Full integration doc: [13_THIRD_PARTY_INTEGRATIONS.md](./13_THIRD_PARTY_INTEGRATIONS.md).

---

## AI / LLM

**Fact:** No LLM API client found in `backend/requirements.txt` or common service imports. IEP “suggestions” and report tooling appear **rule/template and structured UI driven**; any future AI must follow `.cursorrules` (Layer 4, explicit buttons only).

**Inference:** Product vision includes clinical intelligence; current shipped code is predominantly **relational + structured forms**.

---

## Background jobs and cron

**Fact:** No Celery worker in repo. Scheduled/ops scripts live under `backend/scripts/` (e.g. `auto_close_sessions_day_end.py`, migration utilities) — typically run via **external scheduler** (Railway cron, manual, or **UNKNOWN — VERIFY WITH TEAM**).

---

## Logging and errors

- Request ID middleware: `app/core/request_middleware.py`  
- DB errors mapped to HTTP via handlers in `main.py` (`IntegrityError`, `OperationalError`)  
- User-facing DB detail gated by `expose_db_errors` (off in production)  
- Health: `GET /health` — DB, Redis, SMTP configured, migration revision  

---

## Communication summary

| From | To | Protocol |
|------|-----|----------|
| Browser | Vercel CDN | HTTPS static assets |
| Browser | API | HTTPS JSON REST `/api/v1/*` |
| API | Postgres | SQLAlchemy / psycopg2 |
| API | Redis | refresh token store |
| API | R2 | S3-compatible API (boto3) |
| API | SMTP | ZeptoMail |
| Integration clients | API | `/api/v1/integrations/*` + JWT (`INTEGRATION_JWT_SECRET_KEY`) |
