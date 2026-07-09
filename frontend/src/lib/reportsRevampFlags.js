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
/** Explicit opt-in for revamp shell — avoids half-built UI on by default. */
const revampSubFlag = revampEnv === 'true'

/** Reports hub + case profile revamp — module or builder gate */
export const REPORTS_REVAMP_ENABLED =
  revampSubFlag && (isReportsModuleEnabled() || isReportBuilderEnabled())

export const REPORTS_REVAMP_THERAPIST = REPORTS_REVAMP_ENABLED

export const REPORTS_REVAMP_ADMIN_CASE = REPORTS_REVAMP_ENABLED

export const REPORTS_REVAMP_PARENT = isReportsModuleEnabled()

/** Session log structured evidence — opt in (stabilisation: default legacy log form). */
export const STRUCTURED_SESSION_EVIDENCE =
  import.meta.env.VITE_STRUCTURED_SESSION_EVIDENCE === 'true'

export const IEP_CARD_BUILDER = isReportBuilderEnabled() && revampSubFlag

export const GOAL_REPOSITORY_ENABLED = isClinicalBrainEnabled() && revampSubFlag

export const AI_ENABLED = false

export const AI_PROVIDER = 'mock'

export const CLINICAL_QUALITY_DASHBOARD = isClinicalBrainEnabled()

export const MONTHLY_EVIDENCE_V2 = isClinicalBrainEnabled()

/** Assigned goals/strategies v2 tab — opt in until clinical sign-off. */
export const GOALS_STRATEGIES_ENGINE_V2 =
  import.meta.env.VITE_GOALS_STRATEGIES_ENGINE_V2 === 'true'

/** Stitch case Reports tab (timeline, attention, filters) — defer until rebuild. */
export const CASE_REPORTS_TAB_V2 =
  import.meta.env.VITE_CASE_REPORTS_TAB_V2 === 'true'

export function isCaseReportsTabV2Active() {
  return CASE_REPORTS_TAB_V2 && isReportsRevampActive('therapist')
}

export const IEP_REVIEW_SUGGESTIONS = isClinicalBrainEnabled()

export const EVIDENCE_DRIVE_V2 = REPORTS_REVAMP_ENABLED

export const AI_GATEWAY_HARDENED = false

export const REPORTS_ENGINE_V1 = isReportBuilderEnabled() && revampSubFlag

export function isReportsEngineActive() {
  return REPORTS_ENGINE_V1 && REPORTS_REVAMP_ENABLED
}

/** Observation + IEP Forest Light builders (does not require full monthly engine). */
export function isClinicalReportBuilderActive() {
  return REPORTS_ENGINE_V1
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
