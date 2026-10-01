# Documentation Gaps

Items that **cannot be fully answered from the repository alone** or are only partially documented in this handover package. Incoming team should close each gap with the listed source/owner.

---

## 1. Staging / testing environment topology

| | |
|--|--|
| **Missing** | Canonical staging API URL, Vercel preview project, which feature flags are enabled, whether staging uses prod-like R2 or local storage |
| **Why it matters** | Safe testing before production deploy and finance cutover |
| **Source** | Railway/Vercel dashboards, finance staging acceptance docs |
| **Verify with** | DevOps / finance lead |

---

## 2. Production database backup and restore

| | |
|--|--|
| **Missing** | RPO/RTO, backup frequency, restore drill procedure |
| **Why it matters** | Migration failure or data incident recovery |
| **Source** | Railway Postgres settings, company BCP |
| **Verify with** | Infrastructure owner |

---

## 3. Auto-deploy wiring

| | |
|--|--|
| **Missing** | Explicit confirmation that merge to `main` triggers both Railway and Vercel without manual promote |
| **Why it matters** | Release process and rollback expectations |
| **Source** | GitHub → Railway/Vercel integration settings |
| **Verify with** | Team lead |

---

## 4. JWT and integration secret rotation runbook

| | |
|--|--|
| **Missing** | Step-by-step rotation without logging out all users / breaking integrations |
| **Why it matters** | Security incident response |
| **Source** | Team security practice |
| **Verify with** | Backend owner |

---

## 5. Geocoding external provider

| | |
|--|--|
| **Missing** | Which API `geocode.py` calls, billing, API key env var name if any |
| **Why it matters** | Address features break if key expires |
| **Source** | Read `backend/app/api/v1/geocode.py` + team |
| **Verify with** | Backend owner |

---

## 6. Google Calendar OAuth

| | |
|--|--|
| **Missing** | OAuth client IDs, redirect URLs, token refresh ops |
| **Why it matters** | CM meeting calendar sync |
| **Source** | Google Cloud console, `UserCalendarConnection` usage |
| **Verify with** | Product/engineering |

---

## 7. Zoho Books and Razorpay production credentials

| | |
|--|--|
| **Missing** | Whether live keys exist, who owns accounts, go-live criteria |
| **Why it matters** | Finance cutover Loop E |
| **Source** | Finance + [FINANCE_CUTOVER_RUNBOOK.md](../FINANCE_CUTOVER_RUNBOOK.md) |
| **Verify with** | Finance director |

---

## 8. SCHOOL_COORDINATOR role product definition

| | |
|--|--|
| **Missing** | Portal entry, permissions, pilot status |
| **Why it matters** | RBAC completeness |
| **Source** | Product owner, seed data |
| **Verify with** | Product |

---

## 9. `review_queue` implementation status

| | |
|--|--|
| **Missing** | Which `.cursorrules` exception triggers are implemented vs planned |
| **Why it matters** | Case manager operating model |
| **Source** | Code search + product |
| **Verify with** | Clinical ops lead |

---

## 10. Bitrix24 / Zoho Sign / WhatsApp roadmap

| | |
|--|--|
| **Missing** | Commitment and timeline (README lists phased) |
| **Why it matters** | Integration planning |
| **Source** | [PRODUCT_ROADMAP.md](../PRODUCT_ROADMAP.md) |
| **Verify with** | Product |

---

## 11. Production on-call and incident response

| | |
|--|--|
| **Missing** | Pager, escalation, who can run emergency migrations |
| **Why it matters** | Outages after handover |
| **Source** | Company ops |
| **Verify with** | Management |

---

## 12. Legal / compliance scope

| | |
|--|--|
| **Missing** | DPA, data residency, retention policies for child data |
| **Why it matters** | Feature and logging decisions |
| **Source** | Legal |
| **Verify with** | Compliance |

---

## 13. Complete OpenAPI in static form

| | |
|--|--|
| **Missing** | Exported OpenAPI JSON in repo (live `/docs` is source of truth) |
| **Why it matters** | Offline API reference |
| **Mitigation** | Hit `/openapi.json` on deployed API and archive periodically |
| **Verify with** | Backend owner |

---

## 14. Hostinger / DNS full zone map

| | |
|--|--|
| **Missing** | Complete DNS record list beyond email doc |
| **Why it matters** | Domain moves |
| **Source** | Cloudflare/Hostinger dashboards |
| **Verify with** | IT |

---

## 15. Production analytics and monitoring

| | |
|--|--|
| **Missing** | Sentry, Datadog, or Railway metrics dashboards (Sentry not in code) |
| **Why it matters** | Proactive failure detection |
| **Source** | Infra choices |
| **Verify with** | DevOps |

---

## Quality check — handover doc coverage

Using **only** `docs/handover/*` plus linked repo docs:

| Question | Covered? |
|----------|----------|
| What does the app do? | Yes — 01 |
| Who uses it? | Yes — 01, 10 |
| Technologies? | Yes — 01, 02, 07, 08 |
| Run locally? | Yes — 04 |
| Configure env? | Yes — 05 |
| Database technology and tables? | Yes — 06 (not every column) |
| AuthN/Z? | Yes — 10 |
| Major features? | Yes — 12 |
| APIs exist? | Partial — 09 + `/docs`; not every schema |
| Frontend ↔ backend? | Yes — 08, apiClient |
| Deploy? | Yes — 14 (auto-deploy gap above) |
| Deploy migration? | Yes — 14, 06 |
| Rollback? | Partial — Vercel/Railway; DB rollback cautious |
| Production hosts? | Yes — 14, 00 |
| External services? | Yes — 13 |
| Business rules? | Yes — 11 (not exhaustive) |
| Known issues? | Yes — 18 |
| Rebuild from scratch? | Yes — 20 |
| Canonical UI/UX contract? | Yes — [docs/design/UI_CONTRACT.md](../design/UI_CONTRACT.md); Stitch `DESIGN.md` files cited there are still missing from the repo |

**Partial answers** should be upgraded when gap owners supply facts — update the relevant handover file and remove or shrink entries here.
