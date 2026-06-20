import { isLeaveBalanceUpdated } from './leaveBalanceDisplay.js'

export const LEAVE_CATEGORIES = [
  { value: 'PAID', label: 'Paid leave' },
  { value: 'CARRY_FORWARD', label: 'Carry forward' },
  { value: 'UNPAID', label: 'Unpaid' },
]

/** @param {{ value: string, label: string }} category @param {Record<string, unknown> | null | undefined} balance */
export function leaveCategoryOptionLabel(category, balance) {
  if (category.value !== 'PAID') return category.label
  if (!balance || !isLeaveBalanceUpdated(balance)) {
    return `${category.label} (credit balance pending HR update)`
  }
  const remaining = balance.paid_remaining ?? 0
  const total = balance.entitlement_paid ?? 0
  return `${category.label} (${remaining} of ${total} remaining)`
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
  if (!value) return '—'
  return String(value).replaceAll('_', ' ')
}
