# 08 — Frontend

---

## Stack

| Technology | Version / notes | Source |
|------------|-----------------|--------|
| React | 19.x | `package.json` |
| Vite | 8.x | dev server, build |
| React Router | 7.x | `AppRoutes.jsx` |
| TanStack Query | 5.x | server state in hooks |
| Tailwind CSS | 4.x | `@tailwindcss/vite` |
| TipTap | 3.x | Rich text in reports |
| PWA | `vite-plugin-pwa` | Therapist mobile |
| DnD | `@dnd-kit` | Kanban (cases) |
| Charts | `recharts` | Dashboards |
| Analytics | `@vercel/analytics` | Vercel deployments |

No Redux — **AuthContext + React Query** pattern.

---

## Entry and layout

- `frontend/src/main.jsx` — mounts app, QueryClient, AuthProvider, Router  
- `frontend/src/layouts/PortalShell.jsx` — navigation shell per portal (`therapist`, `admin`, `parent`)  
- Lazy-loaded admin/parent chunks via `React.lazy` + `Suspense` in `AppRoutes.jsx`  

---

## Routing map

Base paths (from `AppRoutes.jsx`):

### Public

| Route | Page | Notes |
|-------|------|-------|
| `/login` | LoginPage | Portal selector |
| `/clientlogin`, `/clinetlogin` | LoginPage | Parent portal (typo alias preserved) |
| `/therapistlogin` | LoginPage | Therapist |
| `/adminlogin` | LoginPage | Admin/staff |
| `/devlogin` | LoginPage | Dev-only portal |
| `/forgot-password`, `/reset-password/:token` | Password reset | |
| `/invite/:token` | InvitePage | Accept invite |

### Therapist (`/therapist/*`, protected)

| Route | Component | Purpose |
|-------|-----------|---------|
| `/therapist` | TherapistDashboardPage | Home / quick actions |
| `/therapist/cases` | MyCasesPage | Case kanban/list |
| `/therapist/cases/:caseId` | CaseDetailPage | Case file tabs |
| `/therapist/logs` | DailyLogsPage | Session logs inbox + timer |
| `/therapist/reports` | MonthlyReportsPage | Cross-case reports |
| `/therapist/reports/cases/:caseId/observation\|iep` | TherapistClinicalReportPage | Clinical builders |
| `/therapist/reports/edit/:reportId` | ReportEditPage | Legacy edit |
| `/therapist/invoices` | InvoicesPage | Therapist invoices |
| `/therapist/support` | TherapistSupportHubPage | Tickets + incidents tabs |
| `/therapist/leave` | TherapistLeavePage | Leave |
| `/therapist/slots` | TherapistSlotsPage | Booking slots |
| `/therapist/profile` | TherapistProfilePage | Profile |
| `/therapist/notifications` | NotificationCenterPage | |

### Parent (`/parent/*`, protected)

| Route | Component | Purpose |
|-------|-----------|---------|
| `/parent` | ParentDashboardRoute | Family dashboard |
| `/parent/cases/:id` | ParentCaseDetailPage | Case hub |
| `/parent/session-logs` | ClientSessionLogsPage | Approved logs feed |
| `/parent/reports` | ParentReportsPage | Reports + IEP |
| `/parent/billing` | ParentBillingPage | Billing statements |
| `/parent/profile` | ParentProfilePage | Profile / address |
| `/parent/support` | ClientSupportHubPage | Support |
| `/parent/book` | ClientBookAppointmentPage | Booking |
| `/parent/notifications` | NotificationCenterPage | |

Legacy redirects: `/parent/iep` → reports; `/parent/address` → profile.

### Admin (`/admin/*`, protected)

| Route | Component | Primary users |
|-------|-----------|---------------|
| `/admin` | AdminIndexPage | Module admin dashboard |
| `/admin/cm` | AdminCaseManagerHomePage | Case managers |
| `/admin/cm/logs` | AdminCmLogReviewPage | CM log review |
| `/admin/workbench` | AdminWorkbenchPage | Session log workbench |
| `/admin/cases`, `/admin/cases/:caseId` | Cases list + detail | CM, admin |
| `/admin/logs` | AdminSessionLogsPage | Log approval queue |
| `/admin/reports`, `/admin/reports/view/:id` | Reports review | CM, admin |
| `/admin/invoices`, compose, client invoice | Finance flows | Finance, admin |
| `/admin/therapist-payouts` | Payouts | Finance |
| `/admin/finance-reports` | AdminFinanceReportsPage | Finance exports |
| `/admin/iep` | AdminIepPage | IEP admin |
| `/admin/support` | AdminSupportHubPage | Tickets, incidents, memos |
| `/admin/people` | AdminPeoplePage | Staff RBAC editor |
| `/admin/client-profiles` | AdminClientProfilesPage | Families |
| `/admin/therapist-profiles` | Therapist HR profiles | HR |
| `/admin/settings/services` | Service categories | Super/module admin |
| `/admin/meetings` | CaseManagerMeetingsPage | CM meetings |
| `/admin/attendance`, `/admin/leave`, `/admin/hr-*` | HR ops | HR |
| `/admin/integrations` | AdminIntegrationsPage | Integration clients |
| `/admin/platform-stats` | PlatformStatsPage | Super admin metrics |

`/hr/*` routes redirect into `/admin/*` (HR merged into admin shell).

---

## Route protection

- `Protected` wrapper in `AppRoutes.jsx` checks `AuthContext` `user` and `portal`  
- Wrong portal → redirect to correct login with message (`LOGIN_ERROR_WRONG_PORTAL`)  
- Admin landing: `GET /api/v1/admin/home` → `landing_route` (CM → `/admin/cm`, finance → invoices, etc.)  

---

## API communication

- `frontend/src/lib/apiClient.js`  
  - `apiFetch(path, options)` — attaches Bearer token, handles refresh, 30s timeout  
  - Production hosts `insighte.org` / `www.insighte.org` use **empty base** for same-origin `/api`  
  - Apex `insighte.org` forced to `https://www.insighte.org` for API base (redirect/body loss avoidance)  

- Vite dev proxy: configured in `vite.config.js` for `/api` and `/health`  

---

## Authentication state

- `frontend/src/context/AuthContext.jsx` — stores user, tokens, portal, login/logout  
- Tokens: access in memory/localStorage pattern (read AuthContext for exact storage)  
- Login passes `portal` to `POST /api/v1/auth/login`  

---

## Forms and validation

- Mostly controlled React state + server validation errors from `apiFetch`  
- Clinical/report forms use structured components under `components/reports-engine/`  
- DOMPurify for sanitized HTML where used  

---

## Error and loading UX

- `RouteLoading`, `PortalRouteError` shared components  
- API errors parsed in `parseApiErrorDetail` — map to user-friendly strings in components (inconsistent — some raw `detail` may show)  
- Canonical copy, saving vs saved, and optimistic-UI rules: [docs/design/UI_CONTRACT.md](../design/UI_CONTRACT.md) Layer 1–2  

---

## Feature flags (frontend)

Hooks and libs read `import.meta.env.VITE_*`:

- `useBillingRuntimeConfig.js`, `useClinicalProductModules.js`, finance stage tests in `src/lib/`  

Backend flags duplicated for write paths — **never trust UI-only hiding for security**.

---

## Important reusable components

| Area | Path |
|------|------|
| Admin UI primitives | `components/admin-portal/ui/` |
| Clinical builder shell | `components/reports-engine/shared/ClinicalBuilderShell.jsx` |
| Session log forms | `components/daily-logs/` |
| Invoices | `components/invoices/` |
| Shared notifications | `components/shared/NotificationCenterPage.jsx` |

---

## Page → API dependency (pattern)

Each page typically:

1. Uses React Query hook or `useEffect` + `apiFetch`  
2. Calls `/api/v1/...` endpoints scoped to user role  
3. Renders empty/error states without banned strings where updated  

**Example:** `DailyLogsPage` → `/api/v1/sessions`, `/api/v1/daily-logs`, therapist portal home stats.

---

## Build and preview

```bash
cd frontend
npm run build      # output dist/
npm run preview    # static preview
```

---

## Related docs

- [docs/design/UI_CONTRACT.md](../design/UI_CONTRACT.md) — canonical UI/UX contract  
- [docs/design/SURFACE_MIGRATION.md](../design/SURFACE_MIGRATION.md) — live route register (prefer `AppRoutes.jsx` over this handover map if they drift)  
- [docs/THERAPIST_PORTAL_GUIDE.md](../THERAPIST_PORTAL_GUIDE.md)  
- [docs/PARENT_CLIENT_PORTAL_GUIDE.md](../PARENT_CLIENT_PORTAL_GUIDE.md)  
- [frontend/docs/admin-mobile-ux.md](../../frontend/docs/admin-mobile-ux.md)  
