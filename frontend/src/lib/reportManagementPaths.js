/** Where to open full edit workspace from report management hub. */

export function isIepCategory(category) {
  return category === 'IEP_PLAN'
}

/**
 * @param {{ case_id: number, category?: string, report_type?: string, id?: number }} detail
 */
export function reportEditPath(detail, reportType) {
  if (!detail?.case_id) return '/admin/reports'
  if (isIepCategory(detail.category)) {
    return `/admin/cases/${detail.case_id}?tab=iep`
  }
  const type = reportType || detail.report_type
  if (type === 'observation') {
    return `/admin/cases/${detail.case_id}?tab=reports`
  }
  if (detail.id) {
    return `/admin/reports/edit/${detail.id}`
  }
  return `/admin/cases/${detail.case_id}?tab=reports`
}

export function reportModuleLabel(category, reportType) {
  if (isIepCategory(category)) return 'IEP management'
  if (reportType === 'observation') return 'Case reports'
  return 'Report editor'
}
