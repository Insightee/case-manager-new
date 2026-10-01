# Change timeline — last 90–120 days

**Window:** 29 April–29 August 2026.  
**Repo birth:** 16 May 2026 (`773a6961`). There is no older product history in this git tree.  
**HEAD analysed:** `main` ~`87eafe9f` (520 commits).  
**Authors (approx.):** Divyam 291, midhunnoble 95, Cursor Agent 93, others.

| Month | Commits | Character |
| --- | --- | --- |
| May (from 16) | 54 | Bootstrap: models, RBAC, first billing pair, IEP v1, Railway firefighting |
| June | 151 | Session policy, leave rewrite, client status, parent portal |
| July | 79 | Tickets, CM scope, prod module hotfix, ops reports |
| August | 236 | Finance engine, IEP v2, transitions, as-of rates, MCP |

Hottest files: `CHANGELOG.md`, `admin.py`, `DailyLogsPage.jsx`, `client_billing_service.py`, `permissions.py`, `invoice_billing_service.py`.

---

## How to read this

**Current status** = what the code does **now**, not whether production flags are on.  
**INTENT UNCERTAIN** = commit message / code cannot prove founder policy.

---

## Timeline

| Period / commit | Area | Previous | New | Reason if visible | Downstream | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-05-16 `773a6961` | Infra | Nothing | Repo created | Greenfield | All history | Done |
| 2026-05-20 `887eb1bc` + `f79aa0fd` | All / Finance | Stub | Full app; `invoice_billing_service`; `client_billing_service`; CLIENT_ABSENT / THERAPIST_LEAVE | Bootstrap | Two money rails from week 1 | Both still live |
| 2026-05-25 | Clinical | No IEP | Observation + IEP builder v1 | Doctrine phase | Superseded Aug 19; old path remains | Legacy retained |
| 2026-05-26 | Auth | Flat roles | MODULE_ADMIN; permission catalog; service categories | Deploy | Catalog still growing | Evolving |
| 2026-05-27 `a6e51b37` | Finance | Invoice composer only | Ledger-first tables + `billing_ledger_service` | “Ledger SSOT” | Third money path | Writes still flagged |
| 2026-05-27–28 | Infra | SQLite-shaped | Postgres/Railway/Redis; enum/migration pain | Prod would not boot | Alembic multi-heads | Chronic |
| 2026-05-29 `0ea239bb` | Cases | Allot = active | Stay PENDING until `activate_allotment`; acceptance columns **off** | Pilot | Soft acceptance still off | In force + later CASE-003 |
| 2026-05-31 | Auth | SMTP | ZeptoMail + retry | Mail failing | Still patched in Aug | Fragile |
| 2026-06-04 | Auth | Shared login | Portal-specific login | Wrong-portal landings | | In force |
| 2026-06-05 | Finance | Constrained share | “Set share freely” | Ops | Then rupee share Jun 15 | Later coerced off % |
| 2026-06-09 | Parent / Sessions / Products | Parents saw closed; clock immutable; all services preselected | Hide closed; time correction; default homecare+shadow only | Privacy + field UX | Duration basis changed | In force |
| 2026-06-12 | Sessions | Informal absence | `session_absence` module | Attendance vs leave | Ledger | In force |
| 2026-06-15 | Finance | Share = % | Share can be **rupees** | Dual UX | PERCENTAGE vs lump mess | Partially reversed Aug 28 |
| 2026-06-16 `6740a8ac` | Cases | 4 statuses | + PENDING_REPLACEMENT, DEACTIVATED; audit | Replacement without close | Invoice slightly simplified | In force |
| 2026-06-17 | Cases / Parent | Closed still scheduled | Close clears schedules; hide from parents | Orphan sessions | | In force |
| 2026-06-20 | Auth / HR | CMs saw all; leave v0 | CM assigned-only; Leave Policy V1 rewrite | Scope leak; policy | Jul 25 B2B exception | In force |
| 2026-06-23–24 | Sessions | Opportunistic auto-close on GET; silent duplicates | 10 PM IST cron; 409 duplicate; `resolve_session_financial_effect` written | Overnight IN_PROGRESS | **Resolver never wired** | Cron in force; resolver dead |
| 2026-06-24 `d4975832` | Finance / Sessions | ₹500/day leave deduct | Assignment-rate leave; ledger event types | Policy correction | Aug still builds on this world | In force except unused resolver |
| 2026-07-01 | Parent / Leave | Leave reason shown | Hide reason, then “under review” messaging **same day** | Privacy vs clarity | | Under-review won |
| 2026-07-10 `4f73bbc7` | Products | Therapist saw unfinished billing/reports | **Hotfix:** gate those modules in production | Prod leak | Frontend gate | Split-brain vs Aug flags |
| 2026-07-10 `60e06f2c` | Cases | Assign left Pending | Assign → ACTIVE | Stuck pending | Conflicts with May 29 activate-only | **Both paths live** |
| 2026-07-10 | Cases / HR / FE | Therapists changed status; saw credits | Status button removed; credits hidden | Wrong actor | Frontend | In force |
| 2026-07-14 | Sessions | Broken scroll | Revert then real mobile fix | Hotfix | Time modal | Fixed |
| 2026-07-25 | Cases | B2B hidden from CM | B2B visible to CM | Carve-out | Scope rule split | In force |
| 2026-07-29 | Leave | No past July backfill | Past leave allowed | Month-end ops | Data-quality risk | In force |
| 2026-08-02 `ead0821a` | Finance | PER_SESSION/PACKAGE; small ledger | MONTHLY_FIXED; Step 6; `feature_flags.py`; +4.7k lines | Finance engine | Writes **off by default** | Staged |
| 2026-08-02 `dcdcb1dd` | Finance | Preview could post | 403 when ledger writes off | Staging preview | | In force |
| 2026-08-03 | Finance / Sessions | Therapists saw client prices; could start with pending log | Redact prices; pending-log gate | Leak + compliance | | In force |
| 2026-08-04–05 | Finance | Read-only tower | Client loop, packages cycles, writable corrections, payout settlement, KPI unified **twice in 24h** | Ground truth | KPI churn | Composed source current |
| 2026-08-11 | Finance | — | `invoice_ledger_service` (yet another bridge) | Demo | Parallel path | In tree |
| 2026-08-13 | Cases | Instant swap; no day type | HALF/FULL day; `case_therapist_transition` | Shadow + mid-month | Invoice grouping | In force |
| 2026-08-17 | Finance | Silent low margin | Approve if profit &lt; ₹5,000; reassignment payout flags | Margin + dual pay | | In force |
| 2026-08-18 | Clinical | Free-text only | Structured evidence **flag off** | Doctrine | | Off |
| 2026-08-19–20 | Clinical | Coming Soon + old IEP | Clinical engine **on in prod** (per commits); redirect off old builder | Soft then hard | Schema-repair same week | Dual stack remains |
| 2026-08-20 | CRM / Finance / HR | No zoho on case | Nullable `zoho_id`; TDS fix; mid-to-mid formula; mentors; finance sees leave/logs | Accounting + payroll | | In force |
| 2026-08-24 | Products | Unclear billing visibility | Module visibility refactor | Related to Jul 10 hotfix | | In force |
| 2026-08-26 | Integrations | No machine API | MCP + integration principals | External tools | Immediate CI fixes | Shipped |
| 2026-08-26–28 | HR / Reports | One HR row per case; ad hoc tickets | Split reassignment rows; four ticket statuses; Control Tower default on **non-prod** | Who owned the case when | KPI fix same day | Current |
| 2026-08-28 `51ea214e` | Finance | Leftover PERCENTAGE cases | Coerce → FIXED_LUMP; enum kept | Compatibility | Zombie enum | Coerced |
| 2026-08-29 | Finance / Sessions | Live breakdown; current rates | Stored snapshots; as-of rates; dual-therapist locks; duration outliers | Mid-month rates | **Current HEAD money contract** | Current |

---

## Rules that flipped several times

1. **Therapist compensation** — % → free % → rupee → monthly/fixed engine → coerce leftover % → as-of history.  
2. **Invoice breakdown SSOT** — live preview → attendance merge → stored snapshot → as-of overlay (27–29 Aug).  
3. **Leave deduction** — ₹500/day → assignment rate → extracted to `invoice_attendance_service`.  
4. **Finance KPI totals** — redefined twice in 24 hours (4–5 Aug).  
5. **Who sees which cases** — parents hide closed; CMs assigned-only then B2B exception; therapists lose status button.  
6. **Therapist billing/reports visibility** — Jul 10 frontend prod gate vs Aug backend flags.  
7. **Ticket statuses** — ad hoc → four canonical + legacy labels (28 Aug).  
8. **IEP** — v1 builder → Coming Soon → v2 engine on.  
9. **Session auto-close** — on GET (removed) → 10 PM cron.  
10. **Allotment activation** — stay pending until activate **and** assign-promotes-active.

---

## Hotfixes / reverts (CONFIRMED from git)

| Commit | What |
| --- | --- |
| Jul 10 prod module gate | Hide therapist reports+billing in production (frontend) |
| Jul 14 time-modal | Revert broken scroll, then real fix |
| Jul 6 leave email burst | Duplicate notify |
| Aug 4 `a27d6000` | Revert intentional CI-breaking downgrade after proving the gate |
| Aug 19 goal-repository schema repair | Drift after IEP engine |
| Aug 20 TDS | “fixed tds problem” — **INTENT UNCERTAIN** (message only) |
| Aug 28 Control Tower 120s timeout | Prod summary too slow |

May 20–28 contains throwaway commit messages around prod migrations. Treat that week as **deploy forensics**, not policy.

---

## Frontend-only vs backend-only (split-brain)

**Frontend-only behaviour:** portal login UX, hide therapist credits, remove therapist status button, parent content hide, Jul 10 prod module gate, much of Aug 29 cases-board polish.

**Backend-only:** PERCENTAGE coerce; most finance flags; MCP; day-end cron; zoho_id column; rate-history backfill.

**Risk:** Jul 10 UI can hide billing while `ENABLE_BILLING` still allows API posts, or the reverse, depending on env. **POSSIBLE RISK** until env is checked.

---

## Domain digest

| Domain | What happened |
| --- | --- |
| CRM | No lead module. Tickets routed then canonicalised. Meetings expanded. Zoho ID stored. |
| HR | Leave V1, credits hidden, mentors, soft-delete, split caseload rows. |
| Finance | Three stacked engines + flags. As-of rates HEAD. Payout release off. |
| Clinical | IEP v1 then v2. Structured evidence off. |
| Cases | Status machine, transitions, day type, allotment queue. |
| Sessions | Time correction, absence, auto-close, pending-log, duration outliers. |
| Reports | Publish workflow → ops Excel → clinical engine → admin overhaul. |
| Auth | Portal login, CM scope, new perms, integration JWT. |
| Integrations | Zepto, Zoho seam, MCP. |
| AI | **No LLM feature commits** in this window. |
| Infra | Railway/Vercel from week 1; Alembic heads monthly. |

---

## 10 largest architectural / business-logic changes (last ~3 months)

See founder diagnosis §7. Short list: Finance engine Aug 2; client billing loop Aug 4; writable payout loops Aug 4–5; clinical reports Aug 19; as-of rates Aug 29; session financial contract Jun 24; client status Jun 16; allotment gate May 29; transitions Aug 13–20; MCP Aug 26.

---

## What this means for the founder

The product did not “evolve slowly.” It **stacked new money and report systems on the old ones** and turned the new ones on with flags. The latest commit is **not automatically the intended business policy**. Several rules were reversed within days. Where the timeline says **INTENT UNCERTAIN**, do not let engineering pick a winner — use `10_FOUNDER_DECISIONS_REQUIRED.md`.
