# InsightCase — System Architecture (CTO view)

_Last updated: May 2026 — reflects therapist-first delivery, dual work surfaces (Session Logs vs My Cases), and API-backed operations._

## Executive summary

InsightCase is a **case-centric operations platform** for Insighte Childcare. Every engagement is anchored on a **Case ID**; sessions, daily logs, monthly reports, bookings, invoices, and parent visibility all roll up to that case.

The current build prioritizes the **therapist portal** (daily execution) while the **admin portal** governs review, billing, and configuration. A **parent portal** consumes approved, visibility-scoped artifacts.

```mermaid
flowchart TB
  subgraph clients [Client tier]
    T[Therapist SPA]
    A[Admin SPA]
    P[Parent SPA]
  end

  subgraph api [API tier - FastAPI]
    AUTH[Auth / RBAC]
    CASE[Cases and Assignments]
    SESS[Sessions and Daily Logs]
    REP[Monthly Reports]
    INV[Invoices and Billing]
    SLOT[Slots and Bookings]
    ADM[Admin Aggregates]
  end

  subgraph data [Data tier]
    DB[(SQLite / Postgres)]
    AUD[Audit Events]
  end

  T --> AUTH
  A --> AUTH
  P --> AUTH
  T --> CASE
  T --> SESS
  T --> REP
  T --> INV
  T --> SLOT
  A --> ADM
  A --> REP
  A --> SESS
  P --> CASE
  AUTH --> DB
  CASE --> DB
  SESS --> DB
  REP --> DB
  INV --> DB
  SLOT --> DB
  ADM --> DB
  SESS --> AUD
  REP --> AUD
```

## Scope change: two therapist work surfaces

Earlier mockups treated “cases” and “logs” as one screen. The product now **separates concerns**:

| Surface | Route | Purpose |
|---------|--------|---------|
| **Session Logs** | `/therapist/logs` | **Today**: timer, start/end, forgot session, submit log, cross-case inbox |
| **My Cases** | `/therapist/cases`, `/therapist/cases/:id` | **Per client**: overview, sessions/logs, reports, bookings, support |

```mermaid
flowchart LR
  subgraph daily [Session Logs - operational]
    U[Upcoming sessions]
    A[Active timer]
    L[Needs log inbox]
    F[Forgot session]
  end

  subgraph crm [My Cases - case file]
    B[Kanban board]
    D[Case detail tabs]
    O[Overview]
    S[Sessions and logs]
    R[Reports]
    K[Bookings]
  end

  daily -->|same APIs| API[(REST API)]
  crm --> API
```

**Monthly Reports** (`/therapist/reports`) remains a **cross-case pipeline** (draft → submit → admin approve → publish). Case detail duplicates create/submit for convenience.

## Parent (client) portal architecture

Parents consume **approved, visibility-scoped** artifacts only. The UI mirrors the therapist **case-centric** model as read-only hubs.

| Surface | Route | Purpose |
|---------|--------|---------|
| Family dashboard | `/parent` | Stats, cases, notifications |
| Case hub | `/parent/cases/:id` | Overview, session updates, reports, bookings |
| Session updates | `/parent/session-logs` | Cross-child feed of approved logs |
| Approved reports | `/parent/reports` | Published monthly reports + viewer |
| IEP | `/parent/iep` | Acknowledge + download attachments |
| Billing | `/parent/billing` | `ParentBillingStatement` rows (family-facing) |
| Book / address / support | existing routes | Booking API, homecare address, tickets |

### Parent visibility rules

| Artifact | Parent API filter |
|----------|-------------------|
| Daily logs | `submitted_at` set, `approval_status=APPROVED`, `visibility_status` in `APPROVED_FOR_PARENT` / `SHARED_WITH_PARENT`; excludes `session_notes` / `observations` |
| Monthly reports | `status=PUBLISHED` + parent-visible visibility |
| IEP attachments | parent-visible; acknowledge sets `SHARED_WITH_PARENT` |
| Billing | Per-parent `parent_billing_statements` table (not therapist invoices) |

```mermaid
flowchart LR
  TH[Therapist submits log] --> AD[Admin approves log]
  AD --> PV[visibility APPROVED_FOR_PARENT]
  PV --> PA[GET /parent/session-logs]
  TH2[Therapist report published] --> PA2[GET /parent/reports]
```

## Admin portal architecture

Admins and case managers **review, assign, and configure** cases. The UI combines **cross-case queues** (dashboard, session logs, reports, invoices) with a **case hub** for per-client operations.

| Surface | Route | Purpose |
|---------|--------|---------|
| Ops dashboard | `/admin` | KPIs + queues with deep links |
| Cases board | `/admin/cases` | List, create, drawer history |
| Case hub | `/admin/cases/:id` | Overview, assignments, logs, reports, billing, schedule |
| Session logs | `/admin/logs` | Approve/reject with internal vs family notes |
| Report review | `/admin/reports` | View modal, approve for parents, reject with comment |
| Invoices | `/admin/invoices` | Finance queue + payment modal |
| IEP | `/admin/iep` | Upload, download, share with parent |
| Incidents | `/admin/incidents` | Status workflow (supervisor+) |

### Admin approval → parent visibility

| Action | Effect on parent portal |
|--------|-------------------------|
| Approve daily log (with `parent_notes`) | Sets `APPROVED` + `APPROVED_FOR_PARENT` + `submitted_at` |
| Approve monthly report | `PUBLISHED` + `APPROVED_FOR_PARENT` visibility |
| Share IEP attachment | `PATCH` attachment to `APPROVED_FOR_PARENT` |

Dashboard and CSV export respect **product-module scoping**; invoice counts filter by therapists on scoped cases.

## Domain model (simplified)

```mermaid
erDiagram
  Case ||--o{ CaseAssignment : has
  User ||--o{ CaseAssignment : therapist
  Case ||--o{ TherapySession : schedules
  TherapySession ||--o| DailyLog : produces
  Case ||--o{ MonthlyReport : summarizes
  User ||--o{ Invoice : earns
  Case ||--o{ TherapistSlot : books
  Child ||--|| Case : profile

  Case {
    int id PK
    string case_code
    string status
    string product_module
  }
  TherapySession {
    int id PK
    string status
    datetime actual_start_at
    datetime actual_end_at
  }
  DailyLog {
    int id PK
    string approval_status
    bool late_addition
  }
  MonthlyReport {
    int id PK
    string status
    string visibility_status
  }
```

## Request flows

### Session → log → approval

```mermaid
sequenceDiagram
  participant TH as Therapist
  participant API as API
  participant AD as Admin

  TH->>API: POST /sessions/{id}/start
  TH->>API: POST /sessions/{id}/end
  TH->>API: POST /daily-logs
  AD->>API: POST /daily-logs/{id}/approve
  Note over API: LogApprovalStatus APPROVED
```

### Monthly report lifecycle

```mermaid
sequenceDiagram
  participant TH as Therapist
  participant API as API
  participant AD as Admin
  participant PA as Parent

  TH->>API: POST /reports/monthly
  TH->>API: POST /reports/monthly/{id}/submit
  AD->>API: POST /reports/monthly/{id}/approve
  Note over API: status PUBLISHED visibility APPROVED_FOR_PARENT
  PA->>API: GET parent reports (scoped)
```

### Invoice (therapist)

Therapist uses **preview → submit**; finance/admin approves payouts separately.

## Security and tenancy

- **JWT** authentication; role + **module feature** flags (`session_logs`, `invoices`, etc.).
- **Case scope**: therapists see only assigned cases; parents see linked children.
- **Visibility** on reports/logs gates parent-facing content.
- **Audit** on approve/reject and sensitive mutations.

## Frontend architecture

| Layer | Stack | Notes |
|-------|--------|------|
| SPA | React + Vite | Role-based route trees |
| State | Context + hooks | `AuthContext`, workbench builders |
| API | `apiClient.js` | Bearer token, `/api/v1` |
| UI | CSS modules / Tailwind mix | Admin portal + therapist areas |

**Workbench pattern**: `caseWorkbench.js` and `reportWorkbench.js` aggregate list endpoints client-side for kanban/pipeline UIs without bespoke BFF endpoints (acceptable at current scale; consider GraphQL or aggregate APIs if N+1 becomes painful).

## Backend architecture

| Layer | Responsibility |
|-------|----------------|
| `api/v1/*` | HTTP routers, auth deps |
| `services/*` | Business rules (logs, invoices, assignments) |
| `models/*` | SQLAlchemy ORM |
| `core/permissions.py` | RBAC matrix |
| `core/modules.py` | Product module features |
| `alembic/` | Schema migrations |

## Deployment topology (target)

```mermaid
flowchart LR
  CDN[Static frontend] --> LB[Load balancer]
  LB --> API1[FastAPI instances]
  API1 --> PG[(Postgres)]
  API1 --> S3[Attachments blob]
```

Local dev uses SQLite (`insightcase.db`) and Vite proxy to `:8000`.

## Scheduling (Calendly-style)

**Invariant:** one booked `TherapistSlot` ↔ one `TherapySession` (SCHEDULED), kept in sync via `appointment_booking_service.sync_session_for_slot` and `cancel_booking_with_session`.

| Slot status | Bookable? | Session when booked |
|-------------|-----------|---------------------|
| AVAILABLE | Yes | — |
| BOOKED | No | SCHEDULED |
| BLOCKED / HOLIDAY | No | — |
| CANCELLED / RESCHEDULED | No | CANCELLED / RESCHEDULED (old slot) |

Default weekly template materializes **60-minute** slots (`therapist_schedule_templates.config_json.slot_duration_minutes`). Parent booking only surfaces slots ≥ 60 minutes.

**Unified API** (`/api/v1/scheduling/*`): calendar, slot CRUD (including PATCH time), book/cancel/block, template materialize, `POST /assign-recurring` (admin bulk book + `recurring_schedule_assignments`), `POST /reschedule` (writes `appointment_reschedules`). Legacy `/api/v1/slots/*` routes remain as aliases.

**Leave approval** cancels booked slots with session sync (`cancel_booking_with_session`), not slot-only cancel.

## Parent appointment booking

Parents use a **week calendar** at `/parent/book` via `GET /api/v1/parent/booking/calendar` (same slot DTO as therapist calendar, plus `is_mine` / policy flags). Booking creates both a `TherapistSlot` (BOOKED) and a linked `TherapySession` (SCHEDULED).

| Rule | Value |
|------|--------|
| Cancel / reschedule window | More than **6 hours** before session start |
| Reschedules per case per month | Max **2** (`case_appointment_usage`) |
| Booking mode on assignment | `OPEN` (any available 1h slot) or `FIXED` (window + optional recurring pre-book) |

**APIs:** `POST /api/v1/booking/appointments`, `POST /parent/appointments/{id}/cancel`, `POST /parent/appointments/{id}/reschedule`, `PATCH /cases/{id}/assignments/{aid}/booking` (admin), `POST /api/v1/scheduling/assign-recurring` (admin wizard).

**Notifications:** Therapist cancel, parent book/reschedule, recurring assign (`appointment_notification_service`).

## Client billing

Family billing uses **`client_invoices`** (separate from therapist payout `invoices`). Parents filter by month, child, service, and payment status; view session-level lines, packages, disputes, and printable invoices.

See [billing-architecture.md](billing-architecture.md) for workflows, dispute loop, package logic, and payment gateway extension points.

| API | Purpose |
|-----|---------|
| `GET /parent/billing/dashboard` | Summary + invoices + packages + filter options |
| `GET /parent/billing/invoices/{id}` | Line items, totals, payments, disputes |
| `POST /parent/billing/invoices/{id}/disputes` | Raise dispute |
| `POST /admin/client-billing/invoices/{id}/payments` | Record UPI/bank/cash payment |
| `POST /admin/client-billing/disputes/{id}/resolve` | Resolve with optional adjustment |

## Parent Reports hub

Parents have a single **Reports** nav item (`/parent/reports`) combining monthly reports and IEP plans. Legacy routes redirect: `/parent/iep` → `?type=iep`, `/parent/address` → profile.

```mermaid
stateDiagram-v2
  [*] --> InternalReview: Therapist submits
  InternalReview --> PendingParent: CM shares to parent
  PendingParent --> Approved: Parent approves
  PendingParent --> ChangesRequested: Parent feedback
  ChangesRequested --> InternalReview: CM revises
  InternalReview --> PendingParent: Resend to parent
  Approved --> [*]
```

| API | Purpose |
|-----|---------|
| `GET /parent/reports/hub` | Combined monthly + IEP list with statuses |
| `GET /parent/reports/monthly/{id}` | Full report + comment thread |
| `POST /parent/reports/monthly/{id}/approve` | Parent sign-off |
| `POST /parent/reports/monthly/{id}/feedback` | Returns report to `UNDER_REVIEW` |
| `GET /parent/reports/iep/{id}` | IEP metadata + comments |
| `POST /parent/reports/iep/{id}/comments` | Goal suggestions / change requests |
| `POST /reports/monthly/{id}/resend-to-parent` | Admin clears feedback, sets `PENDING` |

**Schema:** `document_comments` (IEP + reports); `monthly_reports.parent_review_status`, `parent_feedback`, `parent_reviewed_at`.

## Admin case allotment and People hub

Operations staff create cases through a **guided allotment wizard** (`AdminCaseAllotmentWizard`) or the cases drawer. Case codes follow **`IC-{YEAR}-{MODULE}-{SEQ}`** (e.g. `IC-2026-HC-042`) via `case_code_service` when omitted on create.

| API | Purpose |
|-----|---------|
| `GET /admin/cases/next-code?product_module=` | Preview next case code |
| `GET /admin/allotment/therapists?product_module=` | Module-scoped therapist list (not booking assignees only) |
| `GET/POST /admin/families`, `POST /admin/children` | Child/parent directory for allotment |
| `POST /admin/cases/allot` | Create case + billing + assignment in one step |
| `GET/POST /admin/invites` | Pending invite tokens (therapist, parent, staff) |

**People hub** (`/admin/people`) consolidates staff, therapists (with profile status), families, and invites. **`client_billing_mode`** on `Case` (`PREPAID` / `POSTPAID`) drives family invoices separately from therapist `billing_type`.

Admin address forms set `showLocationButton={false}` so GPS capture stays on parent/therapist flows only.

## Maturity matrix

| Capability | Therapist | Admin | Parent | API |
|------------|-----------|-------|--------|-----|
| Auth / invite | ✓ | ✓ | ✓ | ✓ |
| Case list / detail | ✓ | ✓ | case hub read-only | ✓ |
| Session timer + logs | ✓ | review | approved logs only | ✓ |
| Monthly reports | ✓ pipeline | approve + resend | hub, approve, feedback | ✓ |
| Invoices | preview/submit | approve + client payments | dashboard, filters, disputes | ✓ |
| Slots / bookings | view/book + parent label | manage | week calendar, book/reschedule/cancel | ✓ |
| Leave / profile | ✓ | — | profile + address | ✓ |
| IEP | admin upload | partial | in-app viewer + comments | ✓ |
| Support tickets | full | manage | raise + list own | ✓ |
| E2E Playwright | therapist smoke | parent smoke | admin smoke | — |
| Case hub | `/therapist/cases/:id` | `/parent/cases/:id` | `/admin/cases/:id` | — |

## Recommended next engineering steps

1. **Aggregate endpoints** for dashboard and My Cases to cut parallel fetches.
2. **Report editor** PATCH UI on Monthly Reports page (summary inline edit).
3. **E2E Playwright** — `therapist-portal.spec.js`, `parent-portal.spec.js`, and `admin-portal.spec.js`; API smoke at `backend/scripts/therapist_flow_smoke.py`.
4. **Postgres** in staging; retire SQLite-only assumptions.
5. **Event bus** (optional) for notifications when logs/reports change state.

## Related docs

- [README.md](../README.md) — local setup and demo accounts
- [backend/README.md](../backend/README.md) — API and roles
