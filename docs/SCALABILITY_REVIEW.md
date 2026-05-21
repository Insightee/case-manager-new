# Scalability and architecture review notes

Date: 2026-05-21 (automated review pass)

## Summary

The application is well suited for pilot scale (tens of staff, hundreds of cases). Several read-heavy admin endpoints load full case sets in memory before filtering; plan pagination and caching before multi-region production load.

## Database and query patterns

| Area | Implementation | Risk | Recommendation |
|------|----------------|------|----------------|
| Pipeline board | [`admin_case_pipeline_service.py`](../backend/app/services/admin_case_pipeline_service.py) loads all cases, then classifies in Python | O(n) cases per request; grows with org size | Add `?product_module=&status=` filters and optional pagination; consider materialized pipeline flags |
| Workbench | Per-section `LIMIT 8` with scoped joins | Low for inbox UX | Add total counts via `COUNT(*)` if KPI badges needed |
| Calendar | `GET /scheduling/calendar` per week range | Repeated fetches on view changes | Optional Redis cache keyed by therapist+date range (short TTL) |
| Reports queue | Paginated in admin API | Low | Keep page_size caps in tests |

## Bulk operations

| Operation | Behavior | Limit |
|-----------|----------|-------|
| Kanban bulk assign | Sequential `POST /cases/{id}/assignments` from browser | Practical ~20 cases; no server-side batch endpoint | Add `POST /admin/cases/bulk-assign` if ops regularly move 50+ cases |
| Report bulk approve | Server batch in `admin_report_service` | Tested | OK |

## Infrastructure

| Component | Role | Scale note |
|-----------|------|------------|
| Postgres | Primary store (Docker compose) | Use connection pooling in production |
| SQLite | Local dev / pytest | Not for multi-worker production |
| Redis | Refresh token store with in-memory fallback | Stateless API scaling OK for JWT access tokens |
| Uploads | Local `uploads/` volume | Move to object storage (S3) for HA |

## Horizontal scaling

- API is stateless except file uploads; multiple uvicorn workers behind a load balancer are feasible.
- Sticky sessions not required for JWT-only access.
- WebSocket/realtime not used.

## Suggested load probe (optional)

With expanded seed (500+ cases): 50 concurrent `GET /admin/cases/pipeline` and `GET /scheduling/calendar` — target p95 &lt; 2s on modest Postgres.

## Automated checks added

See `backend/app/tests/test_comprehensive_review.py` for API-level regression of auth scope, workbench, reschedule, billing, and tickets.
