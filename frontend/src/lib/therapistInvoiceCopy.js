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

export function lineDisplayAmount(line) {
  if (line?.display_amount_inr != null) return Number(line.display_amount_inr)
  return Number(line?.amount_inr || 0)
}

export function lineStatusTag(line) {
  if (line?.status_tag) return line.status_tag
  if (line?.flags?.pending_approval || line?.breakdown_bucket === 'pending') return 'Pending approval'
  if (line?.flags?.pending_reason) return line.flags.pending_reason
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
        String(line.ui_label || '').includes('not billed'))
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
  if (approved > 0) parts.push(`${approved} in this pay`)
  if (pending > 0) {
    parts.push(
      `${pending} waiting on review (${formatInr(data.pending_approval_inr ?? data.pending_late_inr)})`,
    )
  }
  const paid = summary.paid_leaves ?? 0
  const unpaid = summary.unpaid_leaves ?? 0
  if (paid > 0 || unpaid > 0) {
    const leaveBits = []
    if (paid > 0) leaveBits.push(`${paid} paid leave (no deduction)`)
    if (unpaid > 0) leaveBits.push(`${unpaid} unpaid (−${formatInr(data.leave_deduction_inr)})`)
    parts.push(leaveBits.join(' · '))
  }
  return parts.length ? parts.join(' · ') : null
}
