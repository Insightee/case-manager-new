/** Paths for IEP / observation landing, builder, and preview across portals. */

export function therapistClinicalReportPath(caseId, kind, view = 'landing') {
  const base = `/therapist/reports/cases/${caseId}/${kind}`
  if (!view || view === 'landing') return base
  return `${base}?view=${encodeURIComponent(view)}`
}

export function clinicalReportNavBase({ caseId, variant = 'therapist', portal = null }) {
  if (variant === 'admin' || portal === 'admin') {
    return `/admin/cases/${caseId}`
  }
  if (variant === 'parent' || portal === 'parent') {
    return `/parent/cases/${caseId}`
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
  const resolved = portal || variant
  if (resolved === 'admin') {
    const tab = section === 'observation' ? 'observation' : section === 'iep' ? 'iep' : 'reports'
    const params = new URLSearchParams({ tab })
    if (view && view !== 'landing') params.set('view', view)
    return `/admin/cases/${caseId}?${params.toString()}`
  }
  if (resolved === 'parent') {
    const tab = section === 'observation' ? 'observation' : 'iep'
    const params = new URLSearchParams({ tab })
    if (view && view !== 'landing') params.set('view', view)
    return `/parent/cases/${caseId}?${params.toString()}`
  }
  return therapistClinicalReportPath(caseId, section, view)
}
