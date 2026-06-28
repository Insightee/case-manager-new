# Future: clinical_evidence_event_snapshots

_Status: artifact only — do not implement until materializer latency requires it_

## Purpose

Cache materialized `ClinicalEvidenceEventContract` JSON for fast aggregation. **Does not replace** `session_goal_entries` or `strategy_use_events` as source of truth.

## Trigger thresholds (suggested)

- Monthly report compile p95 > 3s for cases with > 30 session logs, OR
- Clinical Brain case-month query p95 > 1s at 10k parallel clients

## Proposed schema

```sql
CREATE TABLE clinical_evidence_event_snapshots (
  id SERIAL PRIMARY KEY,
  evidence_event_id UUID NOT NULL,
  contract_version VARCHAR(16) NOT NULL,
  source_hash VARCHAR(64) NOT NULL,
  case_id INTEGER NOT NULL REFERENCES cases(id),
  daily_log_id INTEGER REFERENCES daily_logs(id),
  goal_entry_id INTEGER,
  strategy_use_event_id INTEGER,
  materialized_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (evidence_event_id, contract_version)
);

CREATE INDEX idx_cee_snapshots_case_month ON clinical_evidence_event_snapshots (case_id, created_at);
```

## Invalidation

Re-materialize snapshot when:
- Source `goal_entry_id` or `strategy_use_event_id` row updated
- `source_hash` of contributing rows changes

## Pass 1 note

Pass 1 uses live materialization only. No Alembic migration in this phase.
