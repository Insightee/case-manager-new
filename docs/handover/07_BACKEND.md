# 07 — Backend

---

## Framework and entry point

| Item | Location |
|------|----------|
| Framework | FastAPI |
| App factory | `backend/app/main.py` |
| API prefix | `/api/v1` via `app/api/v1/router.py` |
| Settings | `backend/app/core/config.py` (`Settings` from env) |
| OpenAPI | `/docs`, `/redoc` |

---

## Application startup (lifespan)

Order in `_run_startup_bootstrap()` (`main.py`):

1. `validate_production_settings()` — fails fast on unsafe prod config  
2. `verify_redis_at_startup()` / warm Redis  
3. `bootstrap_schema()` — SQLite table creation  
4. `_repair_postgres_schema_drift()` — targeted Postgres fixes  
5. `_apply_sqlite_patches_if_needed()`  
6. `_maybe_seed_demo_on_empty_db()` if `SEED_DEMO_DATA`  
7. `_sync_missing_coded_roles()` — role registry  
8. `_verify_sqlite_writable()` — SQLite probe  
9. `_log_schema_health()` — ledger column warnings  
10. Optional MCP session manager if flags enabled  

---

## Routing structure

All v1 routers registered in `router.py`. Pattern:

```text
HTTP → api/v1/<router.prefix>/... → Depends(get_current_user | permissions) → service → models → JSON
```

Router modules (prefix relative to `/api/v1` unless noted):

| Module | Prefix | Tags / notes |
|--------|--------|--------------|
| `auth` | `/auth` | Login, refresh, me, invite, password reset |
| `cases` | `/cases` | Case CRUD, clinical profile, IEP, exports |
| `assignments` | `/cases/{case_id}/assignments` | Assignment history |
| `case_services` | `/cases/{case_id}/services` | Service lines |
| `sessions` | `/sessions` | Start/end/list sessions |
| `session_absence` | `/sessions` | Absence on sessions |
| `daily_logs` | `/daily-logs` | Log CRUD, approve, reject |
| `reports` | `/reports` | Monthly/observation reports |
| `clinical_reports` | case-scoped paths | Gated by `ENABLE_CLINICAL_REPORTS_ENGINE` |
| `invoices` | `/invoices` | Therapist invoices |
| `admin` | `/admin` | Dashboard, users, families, RBAC, exports |
| `finance_ops` | `/admin` | Finance overview, payouts (billing flag) |
| `finance_control_tower` | `/admin/...` | Control tower (billing flag) |
| `finance_writable` | `/admin/finance-writable/...` | Corrections (billing flag) |
| `ledger_billing` | `/admin/ledger-billing` | Ledger engine (billing flag) |
| `client_billing` | admin + parent routers | Client invoices (billing flag) |
| `parent` | `/parent` | Parent portal aggregate API |
| `therapist_portal` | `/therapist` | Dashboard stats, home |
| `therapist_profile` | `/therapist` | Profile, reviews |
| `booking`, `slots`, `scheduling` | respective | Appointments |
| `tickets`, `support`, `memos`, `incidents` | respective | Support hub |
| `leave`, `staff_attendance`, `hr`, `hr_ops` | respective | HR |
| `integrations` | `/integrations` | Machine API |
| `notifications` | `/notifications` | In-app notifications |
| `files`, `attachments`, `case_documents` | various | Upload/download |
| `meetings`, `calendar`, `users` | various | CM meetings, availability |

Exact paths: OpenAPI `/docs` or [09_API_REFERENCE.md](./09_API_REFERENCE.md).

---

## Layer responsibilities

| Layer | Directory | Responsibility |
|-------|-----------|----------------|
| Routers | `app/api/v1/` | HTTP validation, status codes, dependency injection |
| Schemas | `app/schemas/` | Pydantic I/O models |
| Services | `app/services/` | Business rules, transactions, notifications |
| Models | `app/models/` | SQLAlchemy tables |
| Core | `app/core/` | Auth, permissions, modules, flags, audit helpers |
| Storage | `app/storage/` | Local/R2 get/put/stream |

**Rule of thumb:** Keep routers thin; grep `app/services` for domain logic.

---

## Middleware

- `CORSMiddleware` — origins from `CORS_ORIGINS` + regex  
- `RequestIdMiddleware` — correlation ID  
- Exception handlers — DB integrity/operational errors → HTTP JSON  

---

## Authentication (backend)

- `app/services/auth_service.py` — password verify, token issue  
- `app/core/security.py` — JWT encode/decode, Redis refresh storage  
- `app/api/deps.py` — `get_current_user`, optional user loading with roles  

---

## Authorization

- `app/core/permissions.py` — `ROLE_PERMISSIONS`, `require_permission(...)`  
- `app/core/module_access.py` — programme module + feature overrides  
- Case scoping services: e.g. `case_portal_visibility.py`, assignment checks in routers  

See [10_AUTHENTICATION_AND_AUTHORIZATION.md](./10_AUTHENTICATION_AND_AUTHORIZATION.md).

---

## Error handling

- HTTPException for domain errors (401/403/404/422)  
- SQLAlchemy `IntegrityError` → user-safe message via `raise_db_integrity_http_error`  
- `OperationalError` → write failure messaging  
- Banned UX strings in product doctrine — backend still returns `detail` strings; frontend should map to friendly copy where implemented  

---

## Logging

- Standard Python `logging` logger `insightcase`  
- Startup schema/Redis messages  
- Email noop vs SMTP logged via `email_logs` table  

**Sentry:** Not in `requirements.txt` — **not integrated in codebase** (README aspirational).

---

## External calls

| Target | Usage |
|--------|--------|
| Redis | Refresh tokens |
| SMTP | Transactional email |
| R2 (boto3) | Object storage |
| Geocode router | External geocoding **UNKNOWN — verify implementation in `geocode.py`** |
| Zoho Books | Optional via finance services when configured |
| Razorpay | Payout stub when enabled |

---

## Background / scheduled work

No in-process job queue. Scripts in `backend/scripts/` intended for cron/manual execution:

- `auto_close_sessions_day_end.py`  
- Migration/backfill scripts  
- Smoke: `production_smoke.py`, `smtp_check.py`  

---

## Example request trace: Admin approves daily log

1. `POST /api/v1/daily-logs/{id}/approve` — `daily_logs.py`  
2. `get_current_user` + permission `logs.approve` (or equivalent) + module scope  
3. Service updates `DailyLog.approval_status`, `visibility_status`, `submitted_at`, parent notes fields  
4. May create `Notification` for parent/therapist  
5. `log_audit(...)`  
6. `db.commit()`  
7. Return updated log schema  

(Parent API filters require approved + visibility enums — see `parent.py` session-logs query.)

---

## Production server

- `backend/scripts/start-production.sh` — migrate, optional seed, `uvicorn` with `WEB_CONCURRENCY`  
- `backend/Dockerfile` — container image for Railway  

---

## Tests

- `backend/app/tests/` — pytest; mirrors RBAC, billing, sessions, finance flags  
- Run: `python3 -m pytest app/tests -q`  

See [16_TESTING.md](./16_TESTING.md).
