# Remediation roadmap

**Do not implement from this file yet.** Inspection-only audit. Each item waits on a founder decision where marked.

Effort: **S** hours–1 day · **M** 2–5 days · **L** 1–3 weeks · **XL** multi-week / migration programme.

---

## P0 — Protect immediately

### P0-1 Stop treating Control Tower / live previews as the books

- **Problem:** Flags default off; KPI definition churned; provisional banner exists but people still screenshot totals.  
- **Business consequence:** Wrong collections or payouts.  
- **Solution:** Written Finance SOP: only submitted invoice snapshots + confirmed payments. Env review of `ENABLE_BILLING`, `BILLING_LEDGER_WRITES`, payout flags.  
- **Systems:** Finance, Railway, Vercel.  
- **Migration:** No. **Data migration:** No.  
- **Regression:** Low. **Tests:** G7 flag matrix. **Effort:** S  
- **Decision:** DEC-07.

### P0-2 Do not wire `resolve_session_financial_effect` “to clean up”

- **Problem:** Dead function treats unknown/COMPLETED as cancelled.  
- **Business consequence:** Mass non-billable if someone “uses the unused helper.”  
- **Solution:** Comment/lock in review policy; add a test that **fails if it gains callers** without a founder sign-off. Do **not** delete until DEC-01/DEC-07.  
- **Systems:** `billing_ledger_service.py`.  
- **Migration:** No. **Effort:** S  
- **Regression:** Low if unused.

### P0-3 Inventory package vs cycle drift (read-only)

- **Problem:** Two remaining numbers.  
- **Business consequence:** Wrong renewals.  
- **Solution:** Staging/prod **counts only** of mismatched package ids. No auto-fix.  
- **Systems:** `care_packages`, `client_package_cycles`.  
- **Migration:** Later. **Effort:** S  
- **Decision:** DEC-01 before any write.

### P0-4 Privilege review: `hr.update_therapist` on `therapist.read`

- **Problem:** Weaker than `user.manage`.  
- **Business consequence:** Employment/status change by a wide role.  
- **Solution:** Confirm with HR whether intentional; if not, tighten permission (API contract change — **founder/HR sign-off**).  
- **Systems:** `hr.py`, RBAC.  
- **Migration:** No. **Effort:** S  
- **Tests:** new permission test. **Regression:** Medium (HR workflows).

---

## P1 — Stabilise the operating system

### P1-1 One rule for “may this session start?”

- **Problem:** Suspend/replacement vs close. Assert after IN_PROGRESS.  
- **Consequence:** Visits after “pause”; leftover IN_PROGRESS.  
- **Solution:** After DEC-02, move case assert **before** status flip; include decided statuses.  
- **Systems:** `session_service.start_session`.  
- **Migration:** No. **Effort:** M  
- **Tests:** CASE-020 + leftover-row test. **Regression:** High (field ops).

### P1-2 Assignment eligibility as an invariant

- **Problem:** Picker ≠ API; exit ≠ unassign.  
- **Consequence:** Ghost therapists.  
- **Solution:** After DEC-03: check `is_active` + approved + services on `create_assignment`; optional job/admin action to end assignments on deactivate.  
- **Systems:** assignment, HR, allotment.  
- **Migration:** Maybe backfill ENDED. **Effort:** M–L  
- **Tests:** G4. **Regression:** High.

### P1-3 Single package remaining SOT

- **Problem:** Cycles unused on consume.  
- **Solution:** After DEC-01: either call `record_consumption` from `consume_package_session` **or** stop reading cycles in readiness/rollover.  
- **Systems:** ledger consume, cycle service, readiness sheet.  
- **Data migration:** Yes if cycles backfilled. **Effort:** M  
- **Tests:** G5. **Regression:** High (parent remaining).

### P1-4 Allotment activate vs assign→ACTIVE

- **Problem:** Two promotion paths.  
- **Solution:** After product decision: one function `promote_pending_to_active` used by both; document who may call it.  
- **Systems:** allotment, assignments.  
- **Effort:** S–M. **Tests:** CASE-002/003. **Regression:** Medium.

### P1-5 Status-request approve must use `change_client_status` only

- **Problem:** Fallback raw write.  
- **Solution:** Remove fallback; reject illegal transitions with a human note (doctrine).  
- **Systems:** case status request.  
- **Effort:** S. **Tests:** existing + fallback case. **Regression:** Medium.

### P1-6 Name the official report

- **Problem:** Dual engines.  
- **Solution:** After DEC-04: feature-flag matrix documented in prod; parent/CM see one list.  
- **Systems:** reports, clinical_reports, parent.  
- **Data migration:** Mapping, not delete. **Effort:** L. **Regression:** High.

---

## P2 — Consolidate architecture

### P2-1 Finance engine cutover (not a rewrite)

- **Problem:** Ledger + composer + invoice engine + Control Tower.  
- **Solution:** After DEC-07: one write path for normal invoices; MANUAL tagged; `finance_cutover_complete` only when G1+G7 green in prod.  
- **Systems:** all finance.  
- **Migration:** Yes. **Effort:** XL. **Regression:** Critical.

### P2-2 Retire leftover money tables from **reads**

- **Problem:** `parent_billing_statements`, old `payouts`.  
- **Solution:** Stop seeding/listing; keep tables until counts are zero.  
- **Effort:** M. **Do not drop columns yet.**

### P2-3 PERCENTAGE removal

- After DEC-08 and row audit. **Effort:** M. **Migration:** Yes.

### P2-4 Module gate SSOT

- **Problem:** `modules.py` vs `feature_flags.py` vs `VITE_*`.  
- **Solution:** One runtime-config API (partially exists for billing) for all money/report flags.  
- **Effort:** M. **Regression:** Medium (Jul 10 hotfix class bugs).

### P2-5 Product policy table

- **Problem:** Shadow extra paths buried in services.  
- **Solution:** After DEC-05/06: one `product_billing_rules` / session-rules row per product; delete duplicate ifs.  
- **Effort:** L. **Regression:** High.

---

## P3 — Maintainability

| Item | Effort | Notes |
| --- | --- | --- |
| Golden journeys G1–G7 | L | See test map |
| Replace `date.today()` with `today_ist()` on money/close | S | Time integrity |
| Incident SLA cron or explicit “SLA stale” banner | S | H-02 |
| Update `ARCHITECTURE.md` / TEST_GAP_BACKLOG | S | Docs currently lie |
| Lock `admin.py` growth (already huge) — no new logic in route file | ongoing | Surgical rule |
| Alembic single-head discipline | ongoing | Already in contributing docs |
| Canvas / this audit refresh after each finance PR | S | `system_logic_map.json` |

---

## What not to touch yet

- Deleting `DEACTIVATED`, `PERCENTAGE`, legacy reports, or ledger tables  
- “Making homecare and shadow the same”  
- Reintroducing `case.therapist_id`  
- Turning payout release on without G2+G4  
- Production data cleanup without counts + backup  
- Wiring the dead financial-effect function  

---

## Suggested sequence (after decisions)

1. DEC-02, DEC-03, DEC-01 (ops + money safety).  
2. P0 SOP + env + package counts.  
3. P1-1, P1-2, P1-3, P1-5.  
4. DEC-04, DEC-07 then P1-6 / P2-1.  
5. P3 tests so the next 90 days cannot silently restack a fourth billing engine.
