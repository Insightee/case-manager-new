const MONTH_ORDER = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function ledgerStatusKey(apiStatus) {
  const s = String(apiStatus || '').toUpperCase()
  if (s === 'PAID') return 'paid'
  if (s === 'QUERIED') return 'queried'
  if (s === 'REJECTED') return 'rejected'
  if (s === 'APPROVED') return 'approved'
  if (s === 'DRAFT') return 'draft'
  return 'in_review'
}

export function ledgerStatusLabel(apiStatus) {
  const key = ledgerStatusKey(apiStatus)
  const labels = {
    paid: 'Paid',
    queried: 'Queried',
    rejected: 'Rejected',
    approved: 'Approved',
    draft: 'Draft',
    in_review: 'In review',
  }
  return labels[key] || apiStatus || '—'
}

export function sortLedgerRows(rows) {
  return [...rows].sort((a, b) => {
    const ka = a.periodSortKey || a.month || ''
    const kb = b.periodSortKey || b.month || ''
    if (kb !== ka) return kb.localeCompare(ka)
    const da = new Date(a.createdAt || a.created_at || 0).getTime()
    const db = new Date(b.createdAt || b.created_at || 0).getTime()
    if (db !== da) return db - da
    return (b.id || 0) - (a.id || 0)
  })
}

export function applyLedgerFilters(rows, filters) {
  const { year = '', month = '', caseId = '', status = '' } = filters || {}
  return sortLedgerRows(rows).filter((row) => {
    if (year && String(row.periodYear || '') !== String(year)) return false
    if (month && row.periodMonth !== month) return false
    if (status && ledgerStatusKey(row.status) !== ledgerStatusKey(status)) return false
    if (caseId) {
      const cid = Number(caseId)
      const cases = row.cases || []
      if (!cases.some((c) => Number(c.caseId) === cid)) return false
    }
    return true
  })
}

export function earningsTrendFromLedger(rows, limit = 6) {
  const byPeriod = new Map()
  for (const row of rows) {
    const key = row.periodSortKey || row.month
    if (!key) continue
    const existing = byPeriod.get(key) || {
      month: row.month,
      periodSortKey: key,
      amountINR: 0,
    }
    existing.amountINR += Number(row.amountInr ?? row.amount_inr ?? 0)
    byPeriod.set(key, existing)
  }
  return [...byPeriod.values()]
    .sort((a, b) => String(a.periodSortKey).localeCompare(String(b.periodSortKey)))
    .slice(-limit)
}

export function defaultLedgerFilters() {
  return { year: '', month: '', caseId: '', status: '' }
}

export function monthOptionsFromFilters(filterOptions) {
  const months = filterOptions?.months || []
  return months.map((m) => ({ value: m, label: m }))
}

export function yearOptionsFromFilters(filterOptions) {
  const years = filterOptions?.years || []
  return years.map((y) => ({ value: String(y), label: String(y) }))
}

export function clientOptionsFromFilters(filterOptions) {
  return (filterOptions?.clients || []).map((c) => ({
    value: String(c.caseId),
    label: c.label,
  }))
}

export function statusOptionsFromFilters(filterOptions) {
  return (filterOptions?.statuses || []).map((s) => ({
    value: s,
    label: ledgerStatusLabel(s),
  }))
}

export function computeFilteredSummary(rows) {
  const gross = rows.reduce((s, r) => s + Number(r.subtotalInr ?? r.subtotal_inr ?? r.amountInr ?? r.amount_inr ?? 0), 0)
  const net = rows.reduce((s, r) => s + Number(r.amountInr ?? r.amount_inr ?? 0), 0)
  const paid = rows
    .filter((r) => ledgerStatusKey(r.status) === 'paid')
    .reduce((s, r) => s + Number(r.paidAmountInr ?? r.paid_amount_inr ?? r.amountInr ?? r.amount_inr ?? 0), 0)
  const pending = rows
    .filter((r) => ['in_review', 'approved', 'draft'].includes(ledgerStatusKey(r.status)))
    .reduce((s, r) => s + Number(r.amountInr ?? r.amount_inr ?? 0), 0)
  const sessions = rows.reduce((s, r) => s + Number(r.sessionsCount ?? r.sessions_count ?? 0), 0)
  return {
    rowCount: rows.length,
    sessionCount: sessions,
    grossInr: gross,
    netInr: net,
    paidInr: paid,
    pendingInr: pending,
  }
}

export function monthSortIndex(label) {
  const idx = MONTH_ORDER.indexOf(label)
  return idx === -1 ? 99 : idx
}
