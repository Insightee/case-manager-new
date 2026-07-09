/**
 * Production-safe module gates. Unset env vars default to OFF on production Vercel.
 * Local dev + Vercel preview / staging hosts default reports ON unless explicitly false.
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

function readEnvFlag(key, { rolloutDefault = false } = {}) {
  const raw = import.meta.env[key]
  if (raw === 'true') return true
  if (raw === 'false') return false
  return rolloutDefault && isRolloutEnvironment()
}

/** Monthly reports hub, parent reports, admin report review UI */
export const ENABLE_REPORTS = readEnvFlag('VITE_ENABLE_REPORTS', { rolloutDefault: false })

/** Therapist invoices, admin client billing / ledger composer */
export const ENABLE_BILLING = readEnvFlag('VITE_ENABLE_BILLING')

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
