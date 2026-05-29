export function isInvoiceAmendable(apiStatus) {
  return apiStatus === 'IN_REVIEW' || apiStatus === 'QUERIED' || apiStatus === 'REJECTED' || apiStatus === 'DRAFT'
}

export function applyLocalExcludes(preview, excludeIds) {
  if (!preview) return preview
  const exclude = new Set(excludeIds)
  const next = structuredClone(preview)
  let subtotal = 0
  let totalSessions = 0
  for (const cg of next.cases || []) {
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
    cg.therapist_share_inr = Math.round(caseTotal * 100) / 100
    cg.included_sessions = included
    cg.additional_sessions = additional
    if (cg.billing?.billing_type === 'PER_SESSION' || cg.billing_snapshot?.billing_type === 'PER_SESSION') {
      cg.display_included_sessions = cg.session_lines?.filter((l) => l.included !== false).length ?? 0
    }
    subtotal += cg.therapist_share_inr
  }
  next.subtotal_inr = Math.round(subtotal * 100) / 100
  next.total_sessions = totalSessions
  next.net_amount_inr = Math.max(next.subtotal_inr - (next.leave_deduction_inr || 0), 0)
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

export function billingSummary(b) {
  if (!b?.billing_type) return 'Billing not configured'
  if (b.billing_type === 'PER_SESSION') {
    return `₹${b.client_rate_per_session_inr}/session · ${b.pay_share_pct}% therapist share`
  }
  if (b.compensation_mode === 'FIXED_LUMP') {
    return `Package ${b.package_session_count} sessions · ₹${b.therapist_fixed_pay_inr} fixed pay`
  }
  return `Package ${b.package_session_count} sessions · ₹${b.package_amount_inr} · ${b.pay_share_pct}% share`
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
