export const LEAVE_CATEGORIES = [
  { value: 'PAID', label: 'Monthly leave' },
  { value: 'CARRY_FORWARD', label: 'Carry forward' },
  { value: 'UNPAID', label: 'Unpaid' },
]

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
