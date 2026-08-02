# Cursor Handover — Finance Control Tower Stage 1 Gate 1 Acceptance

**Gate 1 verdict:** `STAGE_1_LOCALLY_VALIDATED_PENDING_LIVE_STAGING`

**Merge stamp:** `HUMAN_FINANCE_UAT_REQUIRED_BEFORE_MERGE`

**Environment note:** No live staging URL or credentials were used. This run is **staging-equivalent local/CI validation only**. Railway/Vercel environments were not discovered, created, or modified.

Do **not** treat this document as `STAGE_1_APPROVED_FOR_MERGE_BEHIND_FLAG`. That verdict requires Gate 2 (live staging) + Gate 3 (human finance UAT).

---

## 1. Stack / branch report

| Item | Value |
|------|--------|
| Branch | `feat/finance-dashboard-stage1` |
| Head SHA (pre-validation commits) | `1aa383235c0c8b12d7c90d4be4068f83bf9fe157` |
| Stage 1 PR | [#14](https://github.com/Insightee/case-manager-new/pull/14) OPEN draft |
| Stage 1 base | `feat/billing-engine-steps-1-6` |
| Engine PR | [#13](https://github.com/Insightee/case-manager-new/pull/13) OPEN → `main` (`mergedAt: null`) |
| Engine head included | `cdacb6dff31fc3967a99b808e0ea7174e3f870ab` |
| Dashboard-only commits beyond engine | 2 (`8170d29a`, `1aa38323`) + Gate 1 validation commit(s) |

**Rebase decision:** Engine PR has **not** merged → keep PR #14 based on `feat/billing-engine-steps-1-6`. Do not merge #14. Do not retarget to `main` yet.

**Diff purity:** `git log origin/feat/billing-engine-steps-1-6..HEAD` shows only Stage 1 dashboard commits (plus this Gate 1 validation follow-up).

---

## 2. Staging-equivalent flags (local/CI)

```text
ENABLE_BILLING=true                 # required to mount control-tower router
BILLING_LEDGER_WRITES=false         # independently blocks automatic ledger writes
FINANCE_CUTOVER_COMPLETE=false      # provisional banner; never RECONCILED
VITE_ENABLE_FINANCE_DASHBOARD_V1=true   # local/dev only; canonical prod force-off unchanged
```

Production defaults remain unchanged (not touched).

### `ENABLE_BILLING` requirement

Proven: with `enable_billing=false`, Control Tower GETs return **404**. With `true`, return **200** for authorised roles.  
Source: `require_billing` dependency on router mount in `backend/app/api/v1/router.py`.

### `BILLING_LEDGER_WRITES=false` write-path proof

With `app_env=staging` (disables test-env write bypass) + `billing_ledger_writes=false`:

| Writer | Result |
|--------|--------|
| `sync_session_status` | returns `None`; no ledger row |
| `upsert_from_session_event` | returns `None` |
| `upsert_from_daily_log_approved` | returns `None` (when a daily log exists) |
| `ensure_period_charges` | `{"skipped": true, "reason": "BILLING_LEDGER_WRITES_disabled"}` |
| `consume_package_session` | returns `None` |

Simultaneously, Control Tower `GET …/summary` still returns **200**.

Not enabled: invoice generation, payout approval, Zoho, RazorpayX, gateway payments, automatic reconciliation, production cutover.

---

## 3. Zero-write before/after evidence

Full exercise (summary + 3 list GETs × multiple months + all 10 queue drills + multi-role logins) left financial tables unchanged.

Tables snapshotted (row counts + id digests + ledger content fingerprint):

| Table | Before → After |
|-------|----------------|
| `billing_ledger` | 0 → 0 |
| `client_invoices` | 2 → 2 (sum 12800.00 unchanged) |
| `client_payments` | 1 → 1 (sum 8000.00 unchanged) |
| `invoices` (therapist) | 1 → 1 (sum 42500.00 unchanged) |
| `invoice_case_lines` | 0 → 0 |
| `invoice_session_lines` | 0 → 0 |
| `invoice_manual_lines` | 0 → 0 |
| `payouts` | 0 → 0 |
| `billing_disputes` | 0 → 0 |
| `case_client_rate_periods` | 0 → 0 |
| `billing_calc_exceptions` | 0 → 0 |
| `billing_period_flags` | 0 → 0 |
| `monthly_case_review` | schema marker `-1` (table not present in local SQLite test DB after seed path) → unchanged |

**Result:** `0 inserted / 0 updated / 0 deleted` on all present money tables. Checksums identical (`delta: none`). Artifact: `/tmp/cursor/artifacts/finance-control-tower-gate1/zero_write_snapshot.json`.

---

## 4. API confidence matrix

| Endpoint | Supplies | Source tables (read) | Confidence (demo 2026-07) | Missing values | Drill |
|----------|----------|----------------------|---------------------------|----------------|-------|
| `GET …/summary` | Header, action queue, finance MoneyValues, readiness funnel, links | `billing_ledger`, `client_invoices`, `client_payments`, `invoices`, `billing_calc_exceptions`, `billing_period_flags`, `billing_disputes`, `cases`, composer read lists | `pageConfidence=INCOMPLETE`; queues mix PARTIAL/ESTIMATED/INCOMPLETE; `provisionalBanner=true` | Omits `value` when no records; count-only cards | `links.*` + `drillQueue` |
| `GET …/exceptions` | Exception preview rows | calc exceptions, period flags, disputes (+ missing package case scan) | list `confidence=PARTIAL` | `financialImpact` often null; owner always `Unassigned` | `openHref` / queue filter |
| `GET …/billing-readiness` | Per-case readiness | `cases`, ledger, calc exceptions, client invoices | list `PARTIAL`; per-row INCOMPLETE when no ledger / missing package | `expectedAmount` without `value` when no ledger | `/admin/cases/{id}` |
| `GET …/payout-readiness` | Therapist payout readiness | `invoices` (+ case_lines when loaded) | list `ESTIMATED` | empty items when no therapist invoices for month | `/admin/therapist-payouts…` |

**Rules confirmed**

- Frontend `downgradeConfidence` / `lowestConfidence` never upgrade; missing → ESTIMATED or INCOMPLETE (`financeConfidence.test.js`).
- Pre-cutover: `money_value(RECONCILED)` → `PARTIAL`; payloads contain no `RECONCILED`.
- Mixed totals use lowest constituent confidence; incomplete amounts not silently summed (`aggregateMoneyValues`).
- `asOf` present on responses.

---

## 5. Record-level traceability (demo fixtures only)

No production-like financial rows were fabricated.

| Category | Demo status |
|----------|-------------|
| PER_SESSION active cases | PRESENT (1) |
| PACKAGE active cases | PRESENT (1) |
| MONTHLY_FIXED active cases | `FIXTURE_ABSENT` |
| Leave / assignment / add-on exception codes | `FIXTURE_ABSENT` (0 calc exception rows) |
| Period flags / open disputes | `FIXTURE_ABSENT` |
| Uninvoiced eligible (composer queue) | PRESENT (count=2 on summary) |
| Ledger rows for 2026-07 | 0 (billing readiness shows 2 cases, ledgerStatus NONE, confidence INCOMPLETE) |

Billing readiness traces (2 cases): each mapped once; `expectedAmount` has no invented ₹ when ledger empty; confidence INCOMPLETE — consistent with no persisted ledger.

Exception codes explicitly checked and marked `FIXTURE_ABSENT`: `MISSING_PACKAGE_COUNT`, `ASSIGNMENT_GAP`, `ASSIGNMENT_OVERLAP`, `MISSING_LEAVE_CREDIT_BALANCE`, `UNKNOWN_LEAVE_TYPE`, `MISSING_ADD_ON_RATE`.

---

## 6. RBAC results

Direct API access (menu hide is not the only protection):

| User | Role | Summary / all tower GETs |
|------|------|--------------------------|
| `superadmin@demo.com` | SUPER_ADMIN | 200 (Founder/COO mapped here — no separate role) |
| `finance@demo.com` | FINANCE | 200 |
| `casemanager@demo.com` | CASE_MANAGER | 403 |
| `admin@demo.com` | MODULE_ADMIN | 403 |
| `support@demo.com` | MODULE_ADMIN (CRM-adjacent) | 403 |
| `hr@demo.com` | HR | 403 |
| `therapist@demo.com` | THERAPIST | 403 |
| `parent@demo.com` | PARENT | 403 |
| `viewonly@demo.com` | CASE_MANAGER view-only | 403 |

Payout readiness (`…/payout-readiness`) denied for therapist, parent, HR, support (403). No dedicated CRM role in seed — `support@demo.com` used as CRM-adjacent denial.

---

## 7. Provisional agent walkthrough (`finance@demo.com`)

**Not human UAT.** Stamp: `HUMAN_FINANCE_UAT_REQUIRED_BEFORE_MERGE`.

| # | Task | Supported | Notes / route |
|---|------|-----------|---------------|
| 1 | Ready for billing | yes | count=0; `…&queue=ready_for_billing` |
| 2 | Missing package counts | yes | count=0; `…&queue=missing_package_counts` |
| 3 | Assignment gaps/overlaps | yes | count=0; `…&queue=assignment_issues` |
| 4 | Largest reliable impact | yes | no PARTIAL+ impact amounts in demo (ledger empty); count-only UX |
| 5 | Explain confidence | yes | observed PARTIAL / ESTIMATED / INCOMPLETE |
| 6 | Drill to records | yes | exceptions endpoint 200; 0 items in demo |
| 7 | Return keeping month | yes | `month=` retained when clearing `queue` (UI contract) |
| 8 | Provisional figures | yes | banner + `cutoverComplete=false` |
| 9 | Payout holds | yes | `payoutExceptions` card |
| 10 | Partial section failure | yes | `Promise.allSettled` + section errors (unit-tested) |

Friction (agent): demo data is sparse (empty ledger / exceptions), so finance users will see many zeros until offline `ensure_period_charges` was run elsewhere — Stage 1 correctly does not trigger writes. Terminology relies on ConfidenceBadge tooltips.

Interactive browser screenshots: deferred (frontend not launched in this Gate 1 run). Route references above are the evidence path.

### Human UAT script (blank results)

See [docs/finance_control_tower_stage1_human_uat_script.md](./finance_control_tower_stage1_human_uat_script.md).

---

## 8. Accessibility / responsive (static + deferred)

| Check | Result |
|-------|--------|
| ConfidenceBadge text + `title` + `aria-label` | Present (not colour-only) |
| Forest Light scoped CSS + mono for IDs/money | Present on Control Tower root |
| Table horizontal overflow styles | Present in `finance-control-tower.css` |
| Interactive keyboard / focus / tablet | **Deferred to Gate 2/3** (UI not launched) |

---

## 9. Tests and results

| Suite | Result |
|-------|--------|
| Finance Engine release-gate set (5 files) | **43 passed** |
| Stage 1 backend `test_finance_control_tower_stage1.py` | **15 passed** |
| Gate 1 backend `test_finance_control_tower_gate1_validation.py` | **16 passed** |
| Stage 1 frontend confidence + static contracts | **14 passed** |

Confirmed: engine calc suite unchanged green; Control Tower module is GET-only (service source scan + UI `apiFetch` GET paths); no Stage 1 clarity code fixes required during this validation run (tests/docs only).

---

## 10. Changes made during Gate 1 validation

- Added `backend/app/tests/test_finance_control_tower_gate1_validation.py` (expanded zero-write, write-path matrix, RBAC, fixture inventory, walkthrough supportability, confidence audit artifacts).
- Added this acceptance doc + human UAT script.
- No product behaviour changes; no flag changes on remote environments.

---

## 11. Known limitations

- Demo DB lacks ledger/exception/MONTHLY_FIXED density → many KPIs are zero / INCOMPLETE (`FIXTURE_ABSENT` not fail).
- `monthly_case_review` table absent in local SQLite test DB snapshot path (`n=-1` marker).
- Therapist payable remains ESTIMATED (log-gated path).
- No exception ownership/resolve UI (by design).
- Live staging + human UAT still required before merge-behind-flag.

---

## 12. Gate 2 — Live staging checklist (pending)

After PR #13 merges:

1. Rebase `feat/finance-dashboard-stage1` onto `main`; retarget PR #14 to `main`; confirm dashboard-only diff.
2. Document staging API + UI URLs in repo docs.
3. Set staging-only: `ENABLE_BILLING=true`, `BILLING_LEDGER_WRITES=false`, `FINANCE_CUTOVER_COMPLETE=false`, `VITE_ENABLE_FINANCE_DASHBOARD_V1=true`.
4. Zero-write smoke on staging DB for the financial tables list.
5. RBAC smoke (finance allow; therapist/parent/CM deny including direct API).
6. Finance user load overview, month change, drill-downs.

**Gate 2 outcome target:** `STAGE_1_LIVE_STAGING_TECHNICALLY_APPROVED`

---

## 13. Gate 3 — Human finance UAT (pending)

Real finance user completes the 10 tasks unguided using the timed script.  
**Gate 3 outcome target:** `STAGE_1_APPROVED_FOR_MERGE_BEHIND_FLAG`

---

## 14. Merge prerequisites

- [ ] PR #13 (Finance Engine) merged  
- [ ] PR #14 rebased onto `main` with dashboard-only diff  
- [ ] Gate 2 live staging complete  
- [ ] Gate 3 human finance UAT complete  
- [ ] Production flags remain off (`VITE_ENABLE_FINANCE_DASHBOARD_V1` forced off on canonical prod; no cutover)

**Do not merge from Gate 1 alone. Do not enable the dashboard in production. Do not perform financial cutover.**

---

## Final Gate 1 verdict

```text
STAGE_1_LOCALLY_VALIDATED_PENDING_LIVE_STAGING
```
