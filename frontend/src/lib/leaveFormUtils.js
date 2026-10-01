import { formatDisplayDate } from './datetime.js'
import { isLeaveBalanceUpdated } from './leaveBalanceDisplay.js'

export const LEAVE_CATEGORIES = [
  { value: 'PAID', label: 'Paid leave' },
  { value: 'UNPAID', label: 'Unpaid' },
]

/** @param {{ value: string, label: string }} category @param {Record<string, unknown> | null | undefined} balance */
export function leaveCategoryOptionLabel(category, balance) {
  if (category.value !== 'PAID') return category.label
  if (!balance || !isLeaveBalanceUpdated(balance)) {
    return `${category.label} (credits pending employment start date)`
  }
  const remaining = balance.leave_credit_pending ?? balance.paid_remaining ?? 0
  return `${category.label} (${remaining} credit${remaining === 1 ? '' : 's'} available)`
}

export function caseServiceLine(c) {
  const mod = (c?.product_module || c?.service_type || 'homecare').toLowerCase()
  return mod === 'shadow_support' ? 'shadow_support' : 'homecare'
}

export function caseLabel(c) {
  const name = c?.child_name || c?.child?.full_name
  const mod = caseServiceLine(c) === 'shadow_support' ? 'Shadow' : 'Homecare'
  return [name, c?.case_code, mod].filter(Boolean).join(' · ')
}

export function categoryLabel(value) {
  const row = LEAVE_CATEGORIES.find((c) => c.value === value)
  if (row) return row.label
  if (value === 'CARRY_FORWARD') return 'Carry forward'
  if (!value) return '—'
  return String(value).replaceAll('_', ' ')
}

export function formatLeaveDayAllocations(allocations) {
  if (!Array.isArray(allocations) || !allocations.length) return ''
  return allocations
    .map((row) => `${formatDisplayDate(row.date)} ${row.status === 'paid' ? 'paid' : 'unpaid'}`)
    .join(' · ')
}

export function formatLeaveSplitLabel(suggestion) {
  if (!suggestion) return ''
  if (suggestion.message) return suggestion.message
  const fromDays = formatLeaveDayAllocations(suggestion.day_allocations)
  if (fromDays) return fromDays
  const paid = suggestion.paid_days ?? 0
  const unpaid = suggestion.unpaid_days ?? 0
  if (paid && unpaid) return `${paid} paid leave + ${unpaid} unpaid leave`
  if (paid) return `${paid} paid leave day${paid === 1 ? '' : 's'}`
  if (unpaid) return `${unpaid} unpaid leave day${unpaid === 1 ? '' : 's'}`
  return ''
}

/** @param {{ paid_days?: number | null, unpaid_days?: number | null, billing_category?: string, leave_type?: string, day_allocations?: Array<{date?: string, status?: string}>, split_message?: string }} leave */
export function formatLeaveRecordSplit(leave) {
  if (!leave) return '—'
  const fromDays = formatLeaveDayAllocations(leave.day_allocations)
  if (fromDays) return fromDays
  if (leave.split_message) return leave.split_message
  if (leave.paid_days != null || leave.unpaid_days != null) {
    const paid = leave.paid_days ?? 0
    const unpaid = leave.unpaid_days ?? 0
    if (paid && unpaid) return `${paid} paid + ${unpaid} unpaid`
    if (paid) return `${paid} paid`
    if (unpaid) return `${unpaid} unpaid`
  }
  if (leave.billing_category) return categoryLabel(leave.billing_category)
  if (leave.leave_type) return categoryLabel(leave.leave_type)
  return '—'
}
