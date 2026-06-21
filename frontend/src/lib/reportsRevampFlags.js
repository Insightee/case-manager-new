/** Feature flags for Reports & Clinical Documentation revamp (default off for safe rollout). */

export const REPORTS_REVAMP_ENABLED = true

export const REPORTS_REVAMP_THERAPIST = true

export const REPORTS_REVAMP_ADMIN_CASE = true

export const REPORTS_REVAMP_PARENT = false

export const STRUCTURED_SESSION_EVIDENCE = true

export const IEP_CARD_BUILDER = true

export const GOAL_REPOSITORY_ENABLED = true

export const AI_ENABLED = false

export const AI_PROVIDER = 'mock'

/** Phase 2 — default false until rollout (Step 12). Enable per rollout checklist. */
export const CLINICAL_QUALITY_DASHBOARD = false

export const MONTHLY_EVIDENCE_V2 = false

export const IEP_REVIEW_SUGGESTIONS = false

export const EVIDENCE_DRIVE_V2 = false

export const AI_GATEWAY_HARDENED = false

/**
 * Rollout order:
 * 1. CLINICAL_QUALITY_DASHBOARD (internal admin)
 * 2. Therapist overview + insights (Phase 1 flags)
 * 3. CM supervision + /admin/clinical-dashboard
 * 4. MONTHLY_EVIDENCE_V2 pilot cases
 * 5. Parent preview CM-only (REPORTS_REVAMP_PARENT stays false)
 * 6. Parent revamp + real AI — out of Phase 2 scope
 */

export function isReportsRevampActive(portal = 'therapist') {
  if (!REPORTS_REVAMP_ENABLED) return false
  if (portal === 'therapist') return REPORTS_REVAMP_THERAPIST
  if (portal === 'admin') return REPORTS_REVAMP_ADMIN_CASE
  if (portal === 'parent') return REPORTS_REVAMP_PARENT
  return false
}
