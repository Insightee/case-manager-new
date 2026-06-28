/**
 * Monthly report API wrappers — route to clinical_reports engine or legacy stack.
 * Default: legacy (MONTHLY_REPORTS_USE_CLINICAL_ENGINE=false).
 */

import { apiFetch } from './apiClient.js'
import { isMonthlyClinicalEngineActive } from './reportsRevampFlags.js'

export function monthlyApiMode() {
  return isMonthlyClinicalEngineActive() ? 'clinical_engine' : 'legacy'
}

export async function createMonthlyDraft({ caseId, month }) {
  if (isMonthlyClinicalEngineActive()) {
    const qs = new URLSearchParams({ month })
    return apiFetch(`/api/v1/cases/${caseId}/reports/monthly/start?${qs}`, { method: 'POST' })
  }
  return apiFetch('/api/v1/reports/monthly', {
    method: 'POST',
    body: JSON.stringify({ case_id: caseId, month }),
  })
}

export async function fetchMonthlyReport({ caseId, month, reportId }) {
  if (isMonthlyClinicalEngineActive() && caseId && month) {
    const qs = new URLSearchParams({ month })
    return apiFetch(`/api/v1/cases/${caseId}/reports/monthly?${qs}`)
  }
  if (isMonthlyClinicalEngineActive() && reportId) {
    return apiFetch(`/api/v1/reports/${reportId}`)
  }
  return apiFetch(`/api/v1/reports/monthly/${reportId}`)
}

export async function submitMonthlyReport(reportId) {
  if (isMonthlyClinicalEngineActive()) {
    return apiFetch(`/api/v1/reports/${reportId}/submit`, { method: 'POST' })
  }
  return apiFetch(`/api/v1/reports/monthly/${reportId}/submit`, { method: 'POST' })
}

export async function populateMonthlyFromEvidence(reportId) {
  return apiFetch(`/api/v1/reports/${reportId}/monthly/populate-from-evidence`, { method: 'POST' })
}

export async function compileMonthlyEvidence(reportId, force = false) {
  const qs = force ? '?force=true' : ''
  return apiFetch(`/api/v1/reports/${reportId}/monthly/compile-evidence${qs}`, { method: 'POST' })
}

export async function fetchMonthlyEvidenceSnapshot(reportId) {
  return apiFetch(`/api/v1/reports/${reportId}/evidence-snapshot`)
}

export async function fetchIepEvidenceReview(caseId, iepPlanId) {
  const qs = iepPlanId ? `?iep_plan_id=${iepPlanId}` : ''
  return apiFetch(`/api/v1/clinical-brain/cases/${caseId}/iep-evidence-review${qs}`)
}

export async function sendIepSuggestionToReview(suggestionId) {
  return apiFetch(`/api/v1/clinical-brain/iep-review-suggestions/${suggestionId}/send-to-review`, {
    method: 'POST',
  })
}

export async function improveSessionNoteClinicalAi(body) {
  return apiFetch('/api/v1/clinical-ai/session-note/improve', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function draftMonthlySectionClinicalAi(reportId, body) {
  return apiFetch(`/api/v1/clinical-ai/monthly-report/${reportId}/draft-section`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

