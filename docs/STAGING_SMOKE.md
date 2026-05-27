# Staging smoke: production import and session logs

Run after `alembic upgrade head` on the target database. Do **not** run `demo_seed` on production.

## 1. Dry-run import

```bash
cd backend
python3 -m scripts.import_production \
  --dir ../docs/import-templates \
  --actor-email superadmin@demo.com \
  --dry-run
```

Review the summary counts and error lists.

## 2. Apply import (staging)

```bash
python3 -m scripts.import_production \
  --dir ../docs/import-templates \
  --actor-email superadmin@demo.com
```

Store generated therapist passwords from script output or set `password` column in CSV.

## 3. Therapist flow

1. Log in as an imported therapist (`therapist1@insighte.in`).
2. `GET /api/v1/therapist/my-cases` — only assigned cases appear.
3. Create or open a session for a case (`POST /api/v1/sessions` or clock-in flow).
4. End session (`POST /api/v1/sessions/{id}/end`).
5. Submit log: `POST /api/v1/therapist/session-logs` with `session_id`, `attendance_status`, notes.

## 4. Case manager flow

1. Log in as CM (`casemanager@insighte.in` or imported CM).
2. `GET /api/v1/admin/session-logs?status=pending` — submitted logs appear.
3. `GET /api/v1/admin/session-logs?status=missing` — completed sessions without logs.
4. Approve: `POST /api/v1/daily-logs/{id}/approve`.

## 5. Parent flow

1. Log in as imported parent (`parent1@insighte.in`).
2. Before CM approve: `GET /api/v1/parent/session-logs` must **not** include the pending log.
3. After CM approve: log appears; check `GET /api/v1/notifications` for in-app alert.

## 6. Production smoke (Railway)

With production env vars loaded (never commit secrets):

```bash
cd backend
export APP_ENV=production
export API_BASE_URL=https://your-api.up.railway.app
# Optional: SMOKE_TEST_EMAIL=you@domain.com SMOKE_TEST_PASSWORD=...
python3 scripts/production_smoke.py
```

Checks: config validation, Postgres, Alembic head, R2 round-trip, legacy `uploads/` dirs empty, `GET /health`, optional ZeptoMail send.

## 7. Regression

```bash
cd backend
python3 -m pytest app/tests/test_session_logs_portal.py app/tests/test_parent_api_isolation.py \
  app/tests/test_production_checks.py app/tests/test_object_storage_uploads.py \
  app/tests/test_report_image_storage.py -q
```
