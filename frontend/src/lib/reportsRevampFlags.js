/**
 * Feature flags for Reports & Clinical Documentation revamp.
 * Default ON for local/WIP — set VITE_REPORTS_REVAMP=false to compare legacy case profile.
 */

const revampEnv = import.meta.env.VITE_REPORTS_REVAMP
const revampOptOut = revampEnv === 'false'
const revampOptIn = revampEnv === 'true' || !revampOptOut

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

export const GOALS_STRATEGIES_ENGINE_V2 = revampOptIn

export const IEP_REVIEW_SUGGESTIONS = false

export const EVIDENCE_DRIVE_V2 = revampOptIn

export const AI_GATEWAY_HARDENED = false

export function isReportsRevampActive(portal = 'therapist') {
  if (!REPORTS_REVAMP_ENABLED) return false
  if (portal === 'therapist') return REPORTS_REVAMP_THERAPIST
  if (portal === 'admin') return REPORTS_REVAMP_ADMIN_CASE
  if (portal === 'parent') return REPORTS_REVAMP_PARENT
  return false
}
