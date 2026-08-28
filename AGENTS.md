## Learned User Preferences

- When implementing an attached plan, do not edit the plan file; use existing todos and mark them `in_progress` rather than creating duplicates.
- Prefer phased delivery (core backend and admin MVP first, then tickets, IEP, exports) unless the user explicitly asks for a full single-pass build.
- Keep a case-centric data model: one `User` with roles/permissions, `case_assignments` with history—never rely on `case.therapist_id` alone.
- Set client billing amounts and therapist pay share when a case is created; admin/HR may revise later.
- Assign module-based product access when creating admin/support users (homecare, shadow_support, billing, etc.).
- Therapist access is scoped to own cases, session logs, invoices, tickets, and profile—not other therapists' data.
- Incident reporting should be available across relevant service lines (e.g. shadow and homecare), not a single product only.
- Use frontend/UI design skills when improving portal layouts (login sizing, admin dashboard density, therapist quick actions).
- Invoice UX should support case-by-case preview, session review, late/extra sessions before submit, and admin breakdown review.
- Prefer **Grok** (`cursor-grok-*`) and **Composer** (`composer-*`) models for subagents, parallel exploration, and browser/UI verification to manage token spend. Use heavier reasoning models (Opus, Sonnet thinking, GPT Sol xhigh, etc.) only when the user explicitly picks one or the task clearly needs deep multi-file reasoning.

## Documentation

- [docs/README.md](docs/README.md) — full documentation index
- [CONTRIBUTING.md](CONTRIBUTING.md) — team PR workflow, pre-push/release scripts, hooks
- [CHANGELOG.md](CHANGELOG.md) — update `[Unreleased]` on every merge; date section before prod release
- [docs/TEAM_OWNERSHIP.md](docs/TEAM_OWNERSHIP.md) — area owners and CODEOWNERS
- [docs/GITHUB_SETUP.md](docs/GITHUB_SETUP.md) — branch protection (admins)
- [docs/ENVIRONMENT_VARIABLES.md](docs/ENVIRONMENT_VARIABLES.md) — all env vars (local, Railway, Vercel)
- [docs/AGENT_WORKFLOW.md](docs/AGENT_WORKFLOW.md) — delivery, RBAC, billing, deploy, and agent checklists (from chat workflow capture).
- [docs/DATA_IMPORT.md](docs/DATA_IMPORT.md) — production bulk import for therapists, families, and cases (templates and API order).

## Team workflow (humans + agents)

- **Do not push directly to `main`.** Use a PR; CI (`backend`, `frontend`, `vercel-monorepo-build`, `contributor-guards`) must pass.
- **Before push:** `./scripts/pre-push-check.sh` or `make check`.
- **Before production release:** `./scripts/pre-release-check.sh` + [docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md) + move [CHANGELOG.md](CHANGELOG.md) `[Unreleased]` to a dated heading.
- **One concern per PR** when possible; RBAC/migration changes need tests.
- Agents: still **commit only when the user asks**; when committing, follow [CONTRIBUTING.md](CONTRIBUTING.md) message style.

## Deploy split (do not confuse names)

| Platform | Project / service name | What runs there |
|----------|------------------------|-----------------|
| **Railway** | `case-manager-new` (repo `Insightee/case-manager-new`) | FastAPI API, Postgres, Redis — all backend env vars |
| **Vercel** | **`insightes-projects/frontend`** only (`prj_ibo0tJpTFO1Y8d5cKiKicB7Yr6vN`) | Vite React UI — **`VITE_API_URL` only** |

Never use Vercel project `case-manager-new` (deleted duplicate). CLI: `vercel … --scope insightes-projects --project frontend`. See [docs/RAILWAY_VERCEL.md](docs/RAILWAY_VERCEL.md).

## Learned Workspace Facts

- Monorepo layout: `backend/` (FastAPI, SQLAlchemy, Alembic), `frontend/` (Vite + React + Tailwind), `docker-compose.yml` for Postgres, Redis, and API.
- Local dev: from `backend/` run `python3 -m app.seed.demo_seed` then `uvicorn app.main:app --reload --port 8000`; from `frontend/` run `npm run dev` on port 5173 with `/api` proxied to the API.
- Demo sign-in uses seeded accounts such as `superadmin@demo.com` and `therapist@demo.com` with password `demo123` (see `backend/README.md` for the full role matrix).
- `Case` is the operational source of truth; sessions, daily logs, reports, invoices, payouts, and incidents link back to cases.
- Seeded roles include SUPER_ADMIN, ADMIN, CASE_MANAGER, SUPERVISOR, THERAPIST, FINANCE, HR, PARENT, and SCHOOL_COORDINATOR.
- Case billing uses `PER_SESSION` and `PACKAGE` types with therapist compensation modes (e.g. percentage share, fixed lump); logic lives in `invoice_billing_service` and admin case forms.
- Product modules are defined in `backend/app/core/modules.py` (`homecare`, `shadow_support`, `billing`) and gate admin/support feature access.
- Frontend portals live under `admin-portal/`, `hr-portal/`, therapist routes, and parent routes, with role-aware login on `LoginPage.jsx`.
- After schema changes, run Alembic migrations (`alembic upgrade head` from `backend/`) before re-seeding or E2E checks.
- Backend tests run with `python3 -m pytest app/tests -q` from `backend/`; billing and admin portal have dedicated test modules.
- The stack is SQL-based (SQLite default locally, Postgres via Docker)—not MongoDB; plugin guidance is advisory only.

## INSIGHTECASE GLOBAL RULE
### Founder Doctrine → Clinical Intelligence System

#### 1. THE CLINICAL DOCTRINE (THE SOUL)
We are not building forms. We are building the world's largest neuro-affirmative clinical intelligence engine. Every session, observation, strategy, goal, report, and interaction must contribute to a growing knowledge graph that helps therapists, children, and families.

* **Connection Before Correction**
  * *Technical Rule*: The system never punishes users. Input errors must become contextual guidance.
  * *Banned UI Strings*: `Invalid Form`, `Submission Failed`, `Missing Data`.
  * *Required UX Alternatives*:
    - *"Looks like we still need a few details before we can save this."*
    - *"Would you like to continue from where you left off?"*
    - *"Let's add one more observation."*
  * *Code Implementation Guardrail*: Optimistic UI is the absolute default. Always update local state immediately on action and reconcile with backend asynchronously. Users must feel progress, not compliance.
* **Neuro-Affirmative First**
  * *Technical Rule*: Never frame children as deficits. Diagnostic-first architecture is strictly forbidden.
  * *Database Schema Hierarchy*: `Child` ──> `Environment` ──> `Support` (NOT `Diagnosis` ──> `Problem` ──> `Fix`).
  * *Data Layer Isolation*: All schemas tracking child state must explicitly separate data points into distinct tables or strongly typed JSON columns matching these exact keys: `strengths`, `support_needs`, `environment_factors`, `participation_patterns`, `strategies`, `progress_signals`, `challenges`.
* **Every Session Creates Knowledge**
  * *Technical Rule*: Free text is a liability; structured signals are organizational assets.
  * *UI Component Directive*: Prioritize relational select sheets, multi-select chips, slider levels, and explicit goal/strategy cross-link dropdowns. Free-text narratives should enrich existing structured intelligence layers, never replace them.

#### 2. THE CLINICAL BRAIN (THE KNOWLEDGE ENGINE)
Every data point must be reusable. The system learns through relationships.

* **Core Knowledge Graph Sequence**: `Child` ──> `Observations` ──> `Challenges` ──> `Goals` ──> `Strategies` ──> `Sessions` ──> `Evidence` ──> `Progress` ──> `Reports`
* **Strategy & Goal Intelligence**
  * *Data-Tier Architecture*: Every user-created strategy must be indexed with structural metadata: `strategy_id`, `goal_id`, `environment_context`, `age_range`, `support_level_tier`, `therapist_id`, `outcome_rating`, `confidence_score`, and `frequency_count`.
  * *Goal Approval Pipeline*: New therapist-created goals must route to an isolated staging state (status: `"pending_review"`) for Case Manager moderation before graduating into the global `goal_library` asset pool.
* **AI Engine Constraints**
  * *The Absolute Limit*: AI does not create clinical truth; it condenses it.
  * *Allowed Actions*: Generating rough report drafts, condensing session timelines into summaries, recommending library-matched goals/strategies, detecting behavioral patterns.
  * *Forbidden Actions*: Finalizing a report status to `"Complete"`, executing automated clinical diagnoses, or mutating/overriding direct therapist inputs.

#### 3. TOKEN ECONOMY (THE COST ENGINE)
AI spend must scale slower than revenue. **Golden Rule**: Store once, reuse forever.

* **Code-Level AI Trigger Constraints**
  * *Strictly Banned Patterns*: Triggering LLM API endpoints or embedding lookups inside component `onChange`, `onScroll`, row-expansion, page loading, or active input fields.
  * *Allowed On-Demand Actions*: Explicit user clicks on action buttons: `[Generate Report]`, `[Generate Summary]`, `[Generate Insights]`, `[Run Clinical Review]`.
* **Context Compression Architecture**
  * *The Token Rule*: Pass ID tokens and structural flags over prose. Read 20 array markers instead of 500 words of narrative string wherever possible.
  * *Compression Pipeline Requirement*: Before shipping logs to an LLM context window, your backend services must map a raw array of `session_logs` through a compression utility function to output a tight, heavily truncated `ClinicalSnapshot` object. This must hit a target of 80-95% reduction in raw string length.
* **Four-Tier Intelligence Routing**
  * When writing backend operations, always implement the lowest numeric layer capable of resolving the problem:
    - *Layer 1*: Relational SQL / Deterministic Rules Engine (For data validation, basic scoring, status gates).
    - *Layer 2*: Postgres/Supabase Foreign Key Graph Joins (For tracking history, lineage, and entity mapping).
    - *Layer 3*: Vector Embeddings cosine similarity (For searching matching historical goals/strategies).
    - *Layer 4*: LLM Execution (Only for unstructured natural language synthesis and finalized report text drafting).

#### 4. CASE MANAGER OPERATING SYSTEM
Case Managers review exceptions, not manual data entries.

* **Exception Queue Trigger Vectors**
  * Route items to the manual `review_queue` table if and only if any of the following triggers return true:
    - `is_edited_after_completion = True`
    - `has_timestamp_mismatch = True`
    - `has_critical_goal_drift = True`
    - `incident_reported = True`
    - `is_report_overdue = True`
    - `is_progress_trend_anomalous = True`
    - `has_flagged_parent_concern = True`
    - `has_flagged_therapist_concern = True`
    - `has_repeated_absences = True`

#### 5. MOBILE-FIRST CLINICAL UX & WORKFLOWS
Design explicitly for field work on touchscreen form factors.

* **The Timing Caps**: Session Log Entry < 5 min; New Observation Entry < 15 min; Monthly Report Verification < 10 min.
* **Ergonomics & UI Layout**
  * *Thumb Zone Binding*: Primary active targets (*Save*, *Complete*, *Submit*, *Voice Note Recording*, *Camera/Evidence Upload*) must be positioned within bottom-sheet sheets or sticky footer arrays accessible easily via single-hand operation.
  * *Progressive Disclosure Directive*: Components must strictly bound view states to the current step context. Hide global profiles, extensive client timelines, or historic records into hidden tabs, exposing them only via deliberate action clicks.

#### 6. REPORT GENERATION ENGINE
No feature can require duplicate data entry.
* **Observation Report**: Initial challenges + strengths + environment_map ──> Outputs `initial_goals`
* **IEP (Individualized Ed. Program)**: `goal_framework` + `strategy_framework` + `measurement_framework`
* **Session Logs**: Real-time `evidence_payload` + `progress_signals` + `strategy_effectiveness_metrics`
* **Monthly Report**: `iep_baseline` + Compounded `session_logs` + `evidence_blobs` + `parent_inputs`
* **Progress Report**: Time-series aggregation of all `monthly_reports` + `goal_trends` + `strategy_trends`

#### 7. THE INSTITUTION RULE
Every single feature code branch generated by this agent must structurally prove:
1. What immutable structured knowledge does this create?
2. Can this asset be systematically reused across other client pipelines?
3. Does this reduce the therapist’s screen-time friction?
4. Does this systematically lower our LLM context token usage?
5. Will this specific table structure and layout sustain performance at 10,000 parallel clients?

