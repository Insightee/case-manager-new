import { formatInr } from '../components/invoices/invoiceUtils.js'

/** Therapist-facing invoice copy and summary helpers. */

export function isHomecareCaseGroup(caseGroup) {
  const mod = String(
    caseGroup?.product_module ||
      caseGroup?.billing?.product_module ||
      caseGroup?.billing_snapshot?.product_module ||
      '',
  ).toLowerCase()
  return mod.includes('homecare')
}

export function isCounsellingCaseGroup(caseGroup) {
  const mod = String(
    caseGroup?.product_module ||
      caseGroup?.billing?.product_module ||
      caseGroup?.billing_snapshot?.product_module ||
      caseGroup?.service_type ||
      caseGroup?.billing?.service_type ||
      '',
  ).toLowerCase()
  return mod.includes('counsel')
}

export function isShadowCaseGroup(caseGroup) {
  const mod = String(
    caseGroup?.product_module ||
      caseGroup?.billing?.product_module ||
      caseGroup?.billing_snapshot?.product_module ||
      '',
  ).toLowerCase()
  if (mod.includes('shadow') || mod.includes('b2b')) return true
  return caseGroup?.billing_profile === 'calendar_day'
}

/** Homecare package/per-session except counselling — next-month session count UI. */
export function showNextMonthSessionCount(caseGroup) {
  if (!isHomecareCaseGroup(caseGroup) || isCounsellingCaseGroup(caseGroup)) return false
  const bt = String(
    caseGroup?.billing?.billing_type ||
      caseGroup?.billing_snapshot?.billing_type ||
      caseGroup?.billing_type ||
      '',
  ).toUpperCase()
  return bt === 'PACKAGE' || bt === 'PER_SESSION' || !bt
}

export function nextMonthSessionCount(plan) {
  if (!plan || typeof plan !== 'object') return 0
  if (plan.session_count != null) return Math.max(0, Number(plan.session_count) || 0)
  if (Array.isArray(plan.sessions)) return plan.sessions.length
  return 0
}

export function lineDisplayAmount(line) {
  if (line?.display_amount_inr != null) return Number(line.display_amount_inr)
  return Number(line?.amount_inr || 0)
}

/** Only Pending chips — no Still paid / Not billed / Deducted tags. */
export function lineStatusTag(line) {
  if (line?.breakdown_bucket === 'pending' || line?.flags?.pending_approval) {
    return line?.status_tag === 'Pending' || line?.status_tag === 'Pending approval'
      ? 'Pending'
      : line?.status_tag || 'Pending'
  }
  return null
}

/** Split case lines into therapist buckets — never treat info/cancelled as pending. */
export function partitionCaseLines(caseGroup) {
  const pending = []
  const inPay = []
  const info = []

  const pushLine = (line) => {
    if (!line) return
    const bucket = line.breakdown_bucket
    if (
      line.flags?.needs_disposition ||
      line.line_kind === 'SESSION_CANCELLED_UNEXPLAINED' ||
      line.line_kind === 'ATTENDANCE_NEEDS_DISPOSITION'
    ) {
      pending.push(line)
      return
    }
    if (bucket === 'pending' || line.flags?.pending_approval) {
      pending.push(line)
      return
    }
    if (bucket === 'info') {
      info.push(line)
      return
    }
    if (bucket === 'in_pay') {
      inPay.push(line)
      return
    }
    if (line.included === false && (line.flags?.pending_approval || line.pending_reason)) {
      pending.push(line)
      return
    }
    if (
      line.included === false &&
      (line.line_kind === 'CHILD_AWAY' ||
        line.line_kind === 'LEAVE_CANCELLED' ||
        String(line.ui_label || '').toLowerCase().includes('cancelled'))
    ) {
      info.push(line)
      return
    }
    if (line.included !== false) {
      inPay.push(line)
      return
    }
    info.push(line)
  }

  for (const line of caseGroup?.session_lines || []) pushLine(line)
  for (const line of caseGroup?.pending_approval_lines || caseGroup?.pending_late_lines || []) {
    pushLine({
      ...line,
      breakdown_bucket: line.breakdown_bucket || 'pending',
      flags: { ...(line.flags || {}), pending_approval: true },
    })
  }
  for (const line of caseGroup?.child_absence_lines || []) pushLine(line)
  for (const line of caseGroup?.leave_lines || []) pushLine(line)

  const sortKey = (l) => l.session_date || ''
  inPay.sort((a, b) => sortKey(a).localeCompare(sortKey(b)))
  pending.sort((a, b) => sortKey(a).localeCompare(sortKey(b)))
  info.sort((a, b) => sortKey(a).localeCompare(sortKey(b)))
  return { inPay, pending, info }
}

export function formatTherapistHeaderSummary(data) {
  if (!data) return null
  const summary = data.attendance_summary || {}
  const parts = []
  const approved = summary.approved_sessions ?? data.total_sessions ?? 0
  const pending = data.pending_approval_count ?? summary.pending_sessions ?? 0
  const unresolved = data.unresolved_attendance_count ?? data.unresolved_attendance_days?.length ?? 0
  if (approved > 0) parts.push(`${approved} in this pay`)
  if (pending > 0) {
    parts.push(
      `${pending} waiting on review (${formatInr(data.pending_approval_inr ?? data.pending_late_inr)})`,
    )
  }
  if (unresolved > 0) {
    parts.push(`${unresolved} need a log or absence`)
  }
  const paid = summary.paid_leaves ?? 0
  const unpaid = summary.unpaid_leaves ?? 0
  if (paid > 0 || unpaid > 0) {
    const leaveBits = []
    if (paid > 0) leaveBits.push(`${paid} paid leave`)
    if (unpaid > 0) leaveBits.push(`${unpaid} unpaid (−${formatInr(data.leave_deduction_inr)})`)
    parts.push(leaveBits.join(' · '))
  }
  return parts.length ? parts.join(' · ') : null
}
