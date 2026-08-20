/**
 * Feature flags for Reports & Clinical Documentation revamp.
 * On whenever reports are enabled, including production. Set VITE_REPORTS_REVAMP=false to compare the legacy UI.
 */

import { isReportsModuleEnabled } from './productFeatureFlags.js'

function readReportsRevampFlag() {
  const raw = import.meta.env.VITE_REPORTS_REVAMP
  if (raw === 'true') return true
  if (raw === 'false') return false
  return isReportsModuleEnabled()
}

const revampOptIn = readReportsRevampFlag()

export const REPORTS_REVAMP_ENABLED = revampOptIn

export const REPORTS_REVAMP_THERAPIST = revampOptIn

export const REPORTS_REVAMP_ADMIN_CASE = revampOptIn

export const REPORTS_REVAMP_PARENT = revampOptIn

export const STRUCTURED_SESSION_EVIDENCE = revampOptIn

export const IEP_CARD_BUILDER = revampOptIn

export const GOAL_REPOSITORY_ENABLED = revampOptIn

export const AI_ENABLED = false

export const AI_PROVIDER = 'mock'

export const CLINICAL_QUALITY_DASHBOARD = false

export const MONTHLY_EVIDENCE_V2 = false

export const GOALS_STRATEGIES_ENGINE_V2 = revampOptIn

export const IEP_REVIEW_SUGGESTIONS = false

export const EVIDENCE_DRIVE_V2 = revampOptIn

export const AI_GATEWAY_HARDENED = false

export const REPORTS_ENGINE_V1 = revampOptIn

export function isReportsEngineActive() {
  return REPORTS_ENGINE_V1 && REPORTS_REVAMP_ENABLED
}

export function isReportsRevampActive(portal = 'therapist') {
  if (!REPORTS_REVAMP_ENABLED) return false
  if (portal === 'therapist') return REPORTS_REVAMP_THERAPIST
  if (portal === 'admin') return REPORTS_REVAMP_ADMIN_CASE
  if (portal === 'parent') return REPORTS_REVAMP_PARENT
  return false
}
