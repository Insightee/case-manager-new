# Cross-team contract matrix

Finance, HR, and CRM/Clinical must exchange **reliable facts**. Today they often share a table but **not a meaning**.

| Trigger | Producing domain | Data produced | Consuming domain | Expected state (business) | Actual implementation | Failure if wrong |
| --- | --- | --- | --- | --- | --- | --- |
| Lead becomes client | CRM | Billable client | Finance | Pricing locked, billing starts | **No lead entity.** Client exists when a Case is allotted (`allotment_service.allot_case`) with rates on `cases` | Finance cannot mark “conversion date” separately from case create |
| Agreed pricing entered | CRM / Admin | Client rate, package, therapist lump | Finance | Same numbers on invoice | `cases.*` + optional `product_billing_rules` + later `case_billing_rate_changes` | Later edits without as-of dates used to rewrite history; Aug 29 as-of **partially** fixes |
| CRM edits terms after invoices exist | CRM | New rates | Finance | History preserved | As-of + invoice snapshots **if** those paths are used. Case-default draft can still use live case | Silent price change on new drafts |
| Multiple packages/rates | CRM | Several products | Finance | One active commercial story per case | One `billing_type` per case; `care_packages` rows per case; `service_products` catalog | Two packages can exist; remaining math can disagree (B-01) |
| Case paused (Suspended) | CRM | Stop service | Finance + Clinical | No new billable work; no new visits | Bookings cancelled; **sessions can still start**; billing cutoff = `status_effective_date` | Visits after “pause”; money vs ops disagree |
| Replacement started | CRM / HR | Pending replacement | Clinical + Finance | Outgoing flagged; incoming billed from dates | `PENDING_REPLACEMENT` + `case_therapist_transitions` + payout flags | Dual pay or unpaid handover if dates wrong |
| Which status starts/stops billing? | CRM | `cases.status` + effective date | Finance | One cutoff rule | `get_case_billing_cutoff` for SUSPENDED / PENDING_REPLACEMENT / DEACTIVATED / CLOSED | PENDING_ALLOTMENT may already have slots (CASE-019) |
| Therapist eligible? | HR | Approved + active + services | CRM allotment | Cannot assign ineligible | **Picker only.** Assignment API skips check | Ineligible person holds case |
| Therapist inactive/resigned | HR | `is_active` / ARCHIVED | CRM / Finance | Assignments end; no future pay | Assignments stay ACTIVE; login blocked | Ghost assignee; payout still computable |
| Onboarding/training | HR | Eligible to work | CRM | No allocation before approved | Direct onboard = APPROVED immediately. No training state | Untrained staff can be allotted |
| Employee status → cases | HR | Employment change | Clinical | Cases reassigned | **No automatic effect** | Clients left on exited therapist |
| Therapist exits with active clients | HR | Exit | CRM | Replacement workflow | Manual `PENDING_REPLACEMENT` / transition | Easy to miss |
| Session completed | Clinical | Visit happened | Finance | Billable / payable per policy | End ≠ consume. Consume on **log approve** (prepaid) + some absences. Ledger often **no-op** | Package/ledger lag behind clock |
| Which sessions payable? | Clinical | Status + attendance | Finance (out) | Same list finance uses | `invoice_billing_service` + attendance facts + calendar-day exception | Therapist pay ≠ parent charge |
| Which sessions billable? | Clinical | Same | Finance (in) | Same list | Ledger/step6/product rules — **different helper than payout** | Margin lies |
| Cancellation: client vs therapist | Clinical | Cancel / absent / leave | Finance both sides | One policy table | Product rule flags + unused resolver + step6 | Parent charged, therapist unpaid (or reverse) |
| Missing log | Clinical | COMPLETED no log | Finance | Hold billing/payout | Pending-log **blocks next start**. Invoice may still see completed visits depending on preview rules | Ops stuck; money may still count clock |
| Session edited later | Clinical | `actual_times_edited` | Finance | Use edited duration; audit | Duration can follow log/edit; snapshots freeze at submit | Edit after submit ≠ old invoice unless reissued |
| Case closed | CRM | CLOSED | Finance | No new invoices; assignments ended | Close blocked by draft client invoices; assignments ended | Cannot close dirty finance; or orphan if invoices flag off |
| Payment / package empty | Finance | Unpaid / exhausted | Operations | Maybe stop service | **No confirmed hard block** of session start on unpaid package | Service continues while unpaid |
| Package remaining | Finance | Count left | CRM / Parent | One number | `used_sessions` vs unused cycles | Wrong renewal / parent complaint |
| Package expire / rollover | Finance | New cycle | CRM | Explicit carry-forward | `advance_cycle` unused in prod | Rollover never happens or happens twice in UI |
| Zoho | CRM stores ID | `cases.zoho_id` | Finance Books | Invoice in Zoho | Best-effort / no-op default | Ops thinks accounting is synced |

---

## CRM → Finance (narrative)

**When is someone a billable client?** When a **Case** exists with commercial fields — not when a lead is marked Converted. There is no CRM conversion event.

**Can CRM change terms after finance starts?** Yes, via case billing form. As-of history (29 Aug) is the intended protection. Dual invoice-create paths mean a new draft can still pick **live** case amounts.

**Pause:** CRM believes service stopped (slots cancelled). Finance believes cutoff date applies. Clinical can still clock a session. **Three interpretations of one button.**

---

## HR → CRM / Clinical

**Eligibility** is a search filter, not a database constraint.

**Exit** does not unassign. HR caseload can still show the person as on the case.

**Training** is not a gate.

---

## Clinical → Finance

**Payable ≠ billable.** Therapist invoice engine and client ledger/step6 are siblings, not one function.

**Child absent / therapist leave / cancel** have product-rule flags. The function that was supposed to centralise this (`resolve_session_financial_effect`) is unused. Live behaviour is easier to get wrong when adding a new product.

---

## Finance → Operations

**Payment status does not clearly stop care.** Package exhaust sets `care_packages.status` EXHAUSTED; session start does not check it (**STRONG INFERENCE** from start_session preconditions list — unpaid/exhaust not in the assert list).

**Authoritative remaining:** treat `care_packages` counters as what parents see. Do not use cycle remaining until consume is wired.

---

## Different interpretations of the same event (summary)

| Event | CRM meaning | Clinical meaning | HR meaning | Finance meaning |
| --- | --- | --- | --- | --- |
| Suspend | Pause family | Bookings die; session may live | — | Cutoff date |
| Close | End relationship | Assignments end; parent portal may die | — | Blocked by draft invoices |
| Leave approved | Parents told (selected) | Slots blocked/cancelled | Credits consumed (shadow) | Invoice deduction (calendar-day) |
| Log approved | Family may see notes | Visibility + mentor | — | Package −1 (prepaid); ledger maybe |
| Therapist deactivated | Still assigned | Cannot login | Employment label | Pay still calculable |
| Rate change | Form saved | — | — | As-of if history row exists |

These are the contradictions the founder must resolve as **policy**, then engineering can make one.
