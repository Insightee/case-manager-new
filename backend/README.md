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
