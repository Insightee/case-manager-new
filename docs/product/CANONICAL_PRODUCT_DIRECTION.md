# Canonical Product Direction

**Status:** ACTIVE — authoritative for all new session-log and clinical-brain work.

## Core decision

The session-log V1 is a **voice-first clinical confirmation workflow**. It is not a recreation of the old manual form and not a parallel log type.

Voice recording, typed source notes, and transcript review are **capture methods** inside one canonical session-log workflow.

## Therapist journey

1. Open the scheduled session
2. Confirm or edit session time (with reason + audit)
3. Record a voice note or type/edit the source note
4. Re-record when required
5. Review transcript / source note
6. Review structured clinical draft from extraction
7. Confirm or reject goals matched from the active IEP
8. Review evidence under each matched goal
9. Review emerging goal suggestions; send accepted ones for CM review
10. Confirm strategies used and how they were applied
11. Review what happened, child response, challenges, strengths
12. Add therapist reflection (private)
13. Preview parent-facing and CM-facing outputs
14. Submit

The interface is a **confirm-and-adjust surface**, not a blank chip-heavy form.

## AI boundaries

AI may: transcribe, extract, match, retrieve, rewrite, summarise.

AI must **not**:

- Finalise clinical truth without therapist confirmation
- Add an active IEP goal automatically
- Approve organisation-wide strategies
- Change a submitted clinical record silently
- Decide that a goal is achieved
- Replace CM review

## Architecture principle

Build a structured clinical orchestration system, not an AI that remembers every report.

- **Deterministic code + relational data:** cases, sessions, goal/strategy IDs, evidence links, statuses, approvals, audit, counts, trends, report eligibility
- **AI:** transcription, extraction, drafting, candidate matching, parent-friendly narrative, evidence synthesis

**One canonical write path:** `SessionLogApplicationService.submit_log()` / `resubmit_log()`.

## Audience projections

One approved canonical session record generates:

| View | Content |
|------|---------|
| Therapist | Editable draft, goal evidence, strategies, reflection |
| CM | Clinical detail, source evidence, suggestions, audit, pending review |
| Parent | Respectful summary — no internal reflection or CM flags |

Do not maintain separate manually edited versions per audience.

## Precedence (conflict resolution)

1. This document + `SESSION_LOG_V1.md` + `CLINICAL_BRAIN_ARCHITECTURE.md`
2. `docs/product/canonical-manifest.yml`
3. `docs/design/DESIGN.md` + `UI_CONTRACT.md`
4. API contracts (`SessionEvidenceProjection`, daily-logs API)
5. Production behaviour requiring migration support
6. `docs/legacy/*` — historical only

## Related docs

- [SESSION_LOG_V1.md](./SESSION_LOG_V1.md) — workflow, state models, source-of-truth hierarchy
- [CLINICAL_BRAIN_ARCHITECTURE.md](./CLINICAL_BRAIN_ARCHITECTURE.md) — services, evidence, reports bridge
- [canonical-manifest.yml](./canonical-manifest.yml) — file/route classification and deletion gates
