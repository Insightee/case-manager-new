/** @param {Record<string, unknown> | null | undefined} balance */
export function isLeaveBalanceUpdated(balance) {
  return Boolean(balance?.balance_updated)
}

/** @param {Record<string, unknown> | null | undefined} balance */
export function leaveBalanceRemainingLabel(balance) {
  if (!balance) return '—'
  if (!isLeaveBalanceUpdated(balance)) return '—'
  return `${balance.paid_remaining} / ${balance.entitlement_paid}`
}

/** @param {Record<string, unknown> | null | undefined} balance */
export function leaveBalancePaidRemainingLabel(balance) {
  if (!balance || !isLeaveBalanceUpdated(balance)) return '—'
  return String(balance.paid_remaining)
}
