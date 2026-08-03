/**
 * Production-safe module gates. Unset env vars default to OFF on production Vercel.
 * Local dev + Vercel preview / staging hosts enable modules when flags are set.
 */

/** True for npm run dev, Vercel preview URLs, and VITE_APP_ENV=staging. */
export function isRolloutEnvironment() {
  if (import.meta.env.DEV) return true

  const appEnv = String(import.meta.env.VITE_APP_ENV || '').toLowerCase()
  if (['staging', 'testing', 'development', 'local', 'preview'].includes(appEnv)) {
    return true
  }

  const vercelEnv = String(import.meta.env.VITE_VERCEL_ENV || import.meta.env.VERCEL_ENV || '').toLowerCase()
  if (vercelEnv === 'preview' || vercelEnv === 'development') {
    return true
  }

  if (typeof window !== 'undefined') {
    const host = window.location.hostname
    if (/\.vercel\.app$/i.test(host) && !/insighte\.org$/i.test(host)) {
      return true
    }
  }

  return false
}

/**
 * Canonical production UI (insighte.org or Vercel Production build).
 * Reports + billing stay off here even if VITE_ENABLE_* is set on Production env.
 */
export function isCanonicalProductionFrontend() {
  if (import.meta.env.DEV) return false

  const appEnv = String(import.meta.env.VITE_APP_ENV || '').toLowerCase()
  if (['staging', 'testing', 'development', 'local', 'preview'].includes(appEnv)) {
    return false
  }
  if (appEnv === 'production') return true

  const vercelEnv = String(import.meta.env.VITE_VERCEL_ENV || import.meta.env.VERCEL_ENV || '').toLowerCase()
  if (vercelEnv === 'production') return true
  if (vercelEnv === 'preview' || vercelEnv === 'development') return false

  if (typeof window !== 'undefined') {
    const host = window.location.hostname
    if (/insighte\.org$/i.test(host)) return true
  }

  return false
}

function readEnvFlag(key, { rolloutDefault = false } = {}) {
  const raw = import.meta.env[key]
  if (raw === 'true') return true
  if (raw === 'false') return false
  return rolloutDefault && isRolloutEnvironment()
}

/** Therapist/parent reports — off on canonical production. */
function readClientModuleFlag(key) {
  if (isCanonicalProductionFrontend()) return false
  return readEnvFlag(key, { rolloutDefault: false })
}

/** Monthly reports hub, parent reports, admin report review UI */
export const ENABLE_REPORTS = readClientModuleFlag('VITE_ENABLE_REPORTS')

/** Therapist invoices, admin client billing / ledger composer */
export const ENABLE_BILLING = readClientModuleFlag('VITE_ENABLE_BILLING')

/** Goal bank, strategy pool, review queue, clinical AI assist */
export const ENABLE_CLINICAL_BRAIN = readEnvFlag('VITE_ENABLE_CLINICAL_BRAIN')

/** Observation / IEP / monthly report builder routes */
export const ENABLE_REPORT_BUILDER = readEnvFlag('VITE_ENABLE_REPORT_BUILDER', { rolloutDefault: false })

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
