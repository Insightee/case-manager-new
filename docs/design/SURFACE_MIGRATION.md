# Surface migration register

**Status:** Operational companion to the canonical [UI_CONTRACT.md](./UI_CONTRACT.md). This is not a second design system.

**Rule:** A future Forest Light green foundation must not trigger a global stylesheet replacement. Each row migrates on its own PR (or tightly related cluster) with rollback.

---

## Status labels

Every surface uses exactly one label:

| Status | Meaning |
|--------|---------|
| **Legacy** | Keeps its current visual contract. Indigo, admin teal, login aqua, or Forest v1 black as shipped. |
| **Migration planned** | Has a documented Forest Light product-foundation target in the UI contract. **Code stays unchanged** until an implementation PR. |
| **Migrated** | Follows the UI contract for that screen, including proposed tokens once that PR remaps them. |

**Forest Light v1** (IEP/observation: near-black primary, mint secondary) is a shipped visual language. It is **not** the proposed product-foundation palette. Those screens are **Migration planned** for token remap, not Legacy purple.

Legacy purple/indigo and admin teal remain valid **only** for unmigrated surfaces.

---

## Required fields for every migration PR

Do not start a restyle without this block in the PR:

```md
### Migration packet
- Routes:
- Canonical components:
- Shared dependencies (CSS/components that other portals import):
- Responsive behaviour (≤900px / ≥901px):
- Required states (empty, loading, saving, saved, error, read-only):
- Acceptance criteria (observable):
- Rollback: revert the PR; no global token file left half-applied
```

Rollback default: revert the surface’s CSS/classes only. Do not leave `:root` token changes that affect other portals.

---

## Register (from `frontend/src/routes/AppRoutes.jsx`)

Routes below are the live router. `frontend/src/routes/TherapistRoutes.jsx` is stale and unused.

### Public

| ID | Routes | Canonical UI | Current visual | Status | Target | Notes |
|----|--------|--------------|----------------|--------|--------|-------|
| PUB-01 | `/login` | `LoginPage.jsx` portal selector | Indigo/aqua, gradients, blobs | Legacy | Phase 3 — Forest foundations, three portal cards retained | Role-aware login stays |
| PUB-02 | `/therapistlogin`, `/clientlogin`, `/clinetlogin`, `/adminlogin` | `LoginPage.jsx` | Aqua submit `#2db7a7` | Legacy | Phase 3 | Typo alias `/clinetlogin` preserved |
| PUB-03 | `/devlogin` | `LoginPage.jsx` `portalType="dev"` | Same | Legacy | Phase 3 | Demo tabs |
| PUB-04 | `/forgot-password`, `/reset-password/:token` | password pages | Login chrome | Legacy | Phase 3 | Keep `?portal=` |
| PUB-05 | `/invite/:token` | `InvitePage.jsx` | Login chrome | Legacy | Phase 3 | |

### Therapist — high priority (phase 1)

| ID | Routes | Canonical UI | Current visual | Status | Target |
|----|--------|--------------|----------------|--------|--------|
| TH-01 | `/therapist` | `TherapistDashboardPage.jsx` | Indigo CTAs, 118px hue tiles, `.admin-btn` | Migration planned | Today’s work, unfinished tasks, Forest foundations, no oversized KPI tiles |
| TH-02 | `/therapist/cases` | `MyCasesPage.jsx`, `my-cases.css` `--ic-primary: #4f46e5` | Operational indigo | Migration planned | Assigned cases; 44px controls; Forest tokens |
| TH-03 | `/therapist/cases/:caseId` | `CaseDetailPage.jsx` tabs `overview`, `observation`, `sessions`, `documents` | Indigo operational | Migration planned | Case context + Forest overview. Stitch case-overview remains authoritative. No `CaseProfileShell` today. |
| TH-04 | `/therapist/logs` | `DailyLogsPage.jsx` | Mixed portal CSS | Migration planned | Thumb-zone submit; saving vs saved; 5-minute cap |
| TH-05 | `/therapist/reports` | `MonthlyReportsPage.jsx` | Operational | Migration planned | Unfinished reports list — not a metric dashboard |
| TH-06 | `/therapist/reports/cases/:caseId/observation` | `TherapistClinicalReportPage` + observation engine | Forest v1 (`forest-light-observation.css`) | Migration planned | Keep stitch blocks; remap to proposed tokens in a dedicated PR; rail reachable on mobile |
| TH-07 | `/therapist/reports/cases/:caseId/iep` | IEP engine + `ClinicalBuilderShell` | Forest v1 (`forest-light-iep.css`, `#0b1c16` buttons) | Migration planned | Seven sections; footer CTAs once on mobile; no PDF/Share without API |
| TH-08 | `/therapist/reports/edit/:reportId` | `ReportEditPage.jsx` | Legacy editor | Legacy | Do not restyle until reports-engine absorbs it or it is removed |

### Therapist — remaining chrome (phase 1 follow-through)

| ID | Routes | Canonical UI | Status | Target |
|----|--------|--------------|--------|--------|
| TH-09 | `/therapist/invoices` | `InvoicesPage.jsx` | Migration planned | Case-by-case preview; financial confirm after server success |
| TH-10 | `/therapist/support` (`/tickets`, `/incidents` redirects) | `TherapistSupportHubPage.jsx` | Migration planned | Reachable from mobile drawer |
| TH-11 | `/therapist/meetings` | `CaseManagerMeetingsPage` `portal="therapist"` | Migration planned | Portal wrapper; CM-only chrome hidden |
| TH-12 | `/therapist/leave` | `TherapistLeavePage.jsx` | Migration planned | Drawer reachable |
| TH-13 | `/therapist/slots` | `TherapistSlotsPage.jsx` | Migration planned | Scheduling; weekends flag unchanged |
| TH-14 | `/therapist/profile` | `TherapistProfilePage.jsx` | Migration planned | Footer / drawer, not a fourth bottom tab |
| TH-15 | `/therapist/notifications` | `NotificationCenterPage.jsx` | Migration planned | Shared component; therapist chrome only |

Therapist bottom tabs today: Today, Cases, Reports, Home. Desktop sidebar adds invoices, support, meetings, leave, scheduling. **Menu drawer must list every sidebar item.** Current `useMenu` / `showMobileDrawer` interaction is a defect (see UX_BACKLOG NAV-01).

Therapist case tabs do **not** include Reports. Clinical reports stay on TH-05–TH-07 until Layer 4 adds a case-profile reports tab and this register is updated.

### Client / parent (phase 2)

| ID | Routes | Canonical UI | Current visual | Status | Target |
|----|--------|--------------|----------------|--------|--------|
| PA-01 | `/parent` | `ClientDashboardPage.jsx` | Purple hero gradient, glass, `.admin-btn` | Migration planned | Next steps, appointments, plain language |
| PA-02 | `/parent/cases/:caseId` | `ParentCaseDetailPage.jsx` tabs overview, sessions, observation, iep, goals, documents, bookings | Mixed | Migration planned | Progressive disclosure; parent preview for IEP/observation |
| PA-03 | `/parent/session-logs` | `ClientSessionLogsPage.jsx` | Operational | Migration planned | Understandable updates |
| PA-04 | `/parent/reports` (`?type=`) | `ParentReportsPage.jsx` | Mix of `admin-btn` and `parent-reports__btn` | Migration planned | Monthly / IEP / observation / documents |
| PA-05 | `/parent/iep` | Redirect → reports `type=iep` | — | Legacy (redirect) | Keep redirect |
| PA-06 | `/parent/billing` | `ParentBillingPage.jsx` | Indigo parent-pay buttons | Migration planned | Plain-language statements |
| PA-07 | `/parent/book` | `ClientBookAppointmentPage.jsx` | Operational | Migration planned | Desktop nav + mobile drawer (not a bottom tab today) |
| PA-08 | `/parent/profile` (`/parent/address` redirect) | `ParentProfilePage.jsx` | Operational | Migration planned | |
| PA-09 | `/parent/support` (`/incidents` redirect) | `ClientSupportHubPage.jsx` | Operational | Migration planned | Communication |
| PA-10 | `/parent/meetings` | `CaseManagerMeetingsPage` `portal="parent"` | Operational | Migration planned | Portal wrapper |
| PA-11 | `/parent/notifications` | `NotificationCenterPage.jsx` | Shared | Migration planned | |

Parent bottom tabs today: Home, Sessions, Reports, Billing. Book, profile, support, meetings **must remain in the drawer**.

### Admin — operations (phase 3)

| ID | Routes | Canonical UI | Status | Notes |
|----|--------|--------------|--------|-------|
| AD-01 | `/admin` | `AdminIndexPage` / `SpotDashboardPage` | Migration planned | Landing via `GET /api/v1/admin/home` `landing_route` |
| AD-02 | `/admin/cm` | `AdminCaseManagerHomePage` | Migration planned | CM home |
| AD-03 | `/admin/cm/logs` | `AdminCmLogReviewPage` | Legacy | Not in sidebar; keep reachable from CM home |
| AD-04 | `/admin/workbench` | `AdminWorkbenchPage` | Migration planned | Queues |
| AD-05 | `/admin/cases` | `AdminCasesPage` | Migration planned | Desktop tables; mobile `AdminDataList` |
| AD-06 | `/admin/cases/:caseId` | `AdminCaseDetailPage` + panels | Migration planned | Tabs in Layer 3; finance desk subset |
| AD-07 | `/admin/logs` | `AdminSessionLogsPage` | Migration planned | Card-first ≤1024px already started |
| AD-08 | `/admin/reports` | `AdminReportsPage` | Migration planned | Queues + filters |
| AD-09 | `/admin/reports/view/:reportId` | `AdminReportViewPage` | Migration planned | |
| AD-10 | `/admin/reports/edit/:reportId` | `ReportEditPage` | Legacy | Shared with therapist |
| AD-11 | `/admin/iep` | `AdminIepPage` | Migration planned | Pills: IEP status / Planner / Uploader — keep ids |

### Admin — finance (phase 3)

| ID | Routes | Canonical UI | Status | Notes |
|----|--------|--------------|--------|-------|
| FN-01 | `/admin/invoices` | `AdminInvoicesPage` | Migration planned | Desktop density; teal pills until migrate |
| FN-02 | `/admin/invoices/compose` | `InvoiceComposer` | Migration planned | Tables → cards on mobile |
| FN-03 | `/admin/invoices/client/:invoiceId` | `AdminClientInvoicePage` | Migration planned | Replace “Invalid invoice.” copy |
| FN-04 | `/admin/therapist-payouts` | `AdminTherapistPayoutsPage` | Migration planned | Confirm after server; no `window.prompt` |
| FN-05 | `/admin/therapist-leave` | `FinanceLeavePage` | Migration planned | Finance-only nav |
| FN-06 | `/admin/finance-reports` | `AdminFinanceReportsPage` | Migration planned | |

### Admin — people, HR, settings (phase 3)

| ID | Routes | Canonical UI | Status | Notes |
|----|--------|--------------|--------|-------|
| HR-01 | `/admin/people` (`/admin/users` redirect) | `AdminPeoplePage` | Migration planned | `window.prompt` debt; tables |
| HR-02 | `/admin/profile` | `AdminStaffProfilePage` | Migration planned | Footer |
| HR-03 | `/admin/client-profiles` | `AdminClientProfilesPage` | Legacy / planned | Not in main sidebar |
| HR-04 | `/admin/therapist-profiles` | `AdminTherapistProfilesPage` | Migration planned | |
| HR-05 | `/admin/attendance` | `StaffAttendancePage` | Migration planned | |
| HR-06 | `/admin/staff-attendance/:userId` | `AdminStaffAttendanceDetailPage` | Legacy | Detail |
| HR-07 | `/admin/leave` | `LeaveManagementPage` | Migration planned | Tables without `AdminDataList` |
| HR-08 | `/admin/hr-cases` | `HRCasesPage` | Migration planned | No `window.prompt` |
| HR-09 | `/admin/hr-reports` | `AdminHrReportsPage` | Migration planned | |
| SU-01 | `/admin/support` (tickets/incidents/memos redirects) | `AdminSupportHubPage` | Migration planned | `overflowIds={[]}` unused More |
| MT-01 | `/admin/meetings` (`/admin/cm-meetings` redirect) | `CaseManagerMeetingsPage` `portal="admin"` | Migration planned | Bottom sheets already closer to the contract |
| ST-01 | `/admin/settings/services` | `AdminServiceCategoriesPage` | Migration planned | Super/module admin |
| ST-02 | `/admin/integrations` | `AdminIntegrationsPage` | Migration planned | Super admin |
| ST-03 | `/admin/platform-stats` | `AdminPlatformStatsPage` | Migration planned | Tables |
| NT-01 | `/admin/notifications` | `NotificationCenterPage` | Migration planned | Shared |
| SP-01 | `/admin/spot-attendance`, `/admin/spot-leave` | `SpotPortalPages.jsx` | Legacy | SPOT-only 3-tab nav; migrate with admin chrome |

### HR path aliases

| ID | Routes | Status | Notes |
|----|--------|--------|-------|
| HR-R | `/hr`, `/hr/people`, `/hr/therapists`, `/hr/cases`, `/hr/leave`, `/hr/memos`, `/hr/tickets`, `/hr/*` | Legacy (redirects) | No HR shell. Do not design a fourth portal. |

---

## Shared shells and CSS (not routes, but must be labelled)

| ID | Surface | Files | Status |
|----|---------|-------|--------|
| SH-01 | Portal shell / sidebar / bottom nav | `PortalShell.jsx`, `index.css` | Migration planned per portal; do not retoken `:root` in phase 1 |
| SH-02 | Forest v1 theme | `forest-light-theme.css` | Shipped; remap only with migrated surfaces |
| SH-03 | UX foundations | `ux-foundations.css` | Keep skip-link and reduced motion; align focus colour on migrate |
| SH-04 | Admin mobile system | `admin-portal-mobile.css`, `admin-mobile-ux.md` | Legacy patterns; tokens later |
| SH-05 | Clinical report CSS | `clinical-report-ui.css` | Migration planned with IEP/observation |
| SH-06 | Unstyled `clinical-ui` buttons | `ClinicalPrimaryButton.jsx`, `ClinicalStatusBadge.jsx` | Legacy debt — restyle or remove; do not revive `clinical-theme.css` |
| SH-07 | Goal modal | `StudentGoalCreateModal.jsx` | Migration planned (AI tab, mobile preview) |

---

## Phase order (locked)

1. **Therapist** — TH-01–TH-07 first (home, cases, case profile, logs, reports, observation, IEP). Then TH-09–TH-15 chrome.
2. **Client / parent** — PA-01–PA-11.
3. **Admin** — operations, then finance, then people/HR/settings. SPOT and login last.

Do not migrate admin tables in the same PR as therapist session logs.
