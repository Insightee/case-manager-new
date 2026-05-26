import { REPORTS_HUB_CATEGORIES } from './reportCategories.js'

/** Storage / API report type (monthly vs observation tables). */
export const REPORT_KIND_OPTIONS = [
  { value: 'all', label: 'All report types' },
  { value: 'monthly', label: 'Monthly reports' },
  { value: 'observation', label: 'Observation reports' },
]

export const IEP_CATEGORY_ID = 'IEP_PLAN'

export function reportKindLabel(value) {
  return REPORT_KIND_OPTIONS.find((o) => o.value === value)?.label || 'All report types'
}

export function reportCategoryOptions() {
  return [
    { value: '', label: 'All categories' },
    ...REPORTS_HUB_CATEGORIES.map((c) => ({ value: c.id, label: c.label })),
  ]
}
