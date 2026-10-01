# Product-by-product logic comparison

## Products that actually exist

Clinical access is **not** only two hardcoded modules. Catalog lives in `service_categories` + `service_products`. Code still special-cases:

| ID | How it appears | Notes |
| --- | --- | --- |
| `homecare` | `FIXED_CLINICAL_IDS` | Default therapist onboard |
| `shadow_support` | `FIXED_CLINICAL_IDS`; alias `shadow` | School-shaped; day type |
| `b2b` | `DAY_TYPE_PRODUCT_MODULES` | Day type + calendar-day pay with shadow |
| school_support, special_education, behavior_therapy, play_therapy, counselling | `clinical_service_resolver` / session caps | Duration caps exist; allotment defaults do not pre-select them |

Org capabilities (`billing`, `people_admin`, `hr_ops`, `service_catalog_admin`) are **not** case products.

Do **not** force products to behave identically. Classify: **INTENTIONAL DIFFERENCE** vs **LIKELY LOGIC DRIFT**.

---

## Comparison matrix

| Topic | Homecare | Shadow support | B2B | Other catalog (e.g. counselling) | Class |
| --- | --- | --- | --- | --- | --- |
| Case lifecycle | Same `CaseStatus` machine | Same | Same | Same | Shared |
| Allotment | No day type | **Half/Full required** | **Half/Full required** | No day type rule found | INTENTIONAL (shadow/B2B) |
| Default location | Home | School | Depends | Resolver-based | INTENTIONAL |
| Assignment eligibility | Picker filter only | Same | Same | Same | Shared drift (API bypass) |
| Session start | Same start rules | Same | Same | Same | Shared; suspend gap shared |
| Auto-end cap | 3h / 45 min after schedule | 10h / 2h | Uses resolver (often school-like if mapped) | counselling 2h/30m; behaviour/play 3h/60m; special ed 4h/60m; unknown 4h/60m | INTENTIONAL caps |
| Attendance / absence | Standard absence + package consume | Extra ledger path on child-absent (`session_absence_service._apply_billing`) | Follows case product | Standard unless mapped to shadow | **LIKELY DRIFT** (extra shadow path) |
| Billing model | PER_SESSION / PACKAGE / MONTHLY_FIXED on the **case**, not the product alone | Same enums; often calendar-day pay | Calendar-day pay with shadow | Case-level | Mixed: enum shared, **pay unit differs** |
| Therapist payout | Per completed/included session from lump ÷ package or per-session lump | **Calendar-day**: share/30 × days − unpaid leave | Same calendar-day helper | Per-session path unless flagged calendar-day | INTENTIONAL **if** founder wants shadow as daily retainers |
| Reports | Legacy monthly + clinical engine (flag) | Same engines | Same | Same | Shared dual-stack |
| Cancellation | Product rule flags on `product_billing_rules` | Same table; extra consume path | Same | Same | Drift on consume |
| Replacement | Same transition entity | Same; day type matters for handover pay (500/350 hardcoded full/half) | Same | Same | INTENTIONAL amounts? **BUSINESS INTENT UNKNOWN** |
| Package | `care_packages` + case `package_*` | Cycle preview marks shadow/retainer `needsReview` (no auto-credit) | Similar review | Standard package delta | INTENTIONAL caution on shadow rollover |
| Role | School coordinator **not** default | School coordinator defaults to shadow | — | — | INTENTIONAL |
| Incidents | Allowed | Allowed | Via case | Via case | Shared |
| Leave credits | Homecare-only leave **always unpaid** | Shadow leave can use monthly credits | Not in leave helper as “shadow” unless service line set | Depends on `service_line` / `includes_shadow_cases` | INTENTIONAL **if** policy holds |
| Homecare share &lt; 20% client → review | Yes (`billing_validation`) | Not that rule | — | — | **LIKELY DRIFT** or undocumented |
| Closure | Same close service | Same | Same | Same | Shared |

---

## “New engine vs old engine” by product

| Engine | Homecare | Shadow | Others |
| --- | --- | --- | --- |
| Session start / pending-log / day-end | Shared new (Jun–Aug) | Shared | Shared |
| Therapist invoice `invoice_billing_service` | Live | Live + calendar-day branch | Live |
| Client ledger | Same flag for all products | Same | Same |
| Clinical reports | Same flag | Same | Same |
| Step 6 windows/add-ons | Shared | Shared | Shared |

**No product is fully on a “new session engine” while another is on a 2025 engine.** The repo is too young. Drift is **branches inside shared services**, not two apps.

---

## Founder read

If homecare is “pay per visit” and shadow is “pay per school day,” the calendar-day and day-type rules are **not bugs**.

If the founder believes **every product should consume packages and pay therapists the same way**, then shadow extra paths and calendar-day pay are **logic drift** and must be unified after a decision — not silently.

Hardcoded handover amounts (₹500 full / ₹350 half in transition service) are **BUSINESS INTENT UNKNOWN** — treat as a policy question, not a rounding accident.
