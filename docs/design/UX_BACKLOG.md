# UX implementation backlog

**Status:** Implementation backlog for the canonical [UI_CONTRACT.md](./UI_CONTRACT.md). No application changes ship from this document alone.

**Order:** therapist first, client/parent second, admin third ([SURFACE_MIGRATION.md](./SURFACE_MIGRATION.md)).

Each item lists affected routes/components and an **observable** acceptance criterion. Items are grouped by the required coverage areas: styling, mobile, buttons, navigation, forms/feedback, accessibility.

---

## Phase 1 — Therapist

### Styling

| ID | Problem | Affected | Proposed fix | Acceptance criterion |
|----|---------|----------|--------------|----------------------|
| TH-ST-01 | Therapist home uses indigo gradient CTAs and 118px multi-hue action tiles | `/therapist` `TherapistDashboardPage.jsx`, `index.css` `.therapist-dashboard__cta` | Task dashboard pattern: Forest surfaces, Title/Metric type steps, no decorative gradient | At 375px and 1280px: no linear-gradient on tiles; one primary 44px action; counts use Metric (1.25rem) not Display; 200% zoom does not clip the primary action |
| TH-ST-02 | My Cases hardcodes `--ic-primary: #4f46e5` | `/therapist/cases` `my-cases.css` | Scope Forest tokens on `.ic-my-cases` when the page migrates; stop introducing new `#4f46e5` | Case cards and filters use contract spacing 8/12/16; primary controls match the migrated therapist primary; no indigo remaining on this route |
| TH-ST-03 | Case overview is operational indigo, not Forest `cov-*` | `/therapist/cases/:caseId?tab=overview` `CaseDetailPage.jsx` | Case detail pattern + Forest foundations. Do **not** claim Stitch visual match until DESIGN.md is recovered or replaced | Overview shows strengths / support needs / environment / pending work without a fabricated progress ring; status is text + pill; PR does not check “matches Stitch PNG” unless the artefact exists |
| TH-ST-04 | IEP section labels use system monospace | IEP builder `clinical-report-ui.css` `.cr-section__label` | `font-family: var(--font-mono)` (JetBrains) only on existing eyebrows | Computed font on section eyebrows is JetBrains Mono; goal titles and KV values remain Inter |
| TH-ST-05 | IEP/observation primary is `#0b1c16` with inline `style={{ backgroundColor: '#0b1c16' }}` | `ClinicalBuilderShell.jsx`, `IepLandingPage.jsx` | Classes only; remap to `#166534` only in the token-remap PR for TH-06/TH-07 | No inline primary hex on builder chrome; buttons use a single primary class |
| TH-ST-06 | Forest `@theme` is global while therapist chrome ignores it | `main.jsx`, `forest-light-theme.css`, `index.css` | Do not remap `:root --primary` in phase 1. Scope `.forest-light` / therapist shell when TH-01 migrates | Admin `/admin/cases` still uses existing indigo/teal after therapist home migrates |

### Mobile

| ID | Problem | Affected | Proposed fix | Acceptance criterion |
|----|---------|----------|--------------|----------------------|
| TH-MO-01 | `--portal-bottom-nav-offset` is 76px, then 72px at 768px; IEP sticky footer is `bottom: 0` | `index.css`, `forest-light-iep.css` `.sticky-footer`, IEP/observation builders | One offset token from the real tab height; footer `bottom: var(--portal-bottom-nav-offset)` plus safe-area | On iPhone-width viewport, Submit/Save are fully visible above the bottom tabs and home indicator; they do not overlap tab labels |
| TH-MO-02 | Double safe-area padding on `body` and `#root` | `index.css` | Apply inset on the shell only | Measuring padding-bottom of `body` + `#root` does not add two full `safe-area-inset-bottom` values |
| TH-MO-03 | Goal modal hides the preview rail below 768px | `StudentGoalCreateModal.jsx`, `.sg-modal` | Medium-form sheet (not a long-editor workspace); preview as a disclosure | On 375px: sheet ≤90dvh; Preview can be opened; primary Add is 44px and not covered by the keyboard |
| TH-MO-04 | Case status / edit-times modal is tall; keyboard can cover fields | `/therapist/cases` `.ic-case-status-modal` | Sheet with sticky 44px actions; scroll the fields | Focused input remains visible while the virtual keyboard is open |
| TH-MO-05 | Icon buttons at 38×38 | `/therapist/cases` `.cases-icon-btn` | 44×44 hit area | Every icon control’s clickable box is ≥44px on ≤900px |
| TH-MO-06 | Builder header and footer both show Save / Preview / Submit | `ClinicalBuilderShell.jsx` | Long-editor workspace: header actions hidden ≤900px; footer remains above portal nav | ≤900px: only one Submit for review control visible; it sits above bottom tabs (not `bottom: 0`) |

### Buttons

| ID | Problem | Affected | Proposed fix | Acceptance criterion |
|----|---------|----------|--------------|----------------------|
| TH-BT-01 | Therapist dashboard uses `.admin-btn` | `TherapistDashboardPage.jsx` | Therapist button classes matching Layer 2 variants | No `.admin-btn` class on `/therapist` after migration |
| TH-BT-02 | Duplicate submit not always announced | Session log submit, IEP submit | `aria-busy`, disable, label **Submitting…** | Double-click submit produces one network request; label reads Submitting… until response |
| TH-BT-03 | Share / PDF / Duplicate treated as equally forbidden | `ClinicalBuilderShell.jsx`, `IepBuilderPage.jsx`, `useIepReport.js` | **No unsupported capability:** keep authorised IEP PDF (`GET …/iep/pdf`) and share-with-parent; remove Duplicate; label observation print as Print | Therapist/admin IEP: Duplicate absent. PDF works for authorised users. Share only if the user can call share-with-parent. Observation preview Print uses local print, not a fake export |
| TH-BT-04 | `window.prompt('Environment name')` | `ObservationStitchBlocks.jsx` | Chip editor / labelled field | Adding an environment never opens a native prompt; value is kept on error |

### Navigation

| ID | Problem | Affected | Proposed fix | Acceptance criterion |
|----|---------|----------|--------------|----------------------|
| TH-NAV-01 | Overflow destinations look missing; bottom Menu branch is dead | `PortalShell.jsx` | Keep header ☰ as overflow; ensure drawer lists every `THERAPIST_NAV` item + profile + notifications; do not add a fifth tab without R-08 evidence | On 375px, therapist opens ☰ and reaches Invoices, Support, Meetings, Leave, Scheduling, Profile, Notifications |
| TH-NAV-02 | Bottom tab **Today** is `/therapist/logs`, colliding with Home’s “today’s work” | `THERAPIST_MOBILE_NAV` | Rename tab to **Logs**. Home stays `/therapist` with `end: true` | Tab label reads Logs; Home is not active on `/therapist/logs`; selected state is selected surface + text + indicator, not colour only |
| TH-NAV-03 | Case profile has no Reports tab; contract described `CaseReportsTab` | `CaseDetailPage.jsx` | Keep reports at `/therapist/reports` until Layer 4 is extended with a real tab | No empty Reports tab. From a case, user can open observation/IEP builders via existing target URLs |
| TH-NAV-04 | Back from case file | `CaseDetailPage.jsx` | Back returns to `/therapist/cases` | Hardware/browser back and in-app back land on My Cases, not login |

### Forms and feedback

| ID | Problem | Affected | Proposed fix | Acceptance criterion |
|----|---------|----------|--------------|----------------------|
| TH-FF-01 | Saving vs saved not revision-accurate | `ClinicalBuilderShell`, IEP `saveDraft` | Draft integrity: Saved only if response matches on-screen content; typing during save → Unsaved | User edits during Saving…; indicator does not show Saved for the stale payload; failed save keeps fields |
| TH-FF-02 | Session log submit must wait for server; extra native confirm in places | `SubmitSessionLogForm.jsx`, `DailyLogsPage.jsx` `window.confirm` | Commit after 2xx. If the log form already reviews fields, no extra confirm dialog | Failed submit leaves fields intact; list does not show submitted; no `window.confirm` |
| TH-FF-03 | Goal modal missing AI Assisted tab | `clinicalUiContract.js` `GOAL_MODAL_TABS` | Add tab; generate only on button click using `POST /reports/{id}/clinical/generate-goal-strategy-drafts` | Three tabs visible; no generate call on modal open; Add writes via existing IEP goal/strategy endpoints |
| TH-FF-04 | Filter/status label “Missing” on logs | `FilterBar.jsx`, `StatusBadge.jsx` | Keep as data-state if needed; never “Missing Data” | UI does not contain the banned string `Missing Data` |
| TH-FF-05 | No dirty-navigate / 401 / upload / conflict rules on editors | IEP, observation, session log | Implement Layer 2 draft integrity | Leaving a dirty IEP prompts stay/leave; 401 keeps fields and retries after sign-in; failed upload keeps the file; newer local edits survive an in-flight save |

### Accessibility

| ID | Problem | Affected | Proposed fix | Acceptance criterion |
|----|---------|----------|--------------|----------------------|
| TH-A11Y-01 | Many inputs `outline: none` without `:focus-visible` | `index.css`, `my-cases.css` | Restore 2px ring | Keyboard tab through dashboard, cases, log form shows a visible ring on every control |
| TH-A11Y-02 | Proposed palette not verified, including default control borders | Token remap PRs | Contrast check for text, **unfocused** control border, and focus ring | Recorded ratios; control border ≥3:1 on surface without focus; `#526057` adjusted if &lt; 4.5:1 |
| TH-A11Y-03 | Dialogs without consistent labelling | Goal modal, case status modal | Sheets: `role="dialog"`; long editors are workspaces not dialogs | Escape closes sheets; focus returns to the opener; IEP is not announced as a dialog |
| TH-A11Y-04 | No zoom/reflow check | Therapist home, logs, IEP | 200% zoom and 320px reflow | Primary Save/Submit remains tappable at 200%; logs/IEP read in one column at 320px |

---

## Phase 2 — Client / parent

### Styling

| ID | Problem | Affected | Proposed fix | Acceptance criterion |
|----|---------|----------|--------------|----------------------|
| PA-ST-01 | Parent home purple glass hero `#6366f1 → #7c3aed` | `/parent` `parent-dashboard.css` | Warm background, white surface, Forest primary for the single next-step CTA | Hero has no multi-stop purple gradient; next appointment/update is the first readable heading |
| PA-ST-02 | Mixed `.admin-btn` and `.parent-reports__btn--primary` | `ParentReportsPage.jsx`, `ParentCaseDetailPage.jsx`, `ClientDashboardPage.jsx` | Parent button variants only | No `.admin-btn` on `/parent*` after migration |
| PA-ST-03 | Dense clinical jargon on home | `ClientDashboardPage.jsx` | Plain language + progressive disclosure | Home states next step in one sentence; IEP internals live behind Reports / case tabs |

### Mobile

| ID | Problem | Affected | Proposed fix | Acceptance criterion |
|----|---------|----------|--------------|----------------------|
| PA-MO-01 | Parent bottom nav is indigo glass `blur(16px)` and may exceed offset | `index.css` `.app-mobile-tabs--app`, `PortalShell.jsx` | Solid surface, 44px items, offset matches height | Tabs do not overlay Billing/Reports content; no backdrop-filter |
| PA-MO-02 | `/parent/book` not on bottom tabs; Billing is | `PARENT_MOBILE_NAV` | Target tabs Home · Sessions · **Schedule** · Reports; Billing in ☰ + Home alerts. **Assumption R-01** — do not reverse without usage evidence | On 375px, Schedule is a bottom tab; Billing is in ☰; overdue Home alert still reaches `/parent/billing` in one tap |
| PA-MO-03 | Parent reports modal is a good **short** sheet — not for long editors | Other parent dialogs vs IEP preview | Sheets for book/reschedule; IEP parent preview is a workspace | Book sheet fits `100dvh`; parent IEP preview is full-screen, not a 50% sheet |

### Buttons

| ID | Problem | Affected | Proposed fix | Acceptance criterion |
|----|---------|----------|--------------|----------------------|
| PA-BT-01 | Multiple parent primary classes (`parent-pay`, `parent-reports`, `parent-support`, `parent-case-card`) | parent CSS files | One parent primary/secondary/tertiary/destructive | Same height (44px) and radius (8px) on book, pay, support submit |
| PA-BT-02 | Parent dashboard CTA `min-height: 40px` | `.parent-dashboard-hero__cta` | 44px | Computed height ≥44px at ≤900px |

### Navigation

| ID | Problem | Affected | Proposed fix | Acceptance criterion |
|----|---------|----------|--------------|----------------------|
| PA-NAV-01 | Case hub not in global nav (intentional) | `/parent/cases/:caseId` | Deep links from notifications/home cards | Opening a case notification lands on the correct tab; Back returns to Home or the referring list |
| PA-NAV-02 | Drawer must include support, meetings, profile, and (until R-01) whatever is not a tab | `PARENT_NAV` vs mobile tabs | Header ☰ lists every authorised destination | All eight desktop destinations are reachable on 375px |

### Forms and feedback

| ID | Problem | Affected | Proposed fix | Acceptance criterion |
|----|---------|----------|--------------|----------------------|
| PA-FF-01 | Booking and profile errors may show raw API `detail` | book + profile pages | Map to supportive copy | Failed book keeps selected slot and explains what to do next; no `Submission Failed` |
| PA-FF-02 | Billing tables on small screens | `ParentBillingPage.jsx` | Card list ≤900px | No horizontal-only table as the only billing view |

### Accessibility

| ID | Problem | Affected | Proposed fix | Acceptance criterion |
|----|---------|----------|--------------|----------------------|
| PA-A11Y-01 | Purple hero text contrast on gradient | parent dashboard | Verify after flattening | Body and CTA text ≥4.5:1 on the actual background |
| PA-A11Y-02 | Icon-only bottom tabs | `PARENT_MOBILE_NAV` | Visible label + icon (already labelled — keep) | Each tab has a visible text label, not icon-only |

---

## Phase 3 — Admin

### Styling

| ID | Problem | Affected | Proposed fix | Acceptance criterion |
|----|---------|----------|--------------|----------------------|
| AD-ST-01 | KPI values 30px and hover shadows | `index.css` `.kpi-value`, `.admin-stat` | Metric type step (1.25rem); 1px decorative border; no hover lift | Admin home KPIs use Metric size, not Display/30px; no indigo shadow on hover |
| AD-ST-02 | Admin teal pills vs future Forest primary | `admin-portal-mobile.css` | Keep teal until this chrome migrates; then selected surface `#EAF3EC` + primary green | After admin token remap, active pill is not `#0d9488` gradient; tables still dense on desktop |
| AD-ST-03 | Body/page stacked gradients | `index.css` body background | `#F7F8F5` (or current solid until remap) | No 155deg page gradient on `/admin` |

### Mobile

| ID | Problem | Affected | Proposed fix | Acceptance criterion |
|----|---------|----------|--------------|----------------------|
| AD-MO-01 | `AdminDataList` skipped; tables `min-width: 560px` | `AdminUsersPage`, `AdminClientProfilesPage`, `AdminPlatformStatsPage`, `AdminProductRulesTab`, `AdminHrReportsPage`, `LeaveManagementPage`, `InvoiceComposerPreviewPanel` | Wrap in `AdminDataList` + `AdminTaskCard` | ≤900px: those pages show cards, not a sideways-only table |
| AD-MO-02 | Admin drawers are side panels with 24px padding and no mobile override | `admin-drawer-backdrop` on People, assign, bulk assign, onboard | **Short/medium:** bottom sheet ≤900px. Not a clinical-editor workspace | Drawer does not overflow; 44px actions above the home indicator; People assign is a sheet, not a full-screen IEP-like workspace |
| AD-MO-03 | `AdminMobilePillTabs` `overflowIds={[]}` so More is unused | Support, People, Invoices, IEP | Put secondary modules in More as documented | IEP mobile still exposes Status, Planner, Uploader; finance tools live under More, not a squashed pill row |
| AD-MO-04 | Admin case mobile “Quick actions” repeats primary pills | `AdminCaseDetailMobileNav.jsx` | Secondary list excludes the four primaries | Overview/Timeline/Sessions/Reports appear once |

### Buttons

| ID | Problem | Affected | Proposed fix | Acceptance criterion |
|----|---------|----------|--------------|----------------------|
| AD-BT-01 | `.admin-btn` 8px padding; `--sm` 6px | `admin-portal.css` row actions | ≥44px on ≤900px including `--sm` | People table row actions are ≥44px tall on a 390px viewport |
| AD-BT-02 | HR pages inline `background: '#6366f1'` | `HRTherapistsPage.jsx`, `HRMemosPage.jsx` | Tokenised variants | No inline indigo hex on HR buttons |
| AD-BT-03 | `window.prompt` for password, TDS, reasons | `PeopleRowActions.jsx`, `AdminUsersPage.jsx`, `TherapistPayoutFinance.jsx`, `HRCasesPage.jsx` | Labelled dialog | Those flows never call `window.prompt`; values persist on error |
| AD-BT-04 | Disabled `pointer-events: none` without status text | `.admin-btn:disabled` | Keep disabled + visible reason/loading | Saving a person/invoice shows Saving… and does not swallow clicks silently |

### Navigation

| ID | Problem | Affected | Proposed fix | Acceptance criterion |
|----|---------|----------|--------------|----------------------|
| AD-NAV-01 | Destinations beyond 3–4 bottom tabs must live in the drawer | `PortalShell.jsx` `buildMobileTabs` | Drawer lists the filtered `adminNav` / `caseManagerNav` | CM on 375px can open Logs, Reports, IEP, Meetings, Support without a desktop sidebar |
| AD-NAV-02 | Duplicate “Reports” / “Cases” labels across finance and operations sections | `adminNav` | Keep routes; disambiguate labels (Client invoices vs Reports) | Two sidebar items named Reports are not shown without a section heading visible |
| AD-NAV-03 | `/admin/client-profiles` and `/admin/cm/logs` missing from sidebar | those routes | Link from People / CM home; do not hide the route | Authorised admin can open client profiles from People; CM can open log review from CM home |

### Forms and feedback

| ID | Problem | Affected | Proposed fix | Acceptance criterion |
|----|---------|----------|--------------|----------------------|
| AD-FF-01 | “Invalid invoice.” | `AdminClientInvoicePage.jsx` | Supportive empty/error copy | Missing invoice shows guidance + back to invoice list; string `Invalid invoice` gone |
| AD-FF-02 | Login punitive copy; mismatch used as a catch-all in product copy | `portalLogin.js`, `LoginPage.jsx` | Failure-specific Layer 1 table | Wrong password ≠ portal-mismatch sentence. Strings `Invalid Login` and `Invalid credentials` gone |
| AD-FF-03 | Approvals and payouts mix native confirm with preview | log approve, report publish, `TherapistPayoutFinance.jsx`, invoice preview | Consequence policy: preview/review = no extra dialog; irreversible list actions = labelled dialog; outcome after 2xx | Invoice preview Submit has no second confirm. Deactivate user uses a labelled dialog. Failed approve leaves prior state |

### Accessibility

| ID | Problem | Affected | Proposed fix | Acceptance criterion |
|----|---------|----------|--------------|----------------------|
| AD-A11Y-01 | Drawers `role="presentation"` | admin drawers | `role="dialog"` + label | Screen-reader announces the drawer title; escape closes |
| AD-A11Y-02 | `AdminDataList` mobile `aria-label="List"` | `AdminDataList` | Specific label per page (“Session logs”, “Cases”) | Accessible name includes the entity |
| AD-A11Y-03 | Focus rings diverge (teal login, indigo portal, none on admin inputs) | admin forms | One `:focus-visible` token on migrate | Every admin filter and text field shows a 2px ring on keyboard focus |

---

## Cross-cutting (do in the phase that first touches the file)

| ID | Problem | Phase | Acceptance criterion |
|----|---------|-------|----------------------|
| X-01 | Skip-link exists — keep it | All | `#main-content` remains the skip target on shell and login |
| X-02 | `prefers-reduced-motion` exists — keep it | All | No new unbounded animation |
| X-03 | Contrast gate for proposed palette | First token-using PR | Recorded ratios for text, **unfocused control border**, focus ring; secondary `#526057` adjusted if &lt; 4.5:1 |
| X-04 | No global stylesheet replacement | All | Therapist migration PR does not change parent/admin computed `--primary` |
| X-05 | Usability targets without baselines | Session log, observation, monthly review PRs | PR records a pre-change walkthrough duration or median; no “faster” claim without it |
| X-06 | Stitch visual-match without files | Case overview / reports tab / IEP PNG claims | Fail review if the PR cites missing `docs/design/stitch/` as accepted |

---

## Out of scope for implementation PRs until the contract is extended

- New case-profile Reports tab (`CaseReportsTab`) — add to Layer 4 **and** recover or replace the Stitch artefact first.
- Rebuilding `clinical-theme.css` / purple `ClinicalCard`.
- Merging parent and therapist bottom-nav styles into one bar.
- Duplicate plan (unsupported capability).
- Claiming visual compliance with missing Stitch files.
