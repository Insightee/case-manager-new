/** Labels and helpers for shadow/B2B half-day vs full-day cases. */

export const DAY_TYPE_LABELS = {
  HALF_DAY: 'Half day',
  FULL_DAY: 'Full day',
}

export const DAY_TYPE_MODULES = new Set(['shadow_support', 'b2b'])

export function productRequiresDayType(productModule) {
  return DAY_TYPE_MODULES.has(productModule)
}

export function dayTypeLabel(dayType) {
  if (!dayType) return null
  return DAY_TYPE_LABELS[dayType] || String(dayType).replaceAll('_', ' ').toLowerCase()
}

export function dayTypeBadgeClass(dayType) {
  if (dayType === 'HALF_DAY') return 'admin-badge admin-badge--warning'
  if (dayType === 'FULL_DAY') return 'admin-badge admin-badge--info'
  return 'admin-chip'
}

export const REASSIGNMENT_REASON_MIN = 5

export function isDayTypeChangeReasonValid(reason) {
  return String(reason || '').trim().length >= REASSIGNMENT_REASON_MIN
}
