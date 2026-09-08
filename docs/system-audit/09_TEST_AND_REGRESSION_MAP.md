# Test and regression map

Coverage **percentage is not the question**. The question is: does a **business rule** have a test that would fail if someone “fixed” it?

Backend: ~182 `test_*.py` files. Frontend: some `node --test` / unit files (`invoiceUtils.test.js`, `billingReadinessMasterSheet.test.js`). Playwright exists (`frontend/e2e/`) for portals — **not** a full finance journey.

`docs/TEST_GAP_BACKLOG.md` is **stale** (still lists leave-deduction preview as P1; leave deduction has since been extracted and unit-tested). Do not treat that backlog as current.

---

## Business rule × tests

| Rule ID | Criticality | Unit | API / integration | UI | E2E | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| CASE-004/005 status machine | High | Y `test_client_status.py` | Y | — | — | Strong isolated |
| CASE-003 assign→ACTIVE | High | partial | — | — | — | Weak vs activate-only |
| CASE-008 close ends assignments | High | Y `test_case_close.py` | Y | — | — | Strong |
| CASE-009 close vs invoices | High | Y | Y | — | — | Strong; flag-dependent |
| CASE-010 parent auto-suspend | High | Y | Y | — | — | Strong |
| CASE-020 suspend still allows start | **Critical ops** | **N** | **N** | — | — | **L — gap** |
| CASE-021/022 start today + pending log | High | Y | Y | FE mirrors | therapist e2e smoke? | Strong |
| CASE-031/HR-003 inactive stays assigned | **Critical ops** | **N** | **N** | — | — | **L — gap** |
| CASE-034 combined start | High | pieces | pieces | `sessionStartRules` | — | No single journey test |
| HR-002 is_active desync | High | **N** | **N** | — | — | **L** |
| HR-006 leave credits | High | Y `test_leave_policy.py` | Y | — | — | Strong HR side |
| HR-008 finance leave view | Medium | Y desk tests | Y | — | — | OK |
| HR-012 therapist.read update | High | **N** | **N** | — | — | **L** |
| FIN-002 flags | Critical | Y release gate | Y | runtime config | — | Strong for defaults |
| FIN-005 consume on approve | Critical | partial | — | — | — | Weak vs cycles |
| FIN-006 cycle unused | Critical | cycle unit only | **N prod path** | — | — | **L** |
| FIN-008/011 invoice snapshots | Critical | Y as-of + billing | Y | invoiceUtils | **N full UI** | Strong BE; weak E2E |
| FIN-014 dead resolver | Critical | **N** | **N** | — | — | **L** (also unused) |
| FIN-015 step6 effects | High | Y `test_billing_step6.py` | — | — | — | Strong for that helper only |
| FIN-016 payment confirm | High | Y loop tests | Y | — | — | OK isolated |
| FIN-020 leave vs pay | High | Y attendance | — | — | — | Not crossed with HR-006 |
| FIN-023 FE excludes | High | Y `invoiceUtils.test.js` | server apply | — | — | Partial |
| CLIN-002 dual reports | High | engine tests (flag on) | Y | — | — | Does not prove exclusivity |
| CLIN-003 parent visibility | High | Y | Y | parent e2e | parent-portal.spec | OK |
| AUTH-002/003 RBAC | High | Y `test_rbac_access.py` `test_phase0` | Y | — | — | Strong |
| AUTO-003 day-end | High | Y | script | — | — | Strong unit |
| AUTO-004 incident SLA | Medium | weak | list hook | — | — | **L** |

---

## What is well protected

- Auth / portal split / many permission denials  
- Client status **admin** transition map  
- Session start date, pending-log, void, day-end, absence **start block**  
- Leave policy math (HR)  
- Invoice preview pieces, as-of rates, period snapshots, settlement/TDS  
- Parent isolation and approved-only logs  

These are **unit/API** protections. They do not prove the **next team** saw the same event.

---

## Golden journeys that should always pass before deploy

These do **not** exist as one automated path today. They are the minimum **cross-functional** suite.

### G1 — Homecare happy path

Allot (rates + lump) → activate → schedule → start/end → log → approve log → package −1 **and** therapist invoice line **and** (if writes on) ledger → parent sees approved log → finance confirms payment.

**Protects:** FIN-005, FIN-008, CLIN-003, CASE-002.

### G2 — Shadow calendar-day + leave

Allot shadow FULL_DAY → month of days → unpaid leave → invoice deduction matches finance **and** HR credit rule (or documents the difference) → parent not over-notified.

**Protects:** FIN-010, FIN-020, HR-006, HR-007.

### G3 — Pause / replacement

Active case → Suspend → **assert no new start** (once policy chosen) → bookings gone → billing cutoff → Pending replacement → transition 3 dates → two therapist invoice segments → payout flags.

**Protects:** CASE-008/020, CASE-033, FIN-019.

### G4 — HR exit

Therapist ARCHIVED + `is_active=false` → **assignments ended or blocked** → cannot start → no future payout without override → CM sees replacement queue.

**Protects:** HR-002/003, CASE-031.

### G5 — Package change mid-flight

Change package size / rate with `applicable_from` → old sessions keep old as-of → remaining uses **one** counter → invoice + dashboard match.

**Protects:** FIN-006/007/012, J-02.

### G6 — Dual report trap

Create legacy monthly **and** clinical IEP on one case → parent/CM see **exactly one** official document (once decided).

**Protects:** CLIN-001/002, B-02.

### G7 — Flag matrix

`ENABLE_BILLING` off → 404. Writes off → no ledger/invoice post. Writes on → idempotent double-approve does not double-consume.

**Protects:** FIN-002, K-01.

---

## Frontend / E2E today

| File (examples) | What it is |
| --- | --- |
| `frontend/e2e/therapist-portal.spec.js` | Portal smoke |
| `frontend/e2e/parent-portal.spec.js` | Parent smoke |
| `frontend/e2e/report-editor-images.spec.js` | Editor |
| Admin workbench spec (backlog) | Smoke |

**Missing:** Playwright finance compose → pay; HR exit; suspend; package remaining.

---

## Minimum pre-deploy gate (recommended, not implemented here)

1. Existing targeted pytest for any file you touched (`./scripts/agent-pytest.sh`).  
2. Before **production money flag change**: G1 + G5 + G7.  
3. Before **HR/process change**: G4.  
4. Do **not** treat `pytest app/tests` as the definition of “safe” — it is wide and still misses G1–G7 as journeys.

---

## Stale test docs

- `docs/TEST_GAP_BACKLOG.md` — outdated P1s.  
- `docs/ARCHITECTURE.md` — parent billing statements.  
- Tests that force `ENABLE_CLINICAL_REPORTS_ENGINE=true` do not prove production if env is off (or the reverse).
