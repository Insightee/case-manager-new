# Founder decisions required

These are **policy** questions. Engineering must not pick a silent default. Each item exists because **two implementations already disagree** or because the code cannot tell what Insighte wants.

---

## DEC-01 — When does a package session get used?

**Decision:** Should remaining sessions drop when the visit is **completed**, when the **log is submitted**, when the log is **approved**, or when finance **posts the ledger**?

**Why this exists:** Consume runs on **log approve** (prepaid) and some absences. Complete does not consume. Cycle `record_consumption` is unused. Docs still talk about a future hook on COMPLETED.

**Current behaviour:** Parent remaining = `care_packages.used_sessions` after approve (and some absences). Clock-complete with no approve does not consume.

**Option A:** Consume on completed visit (ops-simple; risk: no-log still burns package).  
**Option B:** Consume on log **submit** (therapist-controlled).  
**Option C:** Consume on log **approve** (current for prepaid) — keep, and **delete or wire** cycles.  
**Option D:** Consume only when ledger is BILLABLE/INVOICED (finance-controlled; needs writes on).

**Recommendation:** Choose **C or D** explicitly; then make cycles follow the same event. Do not leave both tables.

**Systems:** packages, parent billing, readiness sheet, absences.

**Answer (locked 2026-09-08 — Founder + Finance + Case Ops):** Consume when a daily log has session times and status is `PENDING` (submitted) **or** `APPROVED`. Reverse on `REJECTED`. Cancelled sessions never consume; completed-with-no-log does not consume. SOT = `care_packages`; cycles non-authoritative until a later epic. Absence PACKAGE consume paths retained; therapist leave does not consume. Reverse blocked if session already on a generated/paid client invoice line.  
**Answered by:** Founder (chat lock for Core OS Stabilisation)  
**Answered:** 08-09-2026

---

## DEC-02 — Can a paused (Suspended) case still have a session?

**Decision:** After Suspend or Pending replacement, may a therapist start a visit?

**Why:** Bookings are cancelled; start assert allows those statuses; finance uses cutoff date.

**Current:** Sessions **can** start. Future booked slots **cannot**.

**Option A:** Hard block start (and end any IN_PROGRESS) on Suspend/Replacement — matches “service stopped.”  
**Option B:** Allow emergency visits; they are always extra/add-on and always reviewed by finance.  
**Option C:** Allow start only with admin override reason.

**Recommendation:** **A** unless field ops require emergency visits — then **C**.

**Systems:** session start, calendar, billing cutoff.

**Answer (locked 2026-09-08 — Founder + Case Ops + Finance):** `SUSPENDED` = no normal new session after `status_effective_date` (immediate if null). `PENDING_REPLACEMENT` = outgoing therapist cannot start normal sessions after cutoff. `CLOSED`/`DEACTIVATED` stay blocked. Already `IN_PROGRESS` may finish. Explicit admin override only; overridden sessions require Finance review. Client portal: `PENDING_REPLACEMENT` accessible; `SUSPENDED`/`CLOSED`/`DEACTIVATED` hidden; parents may request status restore.  
**Answered by:** Founder (chat lock for Core OS Stabilisation)  
**Answered:** 08-09-2026

---

## DEC-03 — What happens when a therapist exits?

**Decision:** Must HR archive/deactivate **automatically end assignments** and open replacement, or is that a manual CRM step?

**Why:** Allotment hides inactive people; assignment API and existing rows do not. Payout can still calculate.

**Current:** Ghost assignee; cannot log in; case still “theirs.”

**Option A:** Deactivate → end assignments same day + force PENDING_REPLACEMENT if cases remain.  
**Option B:** Deactivate → block **new** sessions only; keep history assignment until CM replaces.  
**Option C:** Manual only (current) — then HR UI must scream “still assigned.”

**Recommendation:** **A** for safety; **C** only if legal/HR needs a delay — then add a blocking queue, not silence.

**Systems:** HR, assignments, sessions, payouts, parent comms.

**Answer (locked 2026-09-08 — Founder + HR + Case Ops):** On therapist SUSPENDED / ARCHIVED / DELETED (and `is_active=false`): end ACTIVE assignments; surface cases for PENDING_REPLACEMENT attention; no new assignment until status restored; historical sessions/payouts intact. Login blocked; therapist may request HR to restore profile status (queue). Eligible therapists may be assigned other cases after restore. CM does not gain `case.assign`.  
**Answered by:** Founder (chat lock for Core OS Stabilisation)  
**Answered:** 08-09-2026

---

## DEC-04 — Which document is the official IEP / monthly report?

**Decision:** One engine for parents and CMs.

**Why:** Legacy `monthly_reports` / `observation_reports` / `iep_plans` plus `clinical_reports` plus `case_documents`.

**Current:** Both stacks can exist; clinical routes flagged; parents redirected off old builder (Aug 20) but old data remains.

**Option A:** Clinical engine only; freeze legacy as read-only archive.  
**Option B:** Legacy only; turn clinical off.  
**Option C:** Keep both for a dated cutover with a mapping table.

**Recommendation:** **C** then **A**. Do not delete legacy rows.

**Systems:** therapist reports, parent reports, meetings links.

---

## DEC-05 — Is shadow (and B2B) paid by the school day, not by the visit?

**Decision:** Confirm calendar-day payout and required Half/Full day type.

**Why:** Homecare is visit-shaped; shadow uses day type + share/30.

**Current:** Code treats them differently (INTENTIONAL in structure).

**Option A:** Yes — shadow is a daily retainer product. Document it.  
**Option B:** No — all products pay per completed session. Then calendar-day is **drift** to remove.  
**Option C:** Shadow school = calendar-day; shadow home = per session (if that product exists).

**Recommendation:** Founder/Finance must pick. Engineering already implemented **A-like** behaviour.

**Systems:** allotment, invoices, leave deduction.

---

## DEC-06 — Homecare leave vs shadow leave

**Decision:** Is it correct that **homecare-only leave never uses paid credits**, while shadow leave does?

**Why:** `leave_policy_service` hard-codes homecare unpaid. Finance deducts unpaid leave on **calendar-day** cases.

**Current:** Two maths, same word “leave.”

**Option A:** Keep (document in HR + Finance SOPs).  
**Option B:** One credit pot for all service lines.  
**Option C:** Credits follow the **cases held that day**, not the leave form’s service line.

**Recommendation:** Do not “simplify” in code until HR + Finance sign **A or B**.

**Systems:** leave, invoices, parent notifications.

---

## DEC-07 — When is ledger the only way to raise a client invoice?

**Decision:** Ban case-default invoices, or keep a manual composer?

**Why:** Doctrine = ledger SSOT. `admin_create_invoice` can skip ledger. Writes often off.

**Current:** Two create paths.

**Option A:** Ledger-only after cutover (`BILLING_LEDGER_WRITES=true`).  
**Option B:** Composer remains for exceptions, always tagged MANUAL, never mixed into “reconciled.”  
**Option C:** Stay flagged off — Excel remains the books. (Honest, not a system.)

**Recommendation:** **B** during cutover, **A** for normal months. Never call Control Tower reconciled under **C**.

**Systems:** composer, Control Tower, Zoho.

---

## DEC-08 — Is PERCENTAGE compensation ever coming back?

**Decision:** Kill the enum in a later migration, or keep for a true %-of-client product?

**Why:** Aug 28 coerce to FIXED_LUMP; enum remains.

**Current:** New writes coerced; old columns still there.

**Option A:** Never again — plan a removing migration after audit of leftover rows.  
**Option B:** Yes, for a named product — then implement properly, do not reuse the zombie.

**Recommendation:** **A** unless Finance has a live %-of-fee contract.

**Systems:** case billing form, resolvers, reports.

---

## DEC-09 — Do we need a CRM lead pipeline?

**Decision:** Case-only is the CRM, or build Lead → Converted?

**Why:** No Lead model. Zoho ID is a sticker. Conversion = allotment.

**Current:** Ops kanban is allotment/reassignment, not sales stages.

**Option A:** Case-only (current). Sales lives in Zoho/Sheets.  
**Option B:** Add Lead with an explicit convert that **creates** the case + commercial terms once.

**Recommendation:** **A** until sales volume demands **B**. Do not pretend `PENDING_ALLOTMENT` is “Qualified lead.”

**Systems:** people, allotment, Zoho.

---

## DEC-10 — Must unpaid packages or overdue invoices stop care?

**Decision:** Can therapists still run sessions if the package is exhausted or invoices overdue?

**Why:** Start rules do not check package/payment.

**Current:** Care continues.

**Option A:** Never auto-stop clinical work (connection before correction). Finance chases separately.  
**Option B:** Soft warn on start.  
**Option C:** Hard block after a grace date.

**Recommendation:** **A or B** fits the clinical doctrine. **C** needs a human override path.

**Systems:** session start, parent billing, Control Tower.

---

## DEC-11 — Acceptance gating

**Decision:** Must a parent accept the therapist before the first session?

**Why:** Columns exist; `ACCEPTANCE_GATING_ENABLED` default false.

**Current:** Informational only.

**Option A:** Keep off.  
**Option B:** Turn on for new allotments only.

**Recommendation:** Do not enable globally without a parent-app communication plan.

---

## DEC-12 — Handover pay ₹500 / ₹350

**Decision:** Are full-day / half-day transition pays fixed rupees or derived from the case lump?

**Why:** Hardcoded in `therapist_transition_service`.

**Option A:** Keep published rates (document).  
**Option B:** Prorate from case therapist pay.  
**Option C:** Always manual finance line.

**Recommendation:** Finance writes the number; engineering stops treating 500/350 as natural law.

---

## How to close a decision

1. Write the chosen option on this page (or in `docs/plans/finance-open-questions.md` for money).  
2. Name the person and date.  
3. Only then change **one** SOT in code.  
4. Add a golden-journey test from `09_TEST_AND_REGRESSION_MAP.md`.
