# INSIGHTECASE HEALTH CHECK

**Audit date:** 29 August 2026  
**Method:** Code, schema, tests, and git history (16 May–29 August 2026). Existing docs were treated as clues, not truth.  
**Scope:** Inspection only. No production code, data, or permissions were changed.  
**Evidence grades:** **CONFIRMED** = read in current source. **STRONG INFERENCE** = several files agree, runtime not executed. **POSSIBLE RISK** = architecture allows it. **BUSINESS INTENT UNKNOWN** = code cannot decide policy.

---

## Architecture discovered (before conclusions)

| Layer | What actually exists |
| --- | --- |
| Backend | FastAPI (`backend/app/main.py`), SQLAlchemy ORM, Alembic (~132 revisions), Redis for sessions/rate limits |
| Frontend | Vite + React JSX (`frontend/src/routes/AppRoutes.jsx`) — therapist, parent/client, and staff/admin portals |
| Database | Postgres in production (Railway); SQLite allowed locally. ~70 model files |
| Auth / RBAC | JWT + portal-split login. 11 roles. Permissions in `backend/app/core/permissions.py`. Clinical access via `service_access_grants`; org capabilities via `org_capability_grants` |
| Products | Clinical lines from `service_categories` (fixed IDs `homecare`, `shadow_support`). Org modules: `billing`, `people_admin`, `hr_ops`, `service_catalog_admin` |
| Jobs | Three Railway crons (email retry, meeting reminders, 22:00 IST session close). No Celery. Request-time BackgroundTasks for email |
| Storage | Local or Cloudflare R2 |
| Money flags | `ENABLE_BILLING`, `BILLING_LEDGER_WRITES`, payout export/release all **default false** (`config.py`) |
| Integrations | Zepto/SMTP email. Zoho ID stored on cases; Zoho Books push env-gated (default no-op). Payments always mock. MCP read-only. **No WhatsApp/SMS. No live LLM.** |
| CRM | **No lead pipeline.** Client ops = Child + Parent + Case. Zoho is a stored ID, not a CRM |

This is a **case-centric operations OS** that grew from a greenfield repo on 16 May 2026 (520 commits, ~15 weeks). Finance, HR, and clinical teams added rules independently. The spine is real. The money and status contracts are not yet one contract.

---

## Overall system health

# AMBER

InsighteCase **does run as an operating system for cases, sessions, logs, leave, and people**. It is **not yet trustworthy as a single finance + HR + CRM source of truth**.

The product is younger than it looks. Parallel money engines, leftover statuses, and feature flags mean “what the screen shows” and “what Finance can collect or pay” can diverge depending on environment.

Amber, not Red: therapists can run a day, cases have a real status machine, and most dangerous money writes are **off by default**. Amber, not Green: those same flags, leftover tables, and unenforced eligibility rules mean the organisation cannot yet treat the database as one book.

---

## Scorecard

| Area | Rating | Why |
| --- | --- | --- |
| Architecture coherence | **Amber** | Case-centric spine is real (`cases` + `case_assignments`). Around it sit two report engines, two+ billing rails, leftover parent statements, and module gates split across `modules.py`, `feature_flags.py`, and frontend. |
| CRM workflow | **Amber** | There is no lead → convert pipeline. “CRM” is case allotment, status, tickets, meetings. That works for operations. It does **not** answer “when did this become a billable client?” as a CRM event. |
| HR workflow | **Amber** | Leave, onboarding, profiles, caseload, memos exist. Eligibility is a **picker filter**, not an assignment lock. Inactive/resigned therapists can remain assigned. `employment_status` and `is_active` can desync. |
| Finance integrity | **Amber / Red** | Therapist invoices and client invoices are separate live rails. Ledger is the *intended* client SSOT but writes default **off**. Package counters and package-cycle tables can drift. Payout release is flagged off. **Do not treat dashboards as reconciled.** |
| Clinical / case workflow | **Amber** | Session start/end/log/absence is mature and tested. Suspended / pending-replacement cases can still start sessions (**CONFIRMED** gap). Dual report stacks. Structured evidence still flagged off. |
| Product consistency | **Amber** | Homecare vs shadow differences are mostly **intentional** (day type, duration caps, leave credits). Some drift: absence billing paths, calendar-day payout, eligibility bypass on assignment API. |
| Data integrity | **Amber** | Many invariants are service-level only. Inactive assignment, suspended+in-progress session, leftover `PERCENTAGE` enum, free-string attendance — all technically possible. |
| Permissions | **Amber** | Backend `require_permission` is the real gate. Frontend hide is UX. Weak spots: HR therapist update on `therapist.read`; assignment POST skips allotment eligibility; therapist can PATCH own `employment_status` without flipping `is_active`. |
| Automation reliability | **Amber** | Three crons are clear. Incident SLA only runs when someone lists incidents. Parent auto-suspend is synchronous on close. Day-end “opportunistic hook” is documented but not on request paths. |
| Test protection | **Amber** | ~182 backend test modules; strong on isolated rules. Weak on **cross-team golden journeys** (CRM→session→invoice→payout; HR exit→assignment→payout). |
| Legacy debt | **Amber / High** | `DEACTIVATED`, `PERCENTAGE`, `parent_billing_statements`, unused `resolve_session_financial_effect`, old `payouts` table, IEP v1 beside clinical engine. Not cosmetic — some still execute. |

---

## Plain answers

### 1. Is InsighteCase currently one coherent system?

**PARTIALLY**

One spine: **Case → assignment → session → log → report / invoice**.  
Several attached systems that do not always notify each other: client billing ledger (often not writing), therapist invoice engine, package cycles, clinical vs legacy reports, HR employment vs assignment, Zoho ID vs Zoho Books.

A feature can “work” on its page and still fail the next team.

### 2. Can we trust Finance numbers?

**WITH CONDITIONS**

Trust **submitted therapist invoice snapshots** and **confirmed client payments** more than live previews or Control Tower KPIs.

Do not trust, without checking flags and source:

- Package “remaining” if anyone also used cycle/rollover screens (`care_packages.used_sessions` vs `client_package_cycles` — **CONFIRMED** consume path does not update cycles).
- Ledger totals when `BILLING_LEDGER_WRITES=false` (default).
- Control Tower as “reconciled” while `finance_cutover_complete` is false.
- Percentage-of-client pay (enum leftover; live path is rupee lump).
- Any number computed only in the therapist invoice exclude-toggle UI (`invoiceUtils.applyLocalExcludes`) until submit.

### 3. Can we trust client/case status?

**WITH CONDITIONS**

Live status is **one column**: `cases.status`. There is no separate `client_status`. That is good.

Conditions:

- `DEACTIVATED` still exists (legacy closed). New closes should be `CLOSED`.
- Therapist requests and admin changes use different allowed maps.
- Approving a therapist status request can **fall back** to writing `case.status` without the audit path if the transition is not in the admin map (**CONFIRMED** in case-status service).
- `SUSPENDED` / `PENDING_REPLACEMENT` cancel future bookings but **do not block session start** the way `CLOSED` does.

### 4. Can we trust therapist/employee status?

**WITH CONDITIONS**

Three different facts:

| Fact | Where | Meaning |
| --- | --- | --- |
| Can they log in? | `users.is_active` | Auth gate |
| Employment label | `users.employment_status` (`ACTIVE` / `SUSPENDED` / `ARCHIVED`) | HR label |
| Clinical profile | `therapist_profiles.status` (`DRAFT`…`APPROVED`…`PAUSED`) | Allotment picker |

Deactivating a user does **not** end `case_assignments`. Allotment list hides inactive people; the assignment API does not re-check. **STRONG INFERENCE:** an exited therapist can remain the live assignee.

### 5. Are product modules using common logic?

**PARTLY**

Shared: case status machine, assignment table, session start rules, pending-log gate, RBAC catalog.

Intentional differences: shadow/B2B day type; longer auto-end for shadow; homecare-only leave is unpaid; calendar-day payout for shadow/B2B.

Likely drift: assignment eligibility enforced only on allotment picker; child-absent billing has extra shadow ledger path; two package-effect helpers disagree on therapist-leave pay.

### 6. Is old logic still influencing current behaviour?

**Yes. Major examples:**

1. **`DEACTIVATED`** — still a legal status; reopen and billing cutoff still treat it.
2. **`CompensationMode.PERCENTAGE`** — enum + columns remain; Aug 28 coerce to `FIXED_LUMP`; resolver prefers `therapist_fixed_pay_inr`.
3. **`parent_billing_statements`** — still seeded and listed; parent portal money is `client_invoices`.
4. **`resolve_session_financial_effect`** — written as the central brain; **zero production callers**. Live policy is `upsert_from_session_event` + `package_unit_effect_for_status`.
5. **Legacy monthly/observation reports** always mounted; clinical engine is a second stack behind a flag.
6. **`is_additional_visit`** vs `add_on_kind` — both written; ledger history never rewritten.
7. **Old `payouts` table** vs new payout batches/transfers.
8. **Acceptance gating columns** exist; `ACCEPTANCE_GATING_ENABLED` defaults false.

### 7. What changed most dramatically in the last 3 months?

1. Finance engine Steps 1–6 (Aug 2) — monthly fixed, ledger expansion, write flags.
2. Client billing loop + mock payments + package cycles (Aug 4).
3. Finance writable corrections, payout settlement, grievances (Aug 4–5).
4. Clinical reports / IEP engine v2 (Aug 19–20) beside May IEP builder.
5. As-of rates + dual-therapist payout locks (Aug 29, current HEAD).
6. Session financial-effect contract + 10 PM IST auto-close (Jun 24).
7. Client status machine: replacement + deactivated (Jun 16) then auto-ACTIVE on assign (Jul 10).
8. Allotment stays pending until activate (May 29) — later also promoted by assign.
9. Mid-month therapist transition + half/full day (Aug 13–20).
10. Read-only MCP / integration API (Aug 26).

### 8. Where are Finance, HR and CRM currently contradicting each other?

**Operational language:**

- **CRM/Clinical** can suspend or replace a case. Future bookings cancel. **Finance** uses `status_effective_date` as a billing cutoff. **Clinical** can still start a session on a suspended case. Those three facts do not match one policy.
- **HR** marks someone archived/inactive. **CRM** can still have them as the active assignee. **Finance** may still calculate payout against that assignment until someone ends it.
- **HR** leave: homecare leave is unpaid credits; shadow leave consumes monthly credits. **Finance** leave deduction on invoices is a separate calendar-day formula. Same word “leave”, two maths.
- **CRM** thinks a package “has sessions left” from `care_packages`. **Finance** rollover UI may read `client_package_cycles` that were never updated on consume.
- **CRM** stores `zoho_id` on the case. **Finance** Zoho Books push is a best-effort, usually no-op. The ID is not proof the invoice exists in Zoho.

### 9. The 10 most dangerous things (ranked)

1. **Silent dual money engines** — therapist `invoices` vs client `client_invoices` / ledger; flags decide which writes. Wrong flag combo = preview that never posts, or posts that dashboards ignore. **J / Critical**
2. **Package remaining can disagree with itself** — `used_sessions` vs unused cycle `record_consumption`. **B / J / High**
3. **Suspended/replacement cases can still run sessions** while bookings were cancelled. **A / High**
4. **Inactive therapist remains ACTIVE assignee** — login blocked, assignment not ended. **A / I / High**
5. **Session start writes IN_PROGRESS before case-status assert** — failed start can leave an in-progress row. **K / High**
6. **Dead financial-effect resolver vs live step-6 helper** — if someone later “wires the unused function”, COMPLETED sessions would be treated as cancelled. **C / M / Critical if wired**
7. **Four report/document systems** — legacy monthly, clinical engine, IEP v1, case documents. Parent/CM can look at the wrong one. **B / E / High**
8. **`hr.update_therapist` gated by `therapist.read`** — weaker than user.manage. **I / High**
9. **Incident SLA only on list** — no cron; missed list = missed escalation. **H / K / Medium–High**
10. **Frontend invoice exclude math** — local re-sum before server submit; calendar-day cases keep server share. Easy to believe a number that is not stored yet. **F / J / High**

### 10. What should NOT be changed yet?

Do **not** delete or “simplify” without a founder decision + migration:

- `DEACTIVATED` rows and reopen path
- `PERCENTAGE` enum / `pay_share_amount_inr` columns
- `parent_billing_statements` until parent UI + seed are proven unused in prod
- Parallel report engines (parents may still have artifacts on the old one)
- Ledger vs invoice dual-write until cutover flags are a conscious production decision
- `case.therapist_id` (it **does not exist** — do not reintroduce it)
- Any financial formula “to make products the same”

See `10_FOUNDER_DECISIONS_REQUIRED.md` and `11_REMEDIATION_ROADMAP.md`.

---

## Can InsighteCase be trusted as the organisational source of truth?

**Not completely. Not yet.**

It **can** be trusted as:

- The operational record of **which child, which case, which assignment, which session clock, which log, which leave request**.
- The permissioned portal for therapists, parents, CMs, HR, and Finance to do daily work.

It **cannot** yet be trusted as:

- One book for **money in and money out**.
- One book for **who is allowed to hold a case**.
- One book for **which report is the official clinical document**.
- One CRM for **lead → client conversion**.

**What prevents trust:** stacked finance services behind flags; eligibility that is not an invariant; status machines that do not fully stop the next module; leftover tables and unused “source of truth” functions; almost no end-to-end tests that walk CRM → clinical → Finance → HR in one journey.

---

## How to read the rest of this audit

| File | Audience |
| --- | --- |
| [01_CURRENT_SYSTEM_MAP.md](./01_CURRENT_SYSTEM_MAP.md) | What exists (architecture + feature inventory) |
| [02_BUSINESS_LOGIC_REGISTRY.md](./02_BUSINESS_LOGIC_REGISTRY.md) | Rules in founder English + where they live |
| [03_CHANGE_TIMELINE_90_120_DAYS.md](./03_CHANGE_TIMELINE_90_120_DAYS.md) | How it got here |
| [04_CONFLICT_AND_LEGACY_REGISTER.md](./04_CONFLICT_AND_LEGACY_REGISTER.md) | Conflicts A–M |
| [05_CROSS_TEAM_CONTRACTS.md](./05_CROSS_TEAM_CONTRACTS.md) | Finance ↔ HR ↔ CRM handoffs |
| [06_PRODUCT_LOGIC_COMPARISON.md](./06_PRODUCT_LOGIC_COMPARISON.md) | Homecare vs shadow vs other |
| [07_DATA_INTEGRITY_AUDIT.md](./07_DATA_INTEGRITY_AUDIT.md) | Invariants and impossible states |
| [08_FINANCE_LOGIC_AUDIT.md](./08_FINANCE_LOGIC_AUDIT.md) | Money lineage |
| [09_TEST_AND_REGRESSION_MAP.md](./09_TEST_AND_REGRESSION_MAP.md) | What tests actually protect |
| [10_FOUNDER_DECISIONS_REQUIRED.md](./10_FOUNDER_DECISIONS_REQUIRED.md) | Policy questions engineering must not guess |
| [11_REMEDIATION_ROADMAP.md](./11_REMEDIATION_ROADMAP.md) | P0–P3, not implemented |
| [system_logic_map.json](./system_logic_map.json) | Machine-readable map for later agents |
