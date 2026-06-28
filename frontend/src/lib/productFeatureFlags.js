/**
 * Production-safe module gates. Unset env vars default to OFF (safe for production).
 * Enable on staging via Vercel env or frontend/.env.local.
 */

function readEnvFlag(key) {
  const raw = import.meta.env[key]
  if (raw === 'true') return true
  if (raw === 'false') return false
  return false
}

/** Monthly reports hub, parent reports, admin report review UI */
export const ENABLE_REPORTS = readEnvFlag('VITE_ENABLE_REPORTS')

/** Therapist invoices, admin client billing / ledger composer */
export const ENABLE_BILLING = readEnvFlag('VITE_ENABLE_BILLING')

/** Goal bank, strategy pool, review queue, clinical AI assist */
export const ENABLE_CLINICAL_BRAIN = readEnvFlag('VITE_ENABLE_CLINICAL_BRAIN')

/** Observation / IEP / monthly report builder routes */
export const ENABLE_REPORT_BUILDER = readEnvFlag('VITE_ENABLE_REPORT_BUILDER')

export function isReportsModuleEnabled() {
  return ENABLE_REPORTS
}

export function isBillingModuleEnabled() {
  return ENABLE_BILLING
}

export function isClinicalBrainEnabled() {
  return ENABLE_CLINICAL_BRAIN
}

export function isReportBuilderEnabled() {
  return ENABLE_REPORT_BUILDER
}
