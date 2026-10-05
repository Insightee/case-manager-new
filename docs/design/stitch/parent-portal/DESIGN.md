# Parent / client portal — Stitch reference (Forest Light)

**Status:** Shipped Phase 2 hub (Oct 2026). Authoritative visual + behaviour reference for `/parent/*`.  
**Implementation:** `frontend/src/styles/parent-portal-theme.css` on `.app-shell--parent.forest-light`, component CSS under `client-portal/parent-*.css`.

## Stitch project

| Field | Value |
|--------|--------|
| Project ID | `5257107495041753907` |
| Title | InsighteCase Parent Portal — Forest Light |
| Design system | `assets/1374043857434626850` (InsighteCase Parent Forest Light) |

## Screens (Stitch → product)

| Screen | Stitch screen ID | Route · component | Notes |
|--------|------------------|-------------------|--------|
| Home hub | `b5a947124bfb45aeae3171aeecb38e03` | `/parent` · `ClientDashboardPage.jsx` | Next **2** upcoming (therapy + CM meetings), attendance alerts, invoice only if due, session log chips, cases with notifications, **Therapist chat** tab |
| Session updates | `d8141cce9f334c26a0fd3e768895a7c3` | `/parent/session-logs` · `ClientSessionLogsPage.jsx` | Approved logs + CM meetings |
| Reports hub | `d5dd703a58fb431c8bc9aa08afcc4c9e` | `/parent/reports` · `ParentReportsPage.jsx` | Monthly, IEP, documents |
| Book session | _(form, no Stitch ID)_ | `/parent/book` · `ParentBookSessionForm.jsx` | 7-day next-open-slot; **Request a meeting** when no slot |
| Profile | _(form)_ | `/parent/profile` · `ParentProfilePage.jsx` | Change password, email prefs, **+ Add another contact** (collapsible backup name/email) |
| Therapist chat | _(chat thread)_ | Dashboard tab · `ParentTherapistChat.jsx` | Support ticket thread; **Say hello** empty state; loop in case manager |

Open in Stitch: project `5257107495041753907` and screen IDs above. HTML exports live on Stitch files API (not committed).

## Visual rules (Forest Light)

- Page background `#F7F8F5`, surfaces `#FFFFFF`, decorative border `#DDE4DE`
- Primary / active nav `#166534`, hover `#14532D`, selected surface `#EAF3EC`
- Text `#17211B`, secondary `#526057`
- Headlines: Manrope 600–700; body: Inter
- No purple gradient heroes, no legacy clinical purple cards
- Minimum control height **44px** on mobile; surface radius **12px**, control **8px**

## Mobile navigation

| Tab | Route | Purpose |
|-----|--------|---------|
| Home | `/parent` | Overview, upcoming, chat tab, action items |
| Sessions | `/parent/session-logs` | Session notes and meetings |
| Reports | `/parent/reports` | Reports and documents |
| Billing | `/parent/billing` | Invoices |
| Overflow (☰) | book, profile, support, meetings, notifications | Desktop nav parity |

**Copy:** Do not use “Family dashboard” or “Parent Updates” — use **Home** and **Therapist chat**.

## PWA / home screen (experience-first)

Parents often use **Add to Home Screen**. After deploys, stale bundles can break sign-in.

| Surface | Component | Behaviour |
|---------|-----------|-----------|
| Sign-in | `PwaStaleRecoveryHelp` on `LoginPage` (`/clientlogin`) | Shown in standalone or after chunk/load errors; **Get latest** · **Open in browser** · **Re-add shortcut** |
| Signed-in shell | `PwaStaleRecoveryHelp` banner in `PortalShell` | When `vite:preloadError` or chunk failure sets session hint |
| Top bar | `PortalInstallButton` | Install / refresh menu (existing) |

Manifest: `/manifest-parent.webmanifest` · app name **InsighteCase Client** (`portalPwa.js`).

## Email notification defaults (profile)

**On by default:** session logs, therapist leave, billing, meetings.  
**Off by default:** appointments, reports.  
Backend: `parent_notification_preferences.py` · UI: `ParentEmailPreferencesSection.jsx`.

## APIs (parent hub)

| Feature | Endpoint |
|---------|----------|
| Next open slot | `GET /api/v1/parent/booking/next-open-slot` |
| Meeting request | `POST /api/v1/parent/booking/meeting-requests` (therapist must be actively assigned) |
| Therapist chat | `GET/POST /api/v1/parent/therapist-chat` |
| Change password | `POST /api/v1/auth/change-password` |

## Acceptance

- [x] Forest green primary; no indigo/purple on parent shell
- [x] Home shows merged upcoming (sessions + CM meetings, `SCHEDULED`)
- [x] Therapist chat tab with bubble thread when messages exist
- [x] Profile backup contact via expander, not separate card
- [x] PWA stale recovery on client login + shell
- [ ] E2E `e2e/parent-portal.spec.js` green on CI
- [ ] Alembic `pmr7req20261005` applied in production
