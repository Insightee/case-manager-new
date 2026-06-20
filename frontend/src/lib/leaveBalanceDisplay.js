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

/** @param {Record<string, unknown> | null | undefined} balance */
export function paidLeaveCreditHint(balance) {
  if (!balance) return null
  if (!isLeaveBalanceUpdated(balance)) {
    return 'Paid leave credit will show here once HR confirms your opening balance.'
  }
  const remaining = balance.paid_remaining ?? 0
  const total = balance.entitlement_paid ?? 0
  return `${remaining} paid leave day${remaining === 1 ? '' : 's'} remaining of ${total} this year.`
}
