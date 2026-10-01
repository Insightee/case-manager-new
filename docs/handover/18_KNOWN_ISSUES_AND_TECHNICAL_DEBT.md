# 18 — Known Issues and Technical Debt

Separated into **Confirmed** (code/docs evidence) vs **Potential concerns** (review recommended).

---

## Confirmed

### Legacy roles

- `ADMIN`, `VIEWER`, `SUPERVISOR` still in DB until `scripts/migrate_staff_roles` run; new invites use `MODULE_ADMIN` / `CASE_MANAGER`.

### RBAC enforcement gaps

- Per-module write enforcement on API **partial** — [RBAC_SCOPE.md](../RBAC_SCOPE.md) / [ROLE_MODEL_PHASES.md](../ROLE_MODEL_PHASES.md).

### Therapist self-onboarding disabled

- Multiple frontend **TODO** comments: re-enable client invite / new client tabs in scheduling and forgot-session flows.

### Retired Vercel Git integrations

- `insightecasestaging` / `insightecasetesting` may post failing PR checks — disconnect ([AGENTS.md](../../AGENTS.md)).

### Finance engine staged behind flags

- Production may run code paths with `ENABLE_BILLING` / ledger writes off — intentional; cutover incomplete until runbooks executed.

### README stack drift

- Root README lists Celery, Nginx, Sentry, MongoDB-adjacent advice — **not reflected in current backend dependencies**.

### SQLite vs Postgres divergence

- Local SQLite uses bootstrap + runtime patches; risk of dev/prod schema skew if developers skip Docker Postgres.

### CM workflows pending

- RBAC doc lists **CM change/suspension approval workflows** as pending.

### Test gaps

- [TEST_GAP_BACKLOG.md](../TEST_GAP_BACKLOG.md) — P1/P2/P3 items open.

### Typo route preserved

- `/clinetlogin` alias for parent login — intentional backward compatibility.

---

## Potential concerns (verify)

| Area | Concern |
|------|---------|
| Rate limiting | Login brute-force beyond password-reset limit — grep `rate_limit` |
| `review_queue` doctrine | All exception triggers may not be implemented |
| Geocoder | External dependency and API key rotation undocumented |
| Razorpay live | Stub adapter — payouts not production-hardened until cutover |
| SCHOOL_COORDINATOR | Role exists; portal/home widgets scope unclear |
| Long admin/parent API files | `admin.py`, `parent.py` size → maintainability |
| Single SPA bundle | Large admin surface — performance on low-end mobile |
| CSRF | Bearer-token API — if cookies added later, revisit |

---

## TODO / FIXME in codebase (sample)

| Location | Note |
|----------|------|
| `TherapistSessionComposer.jsx` | Re-enable therapist self-onboarding |
| `BookSlotModal.jsx`, `SlotEditSheet.jsx`, `ForgotSessionForm.jsx` | Same |
| `test_admin_home_roles.py` | SCHOOL_COORDINATOR widget scope |

Run `rg TODO|FIXME backend frontend` for full list during onboarding.

---

## Deprecated dependencies

- No automated Dependabot report in handover — **run `npm audit` / pip audit periodically**.

---

## Architectural limitations

- Monolithic FastAPI — scale via horizontal workers + Postgres connection pool math (`WEB_CONCURRENCY × pool`).  
- No background worker — long tasks block request or rely on external cron scripts.  
- Clinical AI not integrated — future features must respect token economy rules.

---

## Performance

- See [SCALABILITY_REVIEW.md](../SCALABILITY_REVIEW.md), [SCALING_P1_IMPLEMENTATION.md](../SCALING_P1_IMPLEMENTATION.md).

---

## Security concerns (non-exploitation)

- JWT in browser storage — XSS risk mitigated partially by DOMPurify; review rich text surfaces.  
- `expose_db_errors` must stay false in prod.  
- Integration API off by default — enable only with credential rotation policy.

---

## Incomplete features (product)

- Root README **Part 4** items (lead conversion, advanced SLA) — partially implemented; compare [PRODUCT_ROADMAP.md](../PRODUCT_ROADMAP.md).

---

## Workarounds in production

- `VITE_HIDE_THERAPIST_LEAVE_CREDITS_UI` — UI-only hide for therapist confusion.  
- Finance provisional banner when `FINANCE_CUTOVER_COMPLETE=false`.
