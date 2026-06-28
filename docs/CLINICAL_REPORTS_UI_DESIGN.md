# InsighteCase Clinical Reports UI Design

**Status:** Strict visual contract for Cursor and human implementers.  
**Reference:** Stitch project *Observation Report Builder* (`5191405174740405927`)
- Overview: `dca7b11651744545a1157b3a0e89db3a` → `docs/stitch/5191405174740405927/case-profile-improved-overview.{png,html}`
- Logs: `7ffaa127da08468bbd501c4a6819e929` → *Case Profile - Optimized Logs & Insights View*
- Reports Home (desktop): `4a4dd77577854b2db4d483e5287f7a0e` → `docs/stitch/5191405174740405927/reports-home-lush-clinical.{png,html}`
- Reports Home (mobile): `9251f3c432624f16bcf76bc3b1ca8935` → `docs/stitch/5191405174740405927/reports-home-mobile.{png,html}`

> Do not reinterpret the UI. Reconstruct the approved design system using existing colors, backend schema, routes, and component logic.

---

# Design Drift Warning

If the implementation begins to visually diverge from the approved Stitch reference, **stop and ask for clarification**.

Do not “improve” the design by inventing a different dashboard style.

**Target:**

- InsighteCase brand retained
- Stitch layout maturity adopted
- Clinical workflow clarity improved
- Backend untouched
- Role-safe information display

---

# InsighteCase Clinical UI Reconstruction Rules

## 1. Design Source of Truth

The approved UI direction is the Stitch-style clinical interface, not a generic SaaS dashboard.

When rebuilding screens, Cursor/AI must preserve:

- Existing InsighteCase color identity
- Existing left sidebar structure unless explicitly changed
- Existing backend schema and API contracts
- Existing routes and role permissions
- Existing clinical workflow logic
- Approved card-based clinical layout
- Mobile-friendly responsive behavior

Cursor must not invent a new visual language.

The goal is not to redesign the app from scratch.  
The goal is to reconstruct the current screens using a more mature clinical UI system.

---

## 2. Non-Negotiable Visual Principles

### Keep the current brand colors

Do not replace the app with a new green/black theme unless that theme already exists in the app.

Use the existing InsighteCase palette as the base:

- Deep green sidebar
- Off-white / light grey page background
- White clinical cards
- Indigo / violet accent for active tabs and primary links
- Soft green status pills
- Soft yellow for clinical guidance or caution cards
- Muted slate text for secondary information

Do not introduce harsh red, neon green, heavy black panels, or unrelated accent colors unless the status requires it.

### Use calm clinical spacing

The UI should feel like a clinical case workspace, not a sales dashboard.

Use:

- Generous white space
- 16–24px card padding
- Rounded cards (16px radius)
- Light borders
- Soft shadows only when needed
- Large readable headings
- Clear section grouping

Avoid:

- Dense widgets
- Over-decorated cards
- Emoji icons in production clinical UI
- Heavy gradients
- Arbitrary dark panels (including default dark “AI chatbot” panels)
- Excessive dashboard stats

---

## 3. Typography Rules

Use the existing app font stack.

Clinical UI typography should follow this hierarchy:

- Page title: 24–32px, semibold/bold
- Section title: 16–20px, semibold
- Card labels: 11–13px, uppercase only when useful
- Body text: 14–16px, readable line height
- Metadata: 12–14px, muted slate

Do not use mono/typewriter styling for normal clinical content unless it is a small technical label such as case ID.

Do not make the interface look like a developer dashboard.

---

## 4. Layout Rules

### Desktop case profile layout

Use this structure:

```text
Left Sidebar
└── Main App Shell
    ├── Case Header
    ├── Case Meta Row (status, service, support brief)
    ├── Top Tab Navigation
    ├── Alert / Internal Note Strip
    ├── Summary Metrics (4 cards)
    └── Two-column Clinical Workspace
        ├── Main Column (~8/12)
        │   ├── Case Summary
        │   ├── Active Goals Progress
        │   └── Recent Activity / Session Evidence
        └── Right Column (~4/12)
            ├── Clinical Guidance
            ├── Stakeholders
            └── Quick Actions
```

The main content area should not stretch into an empty dashboard.  
Every screen must answer: “What should the therapist or case manager do next?”

### Mobile layout

On mobile:

- Sidebar collapses into bottom navigation or hamburger (existing portal shell)
- Case header remains visible near top
- Tabs become horizontal scroll chips
- Cards stack vertically
- Right-column cards move below main content
- Primary action remains visible near top
- Avoid tables; use stacked cards

---

## 5. Case Header Contract

Every case profile screen must start with a consistent case header.

Required elements:

- Back link: `← My Cases`
- Child initials avatar
- Child name
- Case ID
- Status pill
- Service type
- Primary action button
- Optional secondary action button

Example structure (therapist):

```text
← My Cases

[AM] Aarav M.
IC-2026-041

[ACTIVE]

Shadow Support · Shadow support

[Request change]
```

Case manager variant may add a **Support brief** (strengths / environment / support needs — never diagnosis-first copy):

```text
Ira K.
[ACTIVE STATUS] [IC-2026-053]

Support brief
Short neuro-affirmative support summary

[Generate Insights] [Edit Case]
```

Do not place unrelated statistics above the case identity.

---

## 6. Tab Navigation Contract

Use top tabs inside the case profile.

Approved tabs (therapist case profile):

- Overview
- Reports
- Goals
- Strategies
- Logs
- Insights
- Documents

Rules:

- Active tab uses existing violet/indigo accent with underline
- Inactive tabs use muted slate
- Tabs must be horizontally scrollable on mobile
- Do not use a left-side sub-navigation for these sections
- Do not create duplicate navigation in cards

---

## 7. Card System

All cards must use a consistent clinical card component (`ClinicalCard` / `.clinical-card`).

Card style:

```css
background: white;
border: 1px solid var(--clinical-border);
border-radius: 16px;
padding: 20px;
box-shadow: subtle or none;
```

Cards should have:

- Clear title
- Optional metadata
- Main content
- Optional action link/button

Do not create different random card styles per section.

### Metric cards

Metric cards should be calm, not flashy. Row layout: label + value left, small icon box right.

Good:

```text
Evidence Events          [icon]
00

Active Goals             [icon]
00

Pending Reports          [icon]
02

Documentation            [icon]
In progress
```

Avoid:

- Large emoji icons
- Full-card red/green backgrounds unless urgent
- Too many metrics in one row
- Dashboard-like KPI styling with oversized purple numbers for text values

---

## 8. Clinical Guidance Card

Clinical guidance should be visually distinct but not overpowering.

Use **soft yellow** for suggested next steps; **soft green** for on-track states.

Example:

```text
CLINICAL GUIDANCE

Suggested next step

Create active IEP

[Open insights →]
```

Rules:

- Do not make this a dark AI chatbot panel by default
- Do not show unreviewed AI suggestions to parents
- Use “Clinical Guidance” or “Insighte AI Draft” depending on approval state
- Always show whether insight is draft, reviewed, or approved when AI content is shown

---

## 9. Role-Specific UI Behaviour

### Therapist view

Therapists need:

- Assigned cases
- Session log status
- Active goals
- Strategies to try
- Pending reports
- Internal notes
- Evidence upload
- Next session guidance

Primary actions:

- Start / continue session log
- Add observation
- View active goals
- Submit report
- Contact support

### Case manager view

Case managers need:

- Case health
- IEP completeness
- Goal quality
- Therapist documentation status
- Reports pending review
- Parent/school inputs
- Strategy effectiveness signals
- Clinical review actions

Primary actions:

- Edit case
- Create / review IEP
- Generate insights
- Review reports
- Assign or revise goals
- Message stakeholders

### Parent view

Parents should only see:

- Approved reports
- Child-friendly progress summary
- Goals being supported
- Home input requests
- Documents shared with family
- Feedback options

Parents must not see:

- Internal notes
- Unreviewed AI insights
- Therapist performance comments
- Clinical uncertainty flags
- Raw strategy confidence scores

---

## 10. AI / Intelligence UI Rules

AI must appear as an assistive clinical layer, not the main product.

Use labels carefully:

**Allowed:** Clinical Guidance, Suggested next step, Insighte AI Draft, Needs CM review, Evidence-based prompt, Pattern noticed

**Avoid:** AI diagnosis, AI decision, Automated clinical recommendation, Prediction, Score (unless clinically defined)

Every AI-generated block must show:

- Source basis: session logs, IEP, observation, parent input, etc.
- Review state: draft / reviewed / approved
- Action: accept, edit, dismiss, send for review

---

## 11. Buttons and Actions

### Primary button

Main workflow action: Generate Insights, Create IEP, Start Session Log, Submit for Review, Approve Report

### Secondary button

Supporting actions: Edit Case, Request Change, Upload Assessment, Print Summary

### Text action

Low-weight links: Contact support, View all logs, See evidence, Open history

Do not use many competing primary buttons in one screen.

---

## 12. What Cursor Must Not Do

Cursor must not:

- Replace the existing InsighteCase design language with a new unrelated UI
- Overuse black/dark clinical cards
- Add decorative UI not present in the approved direction
- Rename backend concepts without checking schema
- Create fake data models
- Break existing routes
- Remove existing role guards
- Add AI calls directly inside UI components
- Create new APIs unless explicitly asked
- Build static mock screens disconnected from the real app
- Use tables on mobile-heavy workflows where cards are better
- Make parent-facing screens show internal clinical notes
- Copy Stitch “Diagnosis Brief” / deficit-first copy — use strengths and support context instead

---

## 13. Implementation Instruction for Cursor

When implementing any clinical report screen:

1. First inspect the existing route, component, API call, and data shape.
2. Preserve the backend contract.
3. Identify the current UI sections.
4. Replace only the visual layout and component structure.
5. Reuse existing clinical UI components where available.
6. Create missing reusable components only if needed.
7. Do not change business logic unless explicitly requested.
8. Test the screen in desktop and mobile width.
9. Ensure role-based visibility remains intact.
10. Keep all copy neuro-affirmative, respectful, and clinically safe.

The expected output is a production-connected UI, not a static mockup.

---

# Design Acceptance Checklist

A screen is accepted only if it satisfies **all** of the following:

## Visual match

- Looks closer to the approved Stitch reference than the old app
- Preserves existing InsighteCase colors
- Uses calm clinical cards
- Uses top case tabs
- Does not look like a generic analytics dashboard
- Does not introduce a new design language

## Workflow match

- Therapist can understand what to do next within 5 seconds
- Case manager can see case status, reports, goals, and guidance clearly
- Parent-facing sections do not expose internal content
- Reports, goals, strategies, logs, insights, and documents are clearly separated

## Technical safety

- Existing API calls continue working
- Existing schema is not changed
- Existing permissions are not bypassed
- Existing route names are preserved unless explicitly approved
- No dummy hardcoded data remains in production files

## Mobile readiness

- Screen works at 390px width
- Tabs scroll horizontally
- Cards stack cleanly
- Primary action remains easy to access
- No horizontal table overflow

---

# Screen: Case Profile Overview (Phase 1 template)

**Route:** `/therapist/cases/:caseId?tab=overview`  
**Component:** `TherapistCaseOverviewDashboard.jsx`  
**Data:** `caseRow`, `clinicalProfile`, `qualitySummary`, `scheduleItems` — no new APIs.

## Component hierarchy (must match)

1. `CaseProfileShell` → `ClinicalCaseHeader` + `ClinicalTabs`
2. Internal clinical note strip (therapist/CM only)
3. `ClinicalMetricCard` × 4 in `.clinical-metric-grid`
4. `.clinical-two-col`
   - **Main:** Case summary (`ClinicalCard`) → Active goals progress (section + goal cards) → Recent activity (`ClinicalCard` + timeline)
   - **Side:** `ClinicalGuidanceCard` → Stakeholders (`ClinicalCard`) → Quick actions (`ClinicalCard`)

## Rollout order

Once Case Profile Overview matches this contract, reuse the same shell for:

- Reports tab
- Goals tab
- Strategies tab
- Logs tab
- Insights tab
- Documents tab

Do not rebuild the entire reports module until Overview is accepted.

---

# Cursor rebuild prompt (Case Profile Overview)

```markdown
You are rebuilding the InsighteCase clinical case profile UI.

Before coding, read:

- docs/CLINICAL_REPORTS_UI_DESIGN.md
- existing clinical UI components
- existing case profile route/component
- existing API calls and schemas used by this screen

Important:

The current UI must not drift into a generic dashboard. Reconstruct the case profile screen using the approved clinical UI rules.

Goal:

Rebuild the Case Profile Overview screen for therapist and case manager views.

Preserve:

- Existing backend contracts
- Existing role permissions
- Existing route structure
- Existing case data model
- Existing app colors
- Existing left sidebar shell

Implement the component hierarchy in “Screen: Case Profile Overview” above.

Design constraints:

- Match the approved Stitch-style structure more closely.
- Do not use the generic dark AI panel style unless explicitly requested.
- Do not invent new colors.
- Do not change schema or create fake API models.
- If a required field is missing, use safe fallbacks from existing case data.
- Keep all clinical copy neuro-affirmative and respectful.

After implementation:

- List files changed.
- Explain which components were reused.
- Explain any new components created.
- Confirm that no backend contract was changed.
```

---

## 14. Insights Tab — Visual Contract

**Canonical product doc:** [INSIGHTS_ENGINE.md](./INSIGHTS_ENGINE.md)

The Insights tab is a **simple on-demand snapshot workspace**, not a heavy analytics dashboard. Retire the 4-card `ClinicalQualitySummary` grid as the default Insights tab layout (quality cards belong on the Reports tab).

### Stable design direction (do not waver)

| Element | Rule |
|--------|------|
| **Palette** | Keep InsighteCase green sidebar + violet primary actions. Forest-green is allowed only as a **header accent strip** on the Ask AI panel — not a full dark chatbot shell. |
| **Layout** | Desktop: full-width main stack (stats → focus card → goal grid), then **full-width AI dock** at bottom. Mobile: AI dock sticky at bottom. No cramped right sidebar. |
| **Header** | Title + subtitle in one block; month selector on a **toolbar row below** (never floated far right). Helper: *AI runs only when you click Generate.* |
| **Focus card** | Light mint gradient (`#ecfdf5` → `#f8fffb`), 4-up stat tiles, safety chips, Generate CTA. After generation title becomes *Today's clinical focus*. |
| **Goal cards** | 2-column grid. Placeholder cards from structured preview when no snapshot; dashed border for placeholders. Alert insights use soft red callout — not harsh error red. |
| **Ask AI panel** | Green gradient header, pill suggestion buttons (2-col grid), inline Ask input, sources in footer. |
| **History** | Collapsible `<details>` under AI panel — not a third floating block. |

### Page header

- Title: **Insighte insights** (no subtitle)
- Insight type **pill tabs** (Full Snapshot, Goal Suggestions, Strategy Review, Supports, What's Not Working, Parent-safe Draft)
- Month selector compact, top-right of title row
- No helper banners ("AI runs only when…", safety chips, or preview hints)

### Data preview stats

Separate **white metric row** above the focus card (not inside the mint card):

- Sessions available · Active goals · Strategies used · Logs need details

### Monthly Clinical Snapshot generator card

Light green accent card (not global dark chatbot):

- Title: **Monthly clinical snapshot** (before generate) / **Today's clinical focus** (after generate)
- No safety chips, no insight-type dropdown (types live in header tabs)
- Primary: **Generate Insights**
- Secondary: **View Previous Snapshot**

**After generation** (same card area):

- Focus insight paragraph (neuro-affirmative)
- Actions: Save Snapshot · Add to Report · Send to CM Review · Regenerate

### Goal / support insight cards (below focus card)

Section title: **Goal insights** (generated) or **Preview focus areas** (pre-generate).

Simple cards — no charts or heatmaps:

- Goal title, status chip, evidence strength, session count
- Strategy chips where relevant
- Generated insight text (1–2 sentences)
- Text actions: View evidence · Add to report · View logs · Discuss with CM

Card types: goal progress · functional communication · what may need review · suggested supports · preview placeholders

### Right panel — Ask Insighte AI

- **Full-width bottom dock** on desktop; sticky bottom sheet on mobile
- Green gradient header with logo + title
- Four suggestion buttons in a row (desktop) / stack (mobile)
- Input + Ask button
- No footer sources list or token disclaimer

### Generation history

Collapsible block below AI panel: month — status — Open

### Responsive

- Desktop: main column + AI panel sidebar
- Mobile: stack AI panel below cards; stats 2×2; goal cards single column
- No large tables on this screen

### Do not

- Auto-run AI on tab open or month change
- Float month selector away from header block
- Use generic dark AI chatbot as default
- Show unreviewed internal insights to parents
- Add complex charts or heatmaps

---

## 15. Reports Tab (Case Profile) — Visual Contract

**Stitch reference:** Reports Home — Lush Clinical (`4a4dd77577854b2db4d483e5287f7a0e`) and Mobile (`9251f3c432624f16bcf76bc3b1ca8935`).  
**Assets:** `docs/stitch/5191405174740405927/reports-home-lush-clinical.{png,html}`

The case profile **Reports** tab is a single-client adaptation of Reports Home — not the global multi-case `MonthlyReportsPage`.

### Stable design direction (do not waver)

| Element | Rule |
|--------|------|
| **Default section** | `Overview` (`section=home`) — not Monthly |
| **Sub-tabs** | Overview · Observation · IEP · Monthly · Progress · Document Drive |
| **KPI row** | Four `ClinicalMetricCard` tiles: Drafts · Under review · Published · Needs attention |
| **Pipeline grid** | Five report-type cards (2-col desktop, 1-col mobile) with status badge, progress bar, optional amber alert, text CTA |
| **Data sources** | `GET /reports-workbench` + `GET /clinical-quality-summary` — no new backend |
| **Removed from top** | Raw `ClinicalQualitySummary` 4-card grid (metrics folded into Overview) |

### Overview layout

1. **Page header:** Reports + subtitle naming the child
2. **Metric row:** case-scoped pipeline counts from monthly report statuses + quality summary
3. **Suggested next steps** (optional amber panel when `recommended_next_actions` present)
4. **Report pipeline** cards linking to sub-sections

### Report type cards

Each card includes:

- Title + one-line subtitle
- Status badge (observation / IEP / monthly / progress / drive)
- Progress bar with short meta label
- Amber alert when documentation gap exists
- Text action: Open / Continue / Create draft

### Sub-sections

Selecting a sub-tab or clicking a pipeline card sets `?tab=reports&section=<id>`. Monthly section keeps existing `CaseReportsPanel` workflow copy.

### Responsive

- KPI row: 4 → 2 columns on mobile
- Pipeline grid: 2 → 1 column on mobile
- Touch targets ≥ 44px on CTAs

### Do not

- Rename this tab "Monthly Reports" in case profile context
- Reintroduce the quality summary 4-card grid above sub-tabs
- Add cross-case search on case profile Reports tab
- Change backend report contracts for layout-only work
