# 04 — Local Development

Complete setup from a fresh machine. Commands are taken from [README.md](../../README.md), [backend/README.md](../../backend/README.md), [frontend/README.md](../../frontend/README.md), and `docker-compose.yml`.

---

## 1. Prerequisites

| Software | Version (from repo) | Purpose |
|----------|---------------------|---------|
| Git | recent | Clone repo |
| Python | **3.11** (CI pin) | Backend API, pytest |
| Node.js | **24** (CI pin) | Frontend dev/build |
| npm | bundled with Node | Frontend packages |
| Optional: Docker Desktop | — | Postgres + Redis + API stack |
| Optional: Redis locally | `redis://localhost:6379/0` | Faster login (refresh tokens) |

**OS note:** User environment may be Windows; use `python` vs `python3` as installed. Examples use `python3` from docs; on Windows often `py -3.11` or `python`.

---

## 2. Clone repository

```bash
git clone https://github.com/Insightee/case-manager-new.git
cd case-manager-new
```

**UNKNOWN — VERIFY WITH TEAM:** Private fork/org URL if different from public path.

---

## 3. Backend — SQLite path (fastest)

```bash
cd backend
python3 -m pip install -r requirements.txt
cp .env.example .env   # optional; defaults work for SQLite
python3 -m app.seed.demo_seed
python3 -m uvicorn app.main:app --reload --port 8000
```

Verify:

```bash
curl -s http://localhost:8000/health
```

Open Swagger: http://localhost:8000/docs

**Tips ([backend/README.md](../../backend/README.md)):**

- Start Redis: `docker compose up redis -d` — avoids slow first-login Redis probe  
- Do not set `SEED_DEMO_DATA=true` on every restart (slow on empty DB)  
- `LAZY_SQLITE_PATCHES=true` (default) — patches on first request  

---

## 4. Frontend

New terminal:

```bash
cd frontend
npm install
cp .env.example .env.local   # optional
npm run dev
```

Open http://localhost:5173

**API URL:** Leave `VITE_API_URL` **empty** in `.env.local` so Vite proxies `/api` and `/health` to port 8000.

Sign in: `superadmin@demo.com` / `demo123` or `therapist@demo.com` / `demo123`.

---

## 5. Docker Compose (Postgres + Redis + API)

From repo root:

```bash
docker compose up --build
```

First boot runs `alembic upgrade head`, seeds if no users, then uvicorn with reload.

Seed manually if needed:

```bash
docker compose exec api python -m app.seed.demo_seed
```

Postgres exposed on `localhost:5432` (user/pass/db: `insightcase`).

---

## 6. Environment setup

| File | Purpose |
|------|---------|
| `backend/.env` | API secrets, `DATABASE_URL`, SMTP, flags |
| `frontend/.env.local` | `VITE_*` only |

Full variable list: [05_ENVIRONMENT_VARIABLES.md](./05_ENVIRONMENT_VARIABLES.md) and [docs/ENVIRONMENT_VARIABLES.md](../ENVIRONMENT_VARIABLES.md).

---

## 7. Database setup

| Mode | Schema application |
|------|-------------------|
| SQLite local | `bootstrap_schema()` on API startup + optional patches |
| Postgres (Docker/prod) | `alembic upgrade head` or `python scripts/migrate_production.py` |

Check single migration head:

```bash
cd backend
PYTHONPATH=.:alembic python3 -m alembic heads
```

Must show exactly **one** `(head)`.

---

## 8. Seed data

Demo seed:

```bash
cd backend
python3 -m app.seed.demo_seed
```

Creates demo users, sample cases, roles per [backend/README.md](../../backend/README.md) matrix.

**Production:** Never enable `SEED_DEMO_DATA=true` on shared production.

---

## 9. Running tests

**Backend (from `backend/`):**

```bash
python3 -m pytest app/tests -q
```

**Frontend unit (from `frontend/`):**

```bash
npm run test:unit
```

**E2E (from `frontend/`):**

```bash
npx playwright install chromium
npm run test:e2e
```

Requires API + dev server (Playwright config may start them — see `frontend/playwright.config.js`).

**Repo pre-push:**

```bash
make check
# or ./scripts/pre-push-check.sh
```

---

## 10. Verification checklist

- [ ] `GET /health` → `"status":"ok"`  
- [ ] Login on correct portal path (therapist vs admin vs parent)  
- [ ] Therapist can open `/therapist/logs` and `/therapist/cases`  
- [ ] Admin landing resolves via `GET /api/v1/admin/home` → `landing_route`  
- [ ] `pytest` green locally before PR  

---

## 11. Remote dependencies

Local dev **does not require** Railway/Vercel/R2 unless you test:

- Real email → set `SMTP_*` in `backend/.env`  
- R2 uploads → set `STORAGE_PROVIDER=r2` and R2 vars  
- Production API from local UI → set `VITE_API_URL` to public API (also add your origin to API `CORS_ORIGINS`)  

**UNKNOWN — VERIFY WITH TEAM:** VPN or IP allowlists for production DB read-only roles (see [docs/Cursor_Handover_Production_Readonly_Postgres.md](../Cursor_Handover_Production_Readonly_Postgres.md)).

---

## 12. Common local pitfalls

See [17_TROUBLESHOOTING.md](./17_TROUBLESHOOTING.md).
