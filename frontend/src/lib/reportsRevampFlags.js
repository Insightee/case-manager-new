/**
 * Feature flags for Reports & Clinical Documentation revamp.
 * Master gates (VITE_ENABLE_*) default OFF in production — opt in on staging only.
 */

import {
  ENABLE_CLINICAL_BRAIN,
  ENABLE_REPORT_BUILDER,
  ENABLE_REPORTS,
  isClinicalBrainEnabled,
  isReportBuilderEnabled,
  isReportsModuleEnabled,
} from './productFeatureFlags.js'

const revampEnv = import.meta.env.VITE_REPORTS_REVAMP
const revampSubFlag = revampEnv === 'true' || revampEnv !== 'false'

/** Reports hub + case profile revamp — requires module gate */
export const REPORTS_REVAMP_ENABLED = isReportsModuleEnabled() && revampSubFlag

export const REPORTS_REVAMP_THERAPIST = REPORTS_REVAMP_ENABLED

export const REPORTS_REVAMP_ADMIN_CASE = REPORTS_REVAMP_ENABLED

export const REPORTS_REVAMP_PARENT = isReportsModuleEnabled()

/** Session log structured evidence — safe production UX; not gated by reports module */
export const STRUCTURED_SESSION_EVIDENCE =
  import.meta.env.VITE_STRUCTURED_SESSION_EVIDENCE !== 'false'

export const IEP_CARD_BUILDER = isReportBuilderEnabled() && revampSubFlag

export const GOAL_REPOSITORY_ENABLED = isClinicalBrainEnabled() && revampSubFlag

export const AI_ENABLED = false

export const AI_PROVIDER = 'mock'

export const CLINICAL_QUALITY_DASHBOARD = isClinicalBrainEnabled()

export const MONTHLY_EVIDENCE_V2 = isClinicalBrainEnabled()

export const GOALS_STRATEGIES_ENGINE_V2 =
  import.meta.env.VITE_GOALS_STRATEGIES_ENGINE_V2 !== 'false'

export const IEP_REVIEW_SUGGESTIONS = isClinicalBrainEnabled()

export const EVIDENCE_DRIVE_V2 = REPORTS_REVAMP_ENABLED

export const AI_GATEWAY_HARDENED = false

export const REPORTS_ENGINE_V1 = isReportBuilderEnabled() && revampSubFlag

export function isReportsEngineActive() {
  return REPORTS_ENGINE_V1 && REPORTS_REVAMP_ENABLED
}

export const MONTHLY_REPORTS_USE_CLINICAL_ENGINE =
  import.meta.env.VITE_MONTHLY_REPORTS_USE_CLINICAL_ENGINE === 'true' && isReportsModuleEnabled()

export function isMonthlyClinicalEngineActive() {
  return MONTHLY_REPORTS_USE_CLINICAL_ENGINE && isReportsEngineActive()
}

export function isReportsRevampActive(portal = 'therapist') {
  if (!REPORTS_REVAMP_ENABLED) return false
  if (portal === 'therapist') return REPORTS_REVAMP_THERAPIST
  if (portal === 'admin') return REPORTS_REVAMP_ADMIN_CASE
  if (portal === 'parent') return REPORTS_REVAMP_PARENT
  return false
}

export { ENABLE_CLINICAL_BRAIN, ENABLE_REPORT_BUILDER, ENABLE_REPORTS }
