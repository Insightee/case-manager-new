/**
 * Feature flags for Reports & Clinical Documentation revamp.
 * Default OFF — set VITE_REPORTS_REVAMP=true in frontend/.env.local to test the new case profile locally.
 */

const revampOptIn = import.meta.env.VITE_REPORTS_REVAMP === 'true'

export const REPORTS_REVAMP_ENABLED = revampOptIn

export const REPORTS_REVAMP_THERAPIST = revampOptIn

export const REPORTS_REVAMP_ADMIN_CASE = revampOptIn

export const REPORTS_REVAMP_PARENT = false

export const STRUCTURED_SESSION_EVIDENCE = revampOptIn

export const IEP_CARD_BUILDER = revampOptIn

export const GOAL_REPOSITORY_ENABLED = revampOptIn

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
 *
 * Local dev: add to frontend/.env.local → VITE_REPORTS_REVAMP=true
 */

export function isReportsRevampActive(portal = 'therapist') {
  if (!REPORTS_REVAMP_ENABLED) return false
  if (portal === 'therapist') return REPORTS_REVAMP_THERAPIST
  if (portal === 'admin') return REPORTS_REVAMP_ADMIN_CASE
  if (portal === 'parent') return REPORTS_REVAMP_PARENT
  return false
}
