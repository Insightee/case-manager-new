# Report Architecture — Canonical Spine & Compatibility Paths

_Last updated: June 2026_

## Canonical spine

**`clinical_reports`** is the future canonical report lifecycle engine for all report types:

| Report type | Engine status | Notes |
|-------------|---------------|-------|
| `observation` | Implemented | Builder + lifecycle when reports revamp flag is on |
| `iep` | Implemented | Report lifecycle; structured plan data may live in `iep_plans` |
| `monthly` | Implemented (engine) | New writes via engine when flag enabled; legacy remains active |
| `progress` | Planned | Enum exists; sections TBD |
| `history` | Planned | Enum exists; sections TBD |

Models: `ClinicalReport`, `ClinicalReportSection`, `ClinicalReportVersion`, `ClinicalReportEvidence`, `ClinicalReportReviewEvent`.

Service: `report_engine_service.py`  
API: `clinical_reports.py` (`/api/v1/cases/{id}/reports/*`, `/api/v1/reports/{id}/*`)

## Compatibility paths (active until engine parity verified)

### Legacy monthly (`monthly_reports`)

- **Status:** Active compatibility path for create/edit/submit/approve/PDF/parent approval.
- **Models:** `MonthlyReport`, `MonthlyReportSection` (legacy sections table).
- **API:** `/api/v1/reports/monthly/*`, `/api/v1/admin/reports/monthly/*`
- **Parent:** `/api/v1/parent/reports/monthly/{id}`
- **Sync:** On legacy approval/publish, `monthly_report_sync_service` mirrors to `clinical_reports(type=monthly)` idempotently.
- **Future:** Stop new legacy writes after `MONTHLY_REPORTS_USE_CLINICAL_ENGINE` is production-safe.

### Legacy observation (`observation_reports`)

- **Status:** Compatibility + historical read fallback.
- **Engine:** `clinical_reports(type=observation)` is canonical when revamp flag on.
- **Input:** `ObservationChecklist` remains source evidence/intake.

### Legacy IEP plan (`iep_plans`)

- **Status:** Active structured plan data (goals, strategies, domains).
- **API:** `/api/v1/cases/{id}/iep-plan`, `/api/v1/admin/cases/{id}/iep-plan`
- **Report lifecycle:** `clinical_reports(type=iep)` owns draft/submit/return/approve/lock/parent visibility.
- **Bridge:** `iep_report_bridge_service` syncs approved/shared plans to engine IEP reports.

## Clinical Brain v1

Clinical Brain is **not** a third report engine. It is an evidence, suggestion, drafting, and quality-check layer that attaches to `clinical_reports`:

- Draft section content → `ClinicalReportSection` (therapist must accept/edit)
- Evidence summaries → `ClinicalReportEvidence`
- Suggestions → section metadata / `ai_draft_outputs` (`target_type=clinical_report_section`)
- Audit → `ai_generation_logs` (existing)

Clinical Brain must not: create independent reports, approve, publish to parents, mutate IEP goals automatically, or bypass CM review.

## Clinical Evidence Event Contract (Pass 1)

Structured session evidence is materialized into **ClinicalEvidenceEventContract** objects from `session_goal_entries` + `strategy_use_events` (logical view, no new evidence table).

- Spec: [`docs/CLINICAL_EVIDENCE_EVENT_CONTRACT.md`](CLINICAL_EVIDENCE_EVENT_CONTRACT.md)
- Roadmap: [`docs/CLINICAL_EVIDENCE_ROADMAP.md`](CLINICAL_EVIDENCE_ROADMAP.md)
- API: `GET /api/v1/daily-logs/{id}/clinical-evidence-events`, `GET /api/v1/cases/{id}/clinical-evidence-events?month=YYYY-MM`
- `clinical_brain_evidence_service` consumes materialized events for report evidence summaries

Pass 1 does **not** wire monthly report compilation or frontend evidence capture (V2).

## Parent portal bridge

Parent APIs use **engine-first, legacy-fallback** resolution (`parent_canonical_report_service`):

1. Look for approved/locked parent-visible `clinical_reports` for the case + type.
2. If found, return via parent-safe serializer.
3. Else fall back to legacy `MonthlyReport` / `ObservationReport` / `IepPlan` / attachments.

Parents never see: drafts, returned reports, internal notes, CM review notes, raw AI output, Clinical Brain quality flags, prompt/model metadata.

## Feature flags

| Flag | Location | Default | Purpose |
|------|----------|---------|---------|
| `REPORTS_ENGINE_V1` | `reportsRevampFlags.js` | on | Observation/IEP engine UI |
| `MONTHLY_REPORTS_USE_CLINICAL_ENGINE` | `reportsRevampFlags.js` | **off** | Monthly builder uses engine APIs |

## Frontend monthly callers (legacy today)

| Component | API |
|-----------|-----|
| `CreateDraftModal.jsx` | `POST /api/v1/reports/monthly` |
| `CaseReportsPanel.jsx` | `GET/POST /api/v1/reports/monthly` |
| `ReportEditPage.jsx` | `GET/PATCH/POST /api/v1/reports/monthly/{id}` |
| `AdminReportsPage.jsx` | `/api/v1/admin/reports/monthly` |
| `ParentReportsPage.jsx` | `/api/v1/parent/reports/monthly/{id}` |

## Migration notes

- Do not delete legacy tables in this phase.
- Legacy monthly approval triggers best-effort sync to engine (idempotent).
- Manual check: compare parent hub items when both engine and legacy monthly exist for same month.

## Migration notes

- No destructive migrations in this PR. `clinical_reports` tables already exist.
- Legacy monthly approval triggers `monthly_report_sync_service` (idempotent).
- Enable engine monthly UI with `VITE_MONTHLY_REPORTS_USE_CLINICAL_ENGINE=true` when ready.
- Manual check: compare parent hub items when both engine and legacy monthly exist for same month.
- Optional future migration: backfill historical monthly rows via sync on read.

## Tests added

- `backend/app/tests/test_clinical_reports_strangler.py` — monthly lifecycle, parent visibility, sync idempotency, brain draft attachment, API start.

## Known risks

- Monthly engine parity with legacy PDF/download not yet complete.
- Parent dual-read must prefer engine when both exist (implemented in `parent_canonical_report_service`).
- IEP plan vs IEP report split requires clear UI labeling.
- `clinical_brain_*` services are boundary-only; no standalone report tables created.
