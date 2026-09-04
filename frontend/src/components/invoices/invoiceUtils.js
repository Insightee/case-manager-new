import { CONFIDENCE_LEVELS } from '../../lib/financeConfidence.js'

function usesCalendarDayPay(caseGroup) {
  const mod = String(caseGroup?.billing?.product_module || caseGroup?.billing_snapshot?.product_module || '')
    .toLowerCase()
  return mod.includes('shadow') || mod.includes('b2b')
}

export function isInvoiceAmendable(apiStatus) {
  return apiStatus === 'IN_REVIEW' || apiStatus === 'QUERIED' || apiStatus === 'REJECTED' || apiStatus === 'DRAFT'
}

export function formatModalHeaderSummary(attendanceSummary) {
  if (!attendanceSummary) return null
  const parts = []
  const approved = attendanceSummary.approved_sessions ?? 0
  const pending = attendanceSummary.pending_sessions ?? 0
  const billableAbsence = attendanceSummary.billable_absence ?? 0
  if (approved > 0) parts.push(`${approved} in this pay`)
  if (pending > 0) parts.push(`${pending} waiting on review`)
  if (billableAbsence > 0) parts.push(`${billableAbsence} session cancelled`)
  if (attendanceSummary.leave_taken != null && attendanceSummary.leave_taken > 0) {
    parts.push(`${attendanceSummary.leave_taken} session cancelled`)
  } else {
    const paid = attendanceSummary.paid_leaves ?? 0
    const unpaid = attendanceSummary.unpaid_leaves ?? 0
    if (paid > 0 || unpaid > 0) {
      const bits = []
      if (paid > 0) bits.push(`${paid} paid leave`)
      if (unpaid > 0) bits.push(`${unpaid} unpaid leave`)
      parts.push(bits.join(' · '))
    }
  }
  return parts.length ? parts.join(' · ') : null
}

export function formatCaseAttendanceStrip(attendance, billingProfile) {
  if (!attendance) return null
  const parts = []
  if ((attendance.approved_sessions ?? 0) > 0) parts.push(`${attendance.approved_sessions} sessions in pay`)
  if ((attendance.pending_sessions ?? 0) > 0) parts.push(`${attendance.pending_sessions} waiting on review`)
  if (billingProfile === 'calendar_day') {
    if ((attendance.billable_absence ?? 0) > 0 || (attendance.pending_absence ?? 0) > 0) {
      const away = (attendance.billable_absence ?? 0) + (attendance.pending_absence ?? 0)
      parts.push(`${away} child away`)
    }
    if ((attendance.paid_leaves ?? 0) > 0) parts.push(`${attendance.paid_leaves} paid leave`)
    if ((attendance.unpaid_leaves ?? 0) > 0) parts.push(`${attendance.unpaid_leaves} unpaid leave`)
  } else {
    if ((attendance.pending_absence ?? 0) > 0) parts.push(`${attendance.pending_absence} child away waiting review`)
    if ((attendance.leave_taken ?? 0) > 0) parts.push(`${attendance.leave_taken} cancelled for leave`)
  }
  return parts.length ? parts.join(' · ') : null
}

export function applyLocalExcludes(preview, excludeIds) {
  if (!preview) return preview
  const exclude = new Set(excludeIds)
  const next = structuredClone(preview)
  const staticLeave = next.leave_deduction_inr || 0
  let subtotal = 0
  let totalSessions = 0
  for (const cg of next.cases || []) {
    const calendarPay = usesCalendarDayPay(cg)
    const originalGross = cg.therapist_share_inr || 0
    let caseTotal = 0
    let included = 0
    let additional = 0
    for (const line of cg.session_lines || []) {
      if (line.session_id && exclude.has(line.session_id)) {
        line.included = false
      }
      if (line.included !== false) {
        caseTotal += line.amount_inr || 0
        totalSessions += 1
        if (line.line_type === 'ADDITIONAL') additional += 1
        else if (line.line_type === 'INCLUDED') included += 1
      }
    }
    const absenceTotal = (cg.child_absence_lines || [])
      .filter((l) => l.included)
      .reduce((sum, l) => sum + (l.amount_inr || 0), 0)
    caseTotal += absenceTotal
    cg.therapist_share_inr = calendarPay ? originalGross : Math.round(caseTotal * 100) / 100
    cg.included_sessions = included
    cg.additional_sessions = additional
    if (cg.billing?.billing_type === 'PER_SESSION' || cg.billing_snapshot?.billing_type === 'PER_SESSION') {
      cg.display_included_sessions = cg.session_lines?.filter((l) => l.included !== false).length ?? 0
    }
    subtotal += cg.therapist_share_inr
  }
  next.subtotal_inr = Math.round(subtotal * 100) / 100
  next.total_sessions = totalSessions
  next.leave_deduction_inr = staticLeave
  next.net_amount_inr = Math.max(next.subtotal_inr - staticLeave, 0)
  next.amount_inr = next.net_amount_inr
  return next
}

export function formatInr(n) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(n ?? 0)
}

export function monthDateBounds(month) {
  const m = month.trim()
  let year
  let monthNum
  if (m.length === 7 && m[4] === '-') {
    year = parseInt(m.slice(0, 4), 10)
    monthNum = parseInt(m.slice(5, 7), 10)
  } else {
    const dt = new Date(`${m} 1`)
    year = dt.getFullYear()
    monthNum = dt.getMonth() + 1
  }
  const lastDay = new Date(year, monthNum, 0).getDate()
  const pad = (n) => String(n).padStart(2, '0')
  return {
    min: `${year}-${pad(monthNum)}-01`,
    max: `${year}-${pad(monthNum)}-${pad(lastDay)}`,
  }
}

export function recentMonthOptions(count = 6) {
  const options = []
  const now = new Date()
  for (let i = 0; i < count; i += 1) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    options.push({
      id: `${y}-${m}`,
      label: d.toLocaleString('en-IN', { month: 'short', year: 'numeric' }),
      value: `${y}-${m}`,
    })
  }
  return options
}

export function lineTypeLabel(type) {
  const map = {
    INCLUDED: 'Included in package',
    ADDITIONAL: 'Extra session',
    PER_SESSION: 'Per session',
  }
  return map[type] || type
}

// Renders whatever pricing fields are present. Admin payloads carry the client
// figures (client rate / package amount) and see the full line; therapist
// payloads are redacted at the API boundary, so those parts drop out and the
// therapist only ever sees their own share — never client-side money.
export function billingSummary(b) {
  if (!b?.billing_type) return 'Billing not configured'
  const lump =
    (b.therapist_fixed_pay_inr != null && Number(b.therapist_fixed_pay_inr) > 0
      ? Number(b.therapist_fixed_pay_inr)
      : null) ??
    (b.pay_share_amount_inr != null ? Number(b.pay_share_amount_inr) : 0) ??
    0
  if (b.billing_type === 'PER_SESSION') {
    const clientPart =
      b.client_rate_per_session_inr != null ? `₹${b.client_rate_per_session_inr}/session · ` : ''
    return `${clientPart}₹${lump} therapist pay`
  }
  if (b.billing_type === 'MONTHLY_FIXED') {
    const clientPart =
      b.client_monthly_rate_inr != null ? `₹${b.client_monthly_rate_inr}/month · ` : ''
    return `${clientPart}₹${lump} therapist pay`
  }
  const clientPart = b.package_amount_inr != null ? `₹${b.package_amount_inr} · ` : ''
  return `Package ${b.package_session_count || '—'} sessions · ${clientPart}₹${lump} therapist pay`
}

// Deduction lines we intend to show but for which no rule is configured yet.
// Rendered as visible, labelled placeholders (no computed amount) so the layout
// is ready the moment finance supplies the rule.
export const STATEMENT_NOT_CONFIGURED = 'Not yet configured'

/**
 * Compose the therapist's monthly statement ladder purely from the payout
 * engine payload — the therapist enters nothing. Reads therapist-side figures
 * only (subtotal / leave / adjustment / net); never touches client pricing.
 * TDS, holdback and expected payment date are placeholders until finance
 * supplies the rules.
 */
export function statementLadder(data) {
  if (!data) return []
  const placeholder = (key, label) => ({
    key,
    label,
    kind: 'placeholder',
    amount: null,
    note: STATEMENT_NOT_CONFIGURED,
  })
  const rows = [{ key: 'gross', label: 'Gross earnings', kind: 'earning', amount: data.subtotal_inr ?? 0 }]

  const leave = data.leave_deduction_inr ?? 0
  if (leave > 0) {
    rows.push({ key: 'leave', label: 'Unpaid leave adjustment', kind: 'deduction', amount: leave })
  }
  if (data.adjustment_inr != null && data.adjustment_inr !== 0) {
    const adj = data.adjustment_inr
    rows.push({
      key: 'adjustment',
      label: 'Adjustment',
      kind: adj < 0 ? 'deduction' : 'earning',
      amount: Math.abs(adj),
    })
  }
  const tds = data.tds_inr ?? data.tdsInr
  if (tds != null) {
    rows.push({ key: 'tds', label: 'TDS', kind: 'deduction', amount: Number(tds) })
  } else {
    rows.push(placeholder('tds', 'TDS'))
  }
  rows.push(placeholder('holdback', 'Holdback'))
  rows.push({ key: 'net', label: 'Net payable', kind: 'net', amount: data.net_amount_inr ?? data.amount_inr ?? 0 })
  rows.push(placeholder('payment_date', 'Expected payment date'))
  return rows
}

/**
 * Confidence for a therapist statement. Pre-cutover everything is provisional —
 * the client may only ever downgrade, never invent RECONCILED.
 */
export function statementConfidence(data, { cutover = false } = {}) {
  if (!cutover) {
    return (data?.pending_late_count ?? 0) > 0
      ? CONFIDENCE_LEVELS.ESTIMATED
      : CONFIDENCE_LEVELS.PARTIAL
  }
  return CONFIDENCE_LEVELS.PARTIAL
}

export function mapInvoiceForCard(inv) {
  const amount = inv.amount_inr ?? 0
  const base = {
    id: inv.id,
    month: inv.month,
    amountINR: amount,
    sessions: inv.sessions_count ?? 0,
    apiStatus: inv.status,
  }
  if (inv.status === 'REJECTED' || inv.status === 'QUERIED') {
    return {
      ...base,
      status: inv.status === 'REJECTED' ? 'rejected' : 'queried',
      detail: inv.reviewer_comment || 'Finance requested changes',
      message: inv.status === 'REJECTED' ? 'Rejected' : 'Queried',
    }
  }
  if (inv.status === 'PAID') {
    return {
      ...base,
      paidDate: inv.month,
    }
  }
  return {
    ...base,
    subtitle: inv.notes || 'Submitted for finance review',
  }
}

export function computeSummaryFromInvoices(invoices) {
  const now = new Date()
  const currentLabel = now.toLocaleString('en-IN', { month: 'short', year: 'numeric' })
  const thisMonth = invoices.filter((i) => i.month === currentLabel)
  const paid = invoices.filter((i) => i.status === 'PAID')
  const pending = invoices.filter((i) => i.status === 'IN_REVIEW' || i.status === 'DRAFT' || i.status === 'APPROVED')
  const queried = invoices.filter((i) => i.status === 'QUERIED' || i.status === 'REJECTED')
  const sum = (arr) => arr.reduce((s, i) => s + (i.amount_inr || 0), 0)
  return {
    totalEarningsThisMonthINR: sum(thisMonth),
    pendingINR: sum(pending),
    paidINR: sum(paid),
    queriedINR: sum(queried),
    trends: null,
  }
}
