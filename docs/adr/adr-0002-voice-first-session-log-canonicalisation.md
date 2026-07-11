---
title: "ADR-0002: Voice-First Session Log and SessionLogApplicationService Canonicalisation"
status: "Accepted"
date: "2026-07-12"
authors: "Engineering, Clinical Product, Case Manager Operations"
tags: ["architecture", "session-log", "voice", "clinical-brain"]
supersedes: ""
superseded_by: ""
---

# ADR-0002: Voice-First Session Log and SessionLogApplicationService Canonicalisation

## Status

**Accepted**

## Context

Therapists capture session evidence through voice-first confirm-and-edit flows on mobile field devices. The legacy session log stack split writes across `log_service`, `clinical_evidence_service`, and ad-hoc route handlers, causing duplicate validation, inconsistent structured JSON persistence, and resubmit failures when structured evidence derived prose after prose validation ran first.

Clinical doctrine requires structured signals (goals, strategies, progress) as reusable knowledge assets—not free-text-only logs. Voice extraction must condense therapist input, not create clinical truth. Mobile-first UX demands sub-five-minute submission with thumb-zone actions and progressive disclosure across five screens.

## Decision

Adopt a thin **`SessionLogApplicationService`** as the single write orchestrator for session logs. All therapist create/update/resubmit paths route through `submit_log`, `update_log`, and `resubmit_log`, which in one transaction: apply lifecycle fields, persist `structured_session_json`, write relational evidence, and derive legacy prose fields. Voice-first UI (`VoiceSessionLogFlow`) is the canonical therapist entry; structured JSON is the source of truth for read projections (`SessionEvidenceProjectionService`, `SessionLogReadOnly`).

Resubmit applies structured evidence **before** prose validation so voice-derived drafts resubmit without false `activities_done` rejections. Additive Alembic migrations (`session_audio_recordings`, `structured_session_json`, `session_time_audit_events`) ship on staging before API deploy; production remains on `main` until explicit merge.

## Consequences

### Positive

- **POS-001**: Single submission transaction eliminates duplicate validation and drift between structured and relational evidence.
- **POS-002**: Structured JSON enables 80–95% context compression for downstream LLM/report pipelines per token economy rules.
- **POS-003**: Mobile-first voice flow reduces therapist screen time while preserving confirm-and-edit clinical safety.
- **POS-004**: Read projections decouple parent/CM/therapist views from legacy prose fields without duplicate data entry.

### Negative

- **NEG-001**: Transitional dual paths (`session_evidence` legacy payload, deprecated `SubmitSessionLogForm`) remain until usage gates clear.
- **NEG-002**: Voice audio on Railway requires durable object storage (`STORAGE_PROVIDER=r2`); ephemeral disk is unsuitable for production voice retention.
- **NEG-003**: Large surface area in first release increases staging QA burden before prod merge.

## Alternatives Considered

### Monolithic orchestrator with feature flag

- **ALT-001**: **Description**: New `SessionLogOrchestrator` behind `ENABLE_SESSION_LOG_V2` flag routing all writes.
- **ALT-002**: **Rejection Reason**: Feature-flagged orchestrators duplicate code paths indefinitely; usage-based deprecation gates preferred per canonicalisation plan.

### Keep route-level branching in `daily_logs.py`

- **ALT-003**: **Description**: Continue inline `log_service` + conditional structured apply in each route handler.
- **ALT-004**: **Rejection Reason**: Caused resubmit ordering bug and inconsistent validation; violates thin-route/fat-service architecture.

### Free-text-only voice transcript as source of truth

- **ALT-005**: **Description**: Store transcript and derive reports directly from prose without structured JSON snapshot.
- **ALT-006**: **Rejection Reason**: Violates Clinical Brain doctrine—free text is a liability; structured signals are organizational assets.

## Implementation Notes

- **IMP-001**: Route handlers in `daily_logs.py` delegate to `SessionLogApplicationService`; responses include `structured_session_json` via `include_structured=True`.
- **IMP-002**: Run Alembic `upgrade head` on **staging** Railway Postgres before deploying API changes; migrations are additive (new table + nullable columns). Do not run on production until merge to `main`.
- **IMP-003**: Monitor staging `/health`, voice upload success rate, resubmit acceptance rate, and deprecated path usage via `session_log_deprecated_usage_report.py` before prod promotion.

## References

- **REF-001**: `docs/product/SESSION_LOG_V1.md`, `docs/product/CLINICAL_BRAIN_ARCHITECTURE.md`, `docs/product/canonical-manifest.yml`
- **REF-002**: `docs/design/DESIGN.md` — five-screen mobile-first voice hierarchy
- **REF-003**: `docs/VOICE_SESSION_LOG_DEPRECATION.md`, `docs/STAGING_HANDOFF.md`
