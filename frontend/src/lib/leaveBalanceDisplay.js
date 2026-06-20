/** @param {Record<string, unknown> | null | undefined} balance */
export function isLeaveBalanceUpdated(balance) {
  return Boolean(balance?.balance_updated ?? balance?.employment_start_date)
}

/** @param {Record<string, unknown> | null | undefined} balance */
export function leaveCreditPendingLabel(balance) {
  if (!balance) return '—'
  if (!isLeaveBalanceUpdated(balance)) return '—'
  return String(balance.leave_credit_pending ?? balance.paid_remaining ?? 0)
}

/** @param {Record<string, unknown> | null | undefined} balance */
export function leaveBalanceRemainingLabel(balance) {
  return leaveCreditPendingLabel(balance)
}

/** @param {Record<string, unknown> | null | undefined} balance */
export function leaveBalancePaidRemainingLabel(balance) {
  return leaveCreditPendingLabel(balance)
}

/** @param {Record<string, unknown> | null | undefined} balance */
export function paidLeaveCreditHint(balance) {
  if (!balance) return null
  if (!isLeaveBalanceUpdated(balance)) {
    return 'Leave credits appear once your employment start date is on file.'
  }
  const remaining = balance.leave_credit_pending ?? balance.paid_remaining ?? 0
  const earned = balance.credits_earned ?? balance.entitlement_paid ?? 0
  return `${remaining} leave credit${remaining === 1 ? '' : 's'} available (${earned} earned this year).`
}

/** @param {Record<string, unknown> | null | undefined} balance */
export function leaveUsedSummaryLabel(balance) {
  if (!balance) return '—'
  const paid = balance.paid_leaves_taken ?? balance.computed_paid_used ?? 0
  const unpaid = balance.unpaid_leaves_taken ?? balance.computed_unpaid_days ?? 0
  return `${paid} paid · ${unpaid} unpaid`
}
