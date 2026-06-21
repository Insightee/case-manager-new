# Insighte Insights Engine

_Last updated: June 2026_

**Audience:** Engineering, product, clinical leads, and AI agents.

**Related:** [CLINICAL_REPORTS_UI_DESIGN.md §14](./CLINICAL_REPORTS_UI_DESIGN.md#14-insights-tab--visual-contract) · [CTO_DIRECTION_AND_DESIGN.md](./CTO_DIRECTION_AND_DESIGN.md)

---

## North star

> **Generate only when needed. Save the snapshot. Reuse it across reports, session logs, IEP reviews, and supervision.**

The Insights Engine is an on-demand, AI-supported clinical snapshot system. It is **not** a heavy analytics dashboard. Opening the Insights tab must never trigger AI.

| Layer | Share of system | Responsibility |
|-------|-----------------|----------------|
| Layer 1 | ~80–90% | SQL counts, rules, evidence strength, documentation health |
| Layer 2 | Storage | Saved `clinical_snapshots`, feedback, audit logs |
| Layer 3 | On-demand | Structured summary → compact prompt → single AI call |
| Layer 4 | Retrieval | Reference chunks (strategy pool, protocols) — top-k only |

---

## Core rules

1. **No AI on tab open, month change, report open, or session log typing.**
2. **One Generate click = one generation call** (unless explicit retrieval embedding).
3. **Reuse saved snapshots** when `input_hash` unchanged.
4. **AI condenses structured truth** — it does not create clinical truth or finalize reports.
5. **No diagnosis generation**, no automatic goal closure, no punishment/compliance framing.
6. **Parent sees approved parent-safe content in reports only** — never raw internal snapshots.

---

## Supported insight types

| Value | Purpose |
|-------|---------|
| `full_snapshot` | Monthly clinical focus summary |
| `goal_suggestions` | Goal-level recommendations |
| `strategy_review` | Strategy effectiveness signals |
| `supports_accommodations` | Support/accommodation suggestions |
| `what_not_working` | Mixed-signal clinical review |
| `parent_safe_draft` | Parent-facing draft (CM approval required) |
| `report_support` | Report section drafting |
| `session_log_support` | Session log improvement |
| `iep_support` | IEP/goal/strategy suggestions |

---

## Role matrix

| Role | Can generate | Can send CM review | Can approve parent-safe | Can manage references |
|------|--------------|-------------------|-------------------------|----------------------|
| Therapist (assigned case) | Yes | Yes | No | No |
| Case Manager / Supervisor | Yes | Yes | Yes | No |
| Admin / Clinical Lead | Yes | Yes | Yes | Yes |
| Parent | No | No | No | No |

---

## Safety and language

**Prefer:** appeared helpful · mixed evidence · needs review · not enough evidence · consider observing · may need additional support

**Avoid:** failed · non-compliant · manipulative · attention-seeking · ineffective (as absolute claim)

Internal notes must never appear in parent-safe outputs.

---

## API surface

Base: `/api/v1/cases/{case_id}/insights`

| Method | Path | AI? | Description |
|--------|------|-----|-------------|
| GET | `/data-preview?month=YYYY-MM` | No | Deterministic counts for selected month |
| POST | `/generate-snapshot` | Yes (on click) | Generate or reuse snapshot |
| POST | `/followup` | Yes (on click) | Ask about saved snapshot |
| GET | `/snapshots?month=YYYY-MM` | No | List snapshots for month |
| GET | `/snapshots/{id}` | No | Snapshot detail |
| POST | `/snapshots/{id}/feedback` | No | User feedback action |
| POST | `/snapshots/{id}/send-review` | No | Therapist → CM queue |
| POST | `/snapshots/{id}/approve` | No | CM approves (parent-safe) |
| POST | `/snapshots/{id}/reject` | No | CM rejects |

Session log assist: `/api/v1/session-logs/{log_id}/ai/*`  
Reports: `/api/v1/reports/{report_id}/insights/insert-snapshot-section`

---

## Phase delivery map

| Phase | Deliverable | Acceptance |
|-------|-------------|------------|
| 1 | Simple Insights tab UI | Layout matches contract; no AI calls |
| 2 | Data preview endpoint | Tab open = preview only |
| 3 | Snapshot storage tables + CRUD | Records persist; RBAC enforced |
| 4 | Mock AI gateway + generate | Generate works without API key |
| 5 | Structured summary + prompt builder | AI receives compact JSON only |
| 6 | OpenAI/Gemini providers | Provider switch via env; budget guard |
| 7 | Reference document RAG | Keyword fallback; admin upload |
| 8 | Session log AI assist | Buttons only; drafts not auto-saved |
| 9 | Reports integration | Reuse snapshot in monthly reports |
| 10 | IEP/Goals/Strategies | On-demand suggestion buttons |
| 11 | Parent-safe output | Parent blocked from snapshot APIs |
| 12 | Audit + admin settings | Usage visible; budget enforced |
| 13 | Tests + QA checklist | Targeted tests pass |

---

## Integration points

- **Insights tab** — primary home for monthly snapshots
- **Session logs** — improve note, check evidence, suggest capture
- **Monthly reports** — insert snapshot sections
- **IEP / Goals / Strategies** — review suggestions from saved snapshots
- **Parent portal** — approved report sections only

`clinical-quality-summary` remains available for Reports/CM surfaces; it is not the primary Insights tab UI.

---

## Manual QA checklist

- [ ] Opening Insights tab does not call AI
- [ ] Month selector refreshes data preview only
- [ ] Generate button creates/reuses snapshot (mock mode)
- [ ] Ask panel disabled until snapshot exists
- [ ] Send to CM review works for therapist
- [ ] Therapist cannot approve parent-safe draft
- [ ] Parent cannot access `/insights/snapshots`
- [ ] Mobile stacks AI panel below cards
- [ ] Session log typing does not trigger AI
- [ ] Reports can insert snapshot without re-generation when hash unchanged
