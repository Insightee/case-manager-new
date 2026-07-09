/**
 * Monthly report API — single frontend bridge for legacy and clinical engine paths.
 * Default: legacy (VITE_MONTHLY_REPORTS_USE_CLINICAL_ENGINE=false).
 */

import { apiFetch, apiDownload, apiUpload } from './apiClient.js'
import { unwrapList } from './listApi.js'
import { isMonthlyClinicalEngineActive } from './reportsRevampFlags.js'

export function monthlyApiMode() {
  return isMonthlyClinicalEngineActive() ? 'clinical_engine' : 'legacy'
}

export async function listMonthlyReports({ caseId, status, pageSize = 100 } = {}) {
  if (isMonthlyClinicalEngineActive() && caseId) {
    const data = await apiFetch(`/api/v1/cases/${caseId}/reports`)
    const items = (data?.items || []).filter((r) => r.report_type === 'monthly')
    return items.map((r) => ({
      id: r.id,
      case_id: caseId,
      month: r.title?.match(/—\s*(\S+\s+\d{4})/)?.[1] || '',
      status: _mapEngineStatusToLegacy(r.status),
      category: 'CLIENT_MONTHLY',
      summary: null,
      updated_at: r.updated_at,
    }))
  }
  const qs = new URLSearchParams({ page_size: String(pageSize) })
  if (status) qs.set('status', status)
  const rows = await apiFetch(`/api/v1/reports/monthly?${qs}`)
  const list = unwrapList(rows)
  return caseId ? list.filter((r) => r.case_id === Number(caseId)) : list
}

function _mapEngineStatusToLegacy(status) {
  const map = {
    DRAFT: 'DRAFT',
    IN_PROGRESS: 'DRAFT',
    SUBMITTED_FOR_REVIEW: 'UNDER_REVIEW',
    RETURNED_FOR_CHANGES: 'REJECTED',
    APPROVED: 'APPROVED',
    LOCKED: 'PUBLISHED',
    ARCHIVED: 'APPROVED',
  }
  return map[status] || status
}

export async function createMonthlyDraft({ caseId, month, category = 'CLIENT_MONTHLY' }) {
  if (isMonthlyClinicalEngineActive()) {
    const qs = new URLSearchParams({ month })
    return apiFetch(`/api/v1/cases/${caseId}/reports/monthly/start?${qs}`, { method: 'POST' })
  }
  return apiFetch('/api/v1/reports/monthly', {
    method: 'POST',
    body: JSON.stringify({ case_id: caseId, month, category }),
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

export async function saveMonthlyReport({
  reportId,
  bodyHtml,
  planNextMonth,
  category,
  subCategory,
  month,
  isAdmin = false,
}) {
  const patchUrl = isAdmin
    ? `/api/v1/admin/reports/monthly/${reportId}`
    : `/api/v1/reports/monthly/${reportId}`
  return apiFetch(patchUrl, {
    method: 'PATCH',
    body: JSON.stringify({
      body_html: bodyHtml,
      plan_next_month: planNextMonth,
      category,
      sub_category: category === 'PROGRESS' ? subCategory || null : null,
      month,
    }),
  })
}

export async function submitMonthlyReport(reportId) {
  if (isMonthlyClinicalEngineActive()) {
    return apiFetch(`/api/v1/reports/${reportId}/submit`, { method: 'POST' })
  }
  return apiFetch(`/api/v1/reports/monthly/${reportId}/submit`, { method: 'POST' })
}

export async function downloadMonthlyReport(reportId, filename) {
  if (isMonthlyClinicalEngineActive()) {
    return apiDownload(`/api/v1/reports/${reportId}/export`, filename)
  }
  return apiDownload(`/api/v1/reports/monthly/${reportId}/download`, filename)
}

export async function fetchMonthlySessionContext(reportId) {
  if (isMonthlyClinicalEngineActive()) {
    return apiFetch(`/api/v1/reports/${reportId}/session-context`).catch(() => [])
  }
  return apiFetch(`/api/v1/reports/monthly/${reportId}/session-context`)
}

export async function fetchMonthlyIepContext(caseId) {
  return apiFetch(`/api/v1/reports/monthly/iep-context?case_id=${caseId}`)
}

export async function fetchMonthlyParentPreview(reportId) {
  if (isMonthlyClinicalEngineActive()) {
    return apiFetch(`/api/v1/reports/${reportId}/parent-preview`)
  }
  return apiFetch(`/api/v1/reports/monthly/${reportId}/parent-preview`)
}

export function monthlyParentPreviewDownloadUrl(reportId) {
  if (isMonthlyClinicalEngineActive()) {
    return `/api/v1/reports/${reportId}/export`
  }
  return `/api/v1/reports/monthly/${reportId}/download`
}

export async function generateMonthlyFromLogs(reportId, mode = 'replace') {
  return apiFetch(`/api/v1/reports/monthly/${reportId}/generate-from-logs`, {
    method: 'POST',
    body: JSON.stringify({ mode }),
  })
}

export async function resendMonthlyToParent(reportId) {
  return apiFetch(`/api/v1/reports/monthly/${reportId}/resend-to-parent`, { method: 'POST' })
}

export async function approveMonthlyReport(reportId, body = {}) {
  return apiFetch(`/api/v1/reports/monthly/${reportId}/approve`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function rejectMonthlyReport(reportId, body) {
  return apiFetch(`/api/v1/reports/monthly/${reportId}/reject`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function uploadMonthlyReportImage(reportId, formData) {
  return apiUpload(`/api/v1/reports/monthly/${reportId}/images`, formData)
}

export async function insertMonthlyInsightsSnapshot(reportId, body) {
  return apiFetch(`/api/v1/reports/monthly/${reportId}/insights/insert-snapshot-section`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
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
