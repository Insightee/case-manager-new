# Clinical Evidence Roadmap

_Four-pass build order for the living Clinical Brain evidence engine._

## Pass 1 — Contract and materializer (DONE)

**Scope:** Backend only. No UI. No DB migrations. No new evidence table.

Deliverables:
- [`clinical_evidence_event_contract.json`](../backend/app/schemas/clinical_evidence_event_contract.json)
- [`clinical_evidence_event_service.py`](../backend/app/services/clinical_evidence_event_service.py)
- Read-only APIs
- Clinical Brain evidence summary consumes materialized events
- [`docs/CLINICAL_EVIDENCE_EVENT_CONTRACT.md`](CLINICAL_EVIDENCE_EVENT_CONTRACT.md)
- Targeted tests

## Pass 2 — Session log evidence UI (V2 capture)

**Scope:** Compact evidence card inside session log. Mobile-first chips, not long forms.

### V2 UI flow

```text
Step 1: Select goal
Step 2: Select strategy/support
Step 3: Tap response + participation
Step 4: Optional note
Step 5: Save
```

### Primary chips (first ship)

- `child_response`
- `regulation_signal`
- `therapist_interpretation`
- `child_agency_signal`
- `environment_fit`
- `adaptation_type`

### Advanced (progressive disclosure)

- `+ Add barrier`
- `+ Add regulation context`
- `+ Mark sensitive`

### Smart defaults (editable)

- `strategy_feedback = NEEDS_ADAPTATION` → suggest `therapist_interpretation = continue_with_adaptation`
- `child_response = requested_break` → suggest `regulation_signal = needed_break`

### Evidence quality nudges (non-blocking)

- Missing child response
- Strategy marked helpful but no activity context
- Goal addressed without strategy/support

Spec: [`docs/artifacts/clinical_evidence_v2_ui_spec.md`](artifacts/clinical_evidence_v2_ui_spec.md)

### Backend at V2

- Extend `SessionEvidenceSave` payload with V1.1 optional fields
- Persist to JSON columns or nullable columns (Alembic decision at V2)
- Set `field_provenance.* = human_selected` on save
- Materializer reads stored values instead of null stubs

## Pass 3 — Report + CM review integration

**Scope:** Monthly report compiler consumes materialized events → goal summary → draft sections.

- Parent-safe preview before submission
- CM evidence gap dashboard before approval

Spec: [`docs/artifacts/clinical_evidence_cm_dashboard.md`](artifacts/clinical_evidence_cm_dashboard.md)

**Not in Pass 1:** Do not wire monthly report generation until Pass 3.

## Pass 4 — Living learning loop

**Scope:** Organisation-wide strategy pool learning (after enough clean structured data).

- Brain recommendation feedback (`recommendation_feedback` section)
- Strategy candidate review queue
- Goal concept drift detection
- Clinical lead learning dashboard

Spec: [`docs/artifacts/clinical_evidence_clinical_lead_dashboard.md`](artifacts/clinical_evidence_clinical_lead_dashboard.md)

## Snapshot table trigger (future)

Add `clinical_evidence_event_snapshots` when:
- Monthly compile p95 latency exceeds threshold, OR
- Clinical Brain aggregation queries exceed SLO

Spec: [`docs/artifacts/clinical_evidence_snapshot_table.md`](artifacts/clinical_evidence_snapshot_table.md)

## Non-negotiables (all passes)

1. Child agency over compliance framing
2. AI never creates clinical truth without human acceptance
3. Parent visibility is explicit, default false
4. `evidence_strength` is completeness only — not parent-facing
5. No duplicate evidence stores — logical contract over source rows until cache proven necessary
