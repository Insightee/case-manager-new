export const CLIENT_INVOICE_STATUSES = [
  'DRAFT',
  'GENERATED',
  'SENT',
  'PARTIALLY_PAID',
  'PAID',
  'DISPUTED',
  'CANCELLED',
  'OVERDUE',
]

export const INVOICE_TYPES = [
  { value: '', label: 'All types' },
  { value: 'POSTPAID', label: 'Postpaid' },
  { value: 'PREPAID', label: 'Prepaid' },
]

export function buildClientInvoiceQuery(filters) {
  const p = new URLSearchParams()
  if (filters.month) p.set('month', filters.month)
  else if (filters.year) p.set('year', String(filters.year))
  if (filters.dateFrom) p.set('date_from', filters.dateFrom)
  if (filters.dateTo) p.set('date_to', filters.dateTo)
  if (filters.status) p.set('status', filters.status)
  if (filters.invoiceType) p.set('invoice_type', filters.invoiceType)
  if (filters.module) p.set('module', filters.module)
  if (filters.search) p.set('search', filters.search)
  if (filters.caseId) p.set('case_id', filters.caseId)
  if (filters.claimsPending) p.set('claims_pending', 'true')
  const qs = p.toString()
  return qs ? `?${qs}` : ''
}

const CLIENT_FILTER_PARAM_KEYS = {
  year: 'year',
  month: 'month',
  dateFrom: 'date_from',
  dateTo: 'date_to',
  status: 'status',
  invoiceType: 'invoice_type',
  module: 'module',
  search: 'search',
}

export function parseClientInvoiceFilters(searchParams) {
  const sp = searchParams instanceof URLSearchParams ? searchParams : new URLSearchParams(searchParams)
  return {
    year: sp.get('year') || '',
    month: sp.get('month') || '',
    dateFrom: sp.get('date_from') || '',
    dateTo: sp.get('date_to') || '',
    status: sp.get('status') || '',
    invoiceType: sp.get('invoice_type') || '',
    module: sp.get('module') || '',
    search: sp.get('search') || '',
    claimsPending: sp.get('claims') === 'pending' || sp.get('claims_pending') === 'true',
  }
}

export function writeClientInvoiceFiltersToParams(baseParams, filters) {
  const next = new URLSearchParams(baseParams)
  for (const [key, param] of Object.entries(CLIENT_FILTER_PARAM_KEYS)) {
    const v = filters[key]
    if (v) next.set(param, String(v))
    else next.delete(param)
  }
  if (filters.claimsPending) next.set('claims', 'pending')
  else next.delete('claims')
  return next
}

export function parseTherapistInvoiceFilters(searchParams) {
  const sp = searchParams instanceof URLSearchParams ? searchParams : new URLSearchParams(searchParams)
  return {
    year: sp.get('year') || '',
    month: sp.get('month') || '',
    dateFrom: sp.get('date_from') || '',
    dateTo: sp.get('date_to') || '',
    status: sp.get('status') || 'ALL',
    search: sp.get('search') || '',
  }
}

export function writeTherapistInvoiceFiltersToParams(baseParams, filters) {
  const next = new URLSearchParams(baseParams)
  const keys = { year: 'year', month: 'month', dateFrom: 'date_from', dateTo: 'date_to', status: 'status', search: 'search' }
  for (const [key, param] of Object.entries(keys)) {
    const v = filters[key]
    if (v && !(key === 'status' && v === 'ALL')) next.set(param, String(v))
    else next.delete(param)
  }
  return next
}

export function buildTherapistInvoiceQuery(filters) {
  const p = new URLSearchParams()
  if (filters.status && filters.status !== 'ALL') p.set('status', filters.status)
  if (filters.year) p.set('year', String(filters.year))
  if (filters.month) p.set('month', filters.month)
  if (filters.dateFrom) p.set('date_from', filters.dateFrom)
  if (filters.dateTo) p.set('date_to', filters.dateTo)
  if (filters.search) p.set('search', filters.search)
  const qs = p.toString()
  return qs ? `?${qs}` : ''
}
