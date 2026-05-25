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
| casemanager@demo.com | demo123 | CASE_MANAGER |
| finance@demo.com | demo123 | FINANCE |

## Tests

```bash
python3 -m pytest app/tests -q
```

## API docs

- Health: `GET /health`
- Swagger: `http://localhost:8000/docs`

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
