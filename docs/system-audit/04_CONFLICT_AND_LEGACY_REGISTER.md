# Conflict and legacy register

Classification from the audit brief (A–M). Severity: Critical / High / Medium / Low.

Every row is **CONFIRMED** in code unless marked **STRONG INFERENCE** or **POSSIBLE RISK**.

---

## A. Logic conflict — two rules give different answers

| ID | Issue | Evidence | Severity |
| --- | --- | --- | --- |
| A-01 | Allotment stays pending until `activate_allotment` **and** assign therapist promotes to Active. | CASE-002 vs CASE-003; commits `0ea239bb`, `60e06f2c` | High |
| A-02 | Close/suspend cancel future work; session start still allowed on Suspended / Pending replacement. | CASE-008 vs CASE-020; `assert_case_allows_new_session` | High |
| A-03 | Unused `resolve_session_financial_effect` vs live `package_unit_effect_for_status` (therapist leave payable or not). | FIN-014 vs FIN-015 | High (Critical if dead fn wired) |
| A-04 | HR leave credits (homecare always unpaid) vs finance calendar-day leave deduction. | HR-006 vs FIN-020 | High |
| A-05 | Therapist status-request approve can write `case.status` **without** admin transition/audit if not in admin map. | `approve_request` fallback | High |
| A-06 | `list_active_cases_for_therapist` hides Closed/Suspended only — not Deactivated or Pending replacement. | therapist portal queries | Medium |

---

## B. Source-of-truth conflict

| ID | Concept | Places | Severity |
| --- | --- | --- | --- |
| B-01 | Package remaining | `care_packages.used_sessions` vs `client_package_cycles.remaining_sessions` | Critical |
| B-02 | Official clinical document | `monthly_reports` / `observation_reports` vs `clinical_reports` vs `iep_plans` vs `case_documents` | High |
| B-03 | Therapist identity for a case | Assignments SSOT — comments still warn against `case.therapist_id` (column absent) | Low (good) |
| B-04 | Employee “active” | `is_active` vs `employment_status` vs `TherapistProfileStatus` | High |
| B-05 | Client money | Ledger vs `client_invoices` vs `parent_billing_statements` vs Zoho | Critical |
| B-06 | Therapist money | Live preview vs stored invoice snapshot vs payout batches vs old `payouts` | High |
| B-07 | Session duration | Clock vs edited times vs log duration vs slot hint | Medium (partly intentional) |
| B-08 | Attendance vocabulary | `AttendanceStatus` enum vs free string vs session absence statuses | Medium |

---

## C. Legacy logic still reachable

| ID | Remnant | Still does | Severity |
| --- | --- | --- | --- |
| C-01 | `CaseStatus.DEACTIVATED` | Reopen, billing cutoff, parent hide, filters | High |
| C-02 | `CompensationMode.PERCENTAGE` | Enum + columns; coerce on write | Medium |
| C-03 | `parent_billing_statements` | Seed + `parent_service` list | Medium |
| C-04 | `resolve_session_financial_effect` | Dead; dangerous if imported later | High |
| C-05 | Legacy reports router always mounted | Dual write with clinical engine | High |
| C-06 | `iep_plans` version `v1` | Parallel to clinical IEP | Medium |
| C-07 | `payouts` table | Beside batches/transfers | Medium |
| C-08 | `is_additional_visit` + `add_on_kind` | Both written; ledger never rewritten | Medium |
| C-09 | MeetingType Postgres-legacy values | Still in enum | Low |
| C-10 | Incident OPEN/INVESTIGATING/RESOLVED aliases | Normalized on read | Low |
| C-11 | Case document `SUPERVISOR_REVIEW` | Normalized to `CM_REVIEW` | Low |
| C-12 | `shadow` → `shadow_support` alias | Bootstrap rename | Low |
| C-13 | Acceptance gating columns | Enforcement off | Medium |
| C-14 | Old `payouts` + `ParentBillingStatus` | Reachable via models | Medium |

---

## D. Partial migration

| ID | New | Old still required | Severity |
| --- | --- | --- | --- |
| D-01 | Ledger-first client billing | Case-default invoice create; writes flag off | Critical |
| D-02 | Clinical reports engine | Legacy monthly/observation | High |
| D-03 | FIXED_LUMP coerce | PERCENTAGE enum / pay_share column | Medium |
| D-04 | Package cycles | Consume still only `used_sessions` | High |
| D-05 | Payout batches | Therapist `invoices` remain the claim SSOT; old `payouts` | High |
| D-06 | Service catalog SSOT | `users.module_assignments` fallback in eligibility | Medium |
| D-07 | As-of rate history | Live `cases.*` rates still used if no history row | Medium |

---

## E. Cross-module / product drift

| ID | Difference | Intentional? | Severity |
| --- | --- | --- | --- |
| E-01 | Shadow/B2B day type required | **INTENTIONAL** | — |
| E-02 | Auto-end caps 3h homecare vs 10h shadow | **INTENTIONAL** | — |
| E-03 | Homecare leave unpaid vs shadow credits | **INTENTIONAL** (HR-006) if founder agrees | Founder |
| E-04 | Calendar-day payout shadow/B2B vs per-session homecare | **INTENTIONAL** if founder agrees | Founder |
| E-05 | Extra shadow child-absent ledger path | **LIKELY DRIFT** | High |
| E-06 | Homecare share &lt; 20% of client triggers review; shadow not | **LIKELY DRIFT** or undocumented policy | Medium |
| E-07 | Assignment eligibility on picker only | **LIKELY DRIFT** | High |
| E-08 | School coordinator defaults to shadow only | **INTENTIONAL** | — |

---

## F. Frontend / backend drift

| ID | Topic | FE | BE | Severity |
| --- | --- | --- | --- | --- |
| F-01 | Session filter FLAGGED | Admin logs | Not a session status | Medium |
| F-02 | Jul 10 prod hide billing vs API flags | `VITE_*` / hotfix | `ENABLE_BILLING` | High |
| F-03 | Invoice exclude totals | `applyLocalExcludes` | Server on submit | High |
| F-04 | ARCHITECTURE.md parent billing | Docs/UI history | `client_invoices` | Medium (docs) |
| F-05 | Report status casing | Revamp lowercase | Legacy UPPER | Medium |
| F-06 | Calendar “under review” | Pending allotment only | Replacement/suspend exist | Low |
| F-07 | Typo route `/clinetlogin` | Works | Alias | Low |

---

## G. Data model drift

| ID | Schema vs rules | Severity |
| --- | --- | --- |
| G-01 | `operational_stage` free string, unused as enum | Low |
| G-02 | `attendance_status` String not enum | Medium |
| G-03 | Nullable `day_type`, `zoho_id`, `add_on_kind` compatibility | Medium |
| G-04 | Retainer is dates on MONTHLY_FIXED, not a billing_type | Medium (documented in model) |
| G-05 | Alembic multi-head merges as a monthly ritual | Medium (ops) |

---

## H. Automation conflict

| ID | Issue | Severity |
| --- | --- | --- |
| H-01 | Day-end “opportunistic hook” documented; **no request-path caller** — only cron | Medium |
| H-02 | Incident SLA only on list — missed list = no SLA | High |
| H-03 | Email retry cron vs request BackgroundTasks — two delivery paths | Low |
| H-04 | Old automations vs new finance flags — ledger upserts silently no-op | High |

---

## I. Permission risk

| ID | Issue | Severity |
| --- | --- | --- |
| I-01 | `hr.update_therapist` = `therapist.read` | High |
| I-02 | Assignment POST skips allotment eligibility | High |
| I-03 | Therapist PATCH employment without `is_active` | Medium |
| I-04 | CM can change case status via `case.update` | Medium (may be intended) |
| I-05 | Finance `case.read.all` — wide clinical read | Medium (likely intended) |
| I-06 | Hidden button ≠ auth — generally OK; rely on API | — |

---

## J. Financial integrity risk

| ID | Issue | Severity |
| --- | --- | --- |
| J-01 | Dual money rails + flags default off | Critical |
| J-02 | Package cycle not updated on consume | Critical |
| J-03 | Case-default invoices without ledger | High |
| J-04 | Dead resolver would mark COMPLETED non-billable | Critical if wired |
| J-05 | Frontend exclude math before persist | High |
| J-06 | Rate change vs historical invoices — mitigated by snapshots/as-of **if** used | Medium (improving) |
| J-07 | Payout vs client billing rules diverge (leave, absence, calendar-day) | High |
| J-08 | Mock payments / no live gateway — cannot over-collect via gateway; **can** mis-record manual confirms | Medium |
| J-09 | Low-margin gate is allotment-time, not every later rate edit | Medium |
| J-10 | `date.today()` vs IST on some billing/close helpers | Medium |

---

## K. Silent failure

| ID | Issue | Severity |
| --- | --- | --- |
| K-01 | Ledger writes disabled → upserts no-op | High |
| K-02 | Start session: IN_PROGRESS then assert case — leftover row | High |
| K-03 | Zoho Books no-op looks like “sync configured” if UI implies success | Medium |
| K-04 | Parent auto-suspend: no email | Medium |
| K-05 | Incident SLA if nobody opens the list | High |
| K-06 | Payment always mock even if “live” mentally assumed | High (ops) |

---

## L. Test gap

See `09_TEST_AND_REGRESSION_MAP.md`. Highest: no golden CRM→finance journey; no inactive-unassign test; no suspend-blocks-start test; no consume-vs-cycle test; dead resolver untested.

---

## M. Intent unclear — founder must decide

| ID | Question | Why code cannot decide |
| --- | --- | --- |
| M-01 | When does a package session get consumed? | Log approve vs complete vs ledger vs cycle |
| M-02 | May a suspended case still run a session? | Bookings cancel; start does not |
| M-03 | Must exit end assignments automatically? | HR and assignments disagree |
| M-04 | Which report is official? | Four stores |
| M-05 | Is calendar-day pay for all shadow or only some? | Code special-cases product |
| M-06 | Is PERCENTAGE ever valid again? | Enum kept after coerce |
| M-07 | When is ledger the only way to invoice? | Dual create paths |
| M-08 | Is there a CRM lead stage or is case-only enough? | No lead model |

Full options: `10_FOUNDER_DECISIONS_REQUIRED.md`.
