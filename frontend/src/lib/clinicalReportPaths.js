/** Therapist standalone clinical report routes (reports hub carve — not case profile v2). */

export function therapistClinicalReportPath(caseId, kind, view = 'landing') {
  const base = `/therapist/reports/cases/${caseId}/${kind}`
  if (!view || view === 'landing') return base
  return `${base}?view=${encodeURIComponent(view)}`
}

/**
 * Base path for in-builder navigation (logs/documents links vs report views).
 * Admin case profile uses tab query params; therapist uses reports/cases routes.
 */
export function clinicalReportNavBase({ caseId, variant = 'therapist', portal = null }) {
  if (variant === 'admin' || portal === 'admin') {
    return `/admin/cases/${caseId}`
  }
  return `/therapist/cases/${caseId}`
}

export function clinicalReportSectionPath({
  caseId,
  section,
  view = 'landing',
  variant = 'therapist',
  portal = null,
}) {
  if (variant === 'admin' || portal === 'admin') {
    const params = new URLSearchParams({ tab: 'reports', section })
    if (view && view !== 'landing') params.set('view', view)
    return `/admin/cases/${caseId}?${params.toString()}`
  }
  return therapistClinicalReportPath(caseId, section, view)
}
