import { apiFetch } from './apiClient.js'

/** Flatten and sort admin case pipeline board for table / queue views. */

export const PIPELINE_COLUMN_META = {
  pending_allotment: { label: 'Pending allotment', tone: 'slate', priority: 0 },
  needs_therapist: { label: 'Needs therapist', tone: 'warning', priority: 1 },
  reassignment: { label: 'Reassignment', tone: 'warning', priority: 2 },
  reports_logs: { label: 'Reports & logs', tone: 'danger', priority: 3 },
  compliance: { label: 'Compliance', tone: 'danger', priority: 4 },
  iep: { label: 'IEP', tone: 'purple', priority: 5 },
  active: { label: 'Active', tone: 'success', priority: 6 },
  closed: { label: 'Closed', tone: 'muted', priority: 7 },
}

/** Unified case state filter options (status + pipeline stage). */
export const CASE_STATE_OPTIONS = [
  { value: 'all', label: 'All states' },
  { value: 'status_active', label: 'Status: Active (in service)' },
  { value: 'pending_allotment', label: 'Pending allotment' },
  { value: 'needs_therapist', label: 'Needs therapist' },
  { value: 'reassignment', label: 'Reassignment' },
  { value: 'reports_logs', label: 'Reports & logs' },
  { value: 'iep', label: 'IEP' },
  { value: 'compliance', label: 'Compliance' },
  { value: 'pipeline_active', label: 'Active (no pending work)' },
  { value: 'closed', label: 'Closed' },
  { value: 'suspended', label: 'Suspended' },
]

export const OPENED_DATE_PRESETS = [
  { value: 'all', label: 'Any time' },
  { value: 'this_month', label: 'This month' },
  { value: 'last_30', label: 'Last 30 days' },
  { value: 'last_90', label: 'Last 90 days' },
  { value: 'custom', label: 'Custom range' },
]

/** Map legacy ?status= query params to unified caseState. */
const LEGACY_STATUS_TO_CASE_STATE = {
  PENDING_ALLOTMENT: 'pending_allotment',
  ACTIVE: 'status_active',
  SUSPENDED: 'suspended',
  CLOSED: 'closed',
}

/** Back-compat for saved links / bookmarks that used pipeline column value "active". */
const LEGACY_CASE_STATE_ALIASES = {
  active: 'pipeline_active',
}

const ACTIONABLE_COLUMNS = new Set([
  'pending_allotment',
  'needs_therapist',
  'reassignment',
  'reports_logs',
  'iep',
  'compliance',
])

export function flattenPipelineBoard(board) {
  if (!board?.columns) return []
  const rows = []
  for (const col of board.columns) {
    for (const card of col.cases || []) {
      rows.push({
        ...card,
        pipeline_column: card.pipeline_column || col.id,
        pipeline_label: PIPELINE_COLUMN_META[card.pipeline_column || col.id]?.label || col.title,
        pipeline_tone: PIPELINE_COLUMN_META[card.pipeline_column || col.id]?.tone || col.tone,
      })
    }
  }
  return rows
}

export function pipelinePriority(row) {
  return PIPELINE_COLUMN_META[row.pipeline_column]?.priority ?? 99
}

export function isPipelineActionRequired(row) {
  return ACTIONABLE_COLUMNS.has(row.pipeline_column) && row.pipeline_column !== 'active'
}

export function sortPipelineRows(rows, sort = 'priority') {
  const list = [...rows]
  if (sort === 'child') {
    return list.sort((a, b) => (a.child_name || '').localeCompare(b.child_name || ''))
  }
  if (sort === 'case') {
    return list.sort((a, b) => (a.case_code || '').localeCompare(b.case_code || ''))
  }
  return list.sort((a, b) => {
    const d = pipelinePriority(a) - pipelinePriority(b)
    if (d !== 0) return d
    return (a.case_code || '').localeCompare(b.case_code || '')
  })
}

const EMPTY_FILTERS = {
  queue: 'all',
  search: '',
  productModule: 'all',
  caseState: 'all',
  caseManagerId: 'all',
  therapistId: 'all',
  childId: 'all',
  openedPreset: 'all',
  openedMonth: 'all',
  openedYear: 'all',
  dateFrom: '',
  dateTo: '',
  operationalStage: 'all',
  unassignedCmOnly: false,
  unassignedTherapistOnly: false,
}

/** Month options for the opened-date filter (value is a zero-padded month number). */
export const OPENED_MONTH_OPTIONS = [
  { value: 'all', label: 'All months' },
  { value: '01', label: 'January' },
  { value: '02', label: 'February' },
  { value: '03', label: 'March' },
  { value: '04', label: 'April' },
  { value: '05', label: 'May' },
  { value: '06', label: 'June' },
  { value: '07', label: 'July' },
  { value: '08', label: 'August' },
  { value: '09', label: 'September' },
  { value: '10', label: 'October' },
  { value: '11', label: 'November' },
  { value: '12', label: 'December' },
]

/** Distinct opened years (from case created_at), newest first, for the year filter. */
export function deriveOpenedYearOptions(rows = []) {
  const years = new Set()
  for (const r of rows) {
    if (r.created_at) years.add(String(r.created_at).slice(0, 4))
  }
  return [
    { value: 'all', label: 'All years' },
    ...[...years]
      .filter(Boolean)
      .sort((a, b) => b.localeCompare(a))
      .map((y) => ({ value: y, label: y })),
  ]
}

export function normalizeCaseState(caseState) {
  if (!caseState || caseState === 'all') return 'all'
  return LEGACY_CASE_STATE_ALIASES[caseState] || caseState
}

export function defaultPipelineFilters(overrides = {}) {
  const merged = { ...EMPTY_FILTERS, ...overrides }
  merged.caseState = normalizeCaseState(merged.caseState)
  if (merged.caseStatus && merged.caseStatus !== 'all' && merged.caseState === 'all') {
    merged.caseState = LEGACY_STATUS_TO_CASE_STATE[merged.caseStatus] || 'all'
  }
  if (merged.pipelineStage && merged.pipelineStage !== 'all' && merged.caseState === 'all') {
    merged.caseState = normalizeCaseState(merged.pipelineStage)
  }
  if (merged.month && merged.month !== 'all' && merged.openedPreset === 'all') {
    merged.openedPreset = 'custom'
    if (!merged.dateFrom) merged.dateFrom = `${merged.month}-01`
    const [y, m] = merged.month.split('-').map(Number)
    const lastDay = new Date(y, m, 0).getDate()
    if (!merged.dateTo) merged.dateTo = `${merged.month}-${String(lastDay).padStart(2, '0')}`
  }
  delete merged.caseStatus
  delete merged.pipelineStage
  delete merged.month
  return merged
}

const STAFF_ROLES_BLOCKING_CM_ONLY = new Set([
  'SUPER_ADMIN',
  'MODULE_ADMIN',
  'FINANCE',
  'HR',
  'ADMIN',
])

/** True when the user should see only their own caseload by default (CM without broader staff roles). */
export function isCaseManagerOnlyRole(roles = []) {
  if (!roles.includes('CASE_MANAGER')) return false
  return !roles.some((r) => STAFF_ROLES_BLOCKING_CM_ONLY.has(r))
}

export function defaultCaseManagerFilterId(user) {
  if (!isCaseManagerOnlyRole(user?.roles || [])) return null
  return user?.id ? String(user.id) : null
}

export function caseStateFromLegacyStatus(status) {
  if (!status) return 'all'
  return LEGACY_STATUS_TO_CASE_STATE[status] || 'all'
}

export function matchesCaseState(row, caseState) {
  const state = normalizeCaseState(caseState)
  if (state === 'all') return true
  if (state === 'status_active') return row.status === 'ACTIVE'
  if (state === 'suspended') return row.status === 'SUSPENDED'
  if (state === 'closed') {
    return row.pipeline_column === 'closed' || row.status === 'CLOSED'
  }
  if (state === 'pending_allotment') {
    return row.pipeline_column === 'pending_allotment' || row.status === 'PENDING_ALLOTMENT'
  }
  if (state === 'pipeline_active') return row.pipeline_column === 'active'
  return row.pipeline_column === state
}

function isoDay(d) {
  return d.toISOString().slice(0, 10)
}

function openedDateBounds(preset, dateFrom, dateTo) {
  if (preset === 'all') return { from: null, to: null }
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  if (preset === 'this_month') {
    const start = new Date(today.getFullYear(), today.getMonth(), 1)
    return { from: isoDay(start), to: isoDay(today) }
  }
  if (preset === 'last_30') {
    const start = new Date(today)
    start.setDate(start.getDate() - 30)
    return { from: isoDay(start), to: isoDay(today) }
  }
  if (preset === 'last_90') {
    const start = new Date(today)
    start.setDate(start.getDate() - 90)
    return { from: isoDay(start), to: isoDay(today) }
  }
  if (preset === 'custom') {
    return { from: dateFrom || null, to: dateTo || null }
  }
  return { from: null, to: null }
}

/** @param {ReturnType<typeof flattenPipelineBoard>} rows */
export function derivePipelineFilterOptions(rows) {
  const therapists = new Map()
  const caseManagers = new Map()
  const children = new Map()
  const stages = new Set()
  for (const r of rows) {
    if (r.therapist_user_id) {
      therapists.set(r.therapist_user_id, r.therapist_name || `Therapist #${r.therapist_user_id}`)
    }
    if (r.case_manager_user_id) {
      caseManagers.set(r.case_manager_user_id, r.case_manager_name || `CM #${r.case_manager_user_id}`)
    }
    if (r.child_id) {
      children.set(r.child_id, r.child_name || `Client #${r.child_id}`)
    }
    if (r.operational_stage) stages.add(r.operational_stage)
  }
  return {
    therapists: [...therapists.entries()].map(([id, label]) => ({ id: String(id), label })).sort((a, b) => a.label.localeCompare(b.label)),
    caseManagers: [...caseManagers.entries()].map(([id, label]) => ({ id: String(id), label })).sort((a, b) => a.label.localeCompare(b.label)),
    children: [...children.entries()].map(([id, label]) => ({ id: String(id), label })).sort((a, b) => a.label.localeCompare(b.label)),
    stages: [...stages].sort(),
  }
}

function rowCreatedDay(row) {
  if (!row.created_at) return null
  return row.created_at.slice(0, 10)
}

export function filterPipelineRows(rows, filters = {}, { viewerUserId } = {}) {
  const f = defaultPipelineFilters(filters)
  let list = rows

  if (f.productModule !== 'all') {
    list = list.filter((r) => r.product_module === f.productModule)
  }
  if (f.caseState !== 'all') {
    list = list.filter((r) => matchesCaseState(r, f.caseState))
  }
  if (f.caseManagerId === 'unassigned') {
    list = list.filter((r) => !r.case_manager_user_id)
  } else if (f.caseManagerId !== 'all') {
    // Mentored cases are tagged is_mentor_case for the current viewer; include them when
    // filtering to that viewer's own case-manager id.
    list = list.filter(
      (r) =>
        String(r.case_manager_user_id) === f.caseManagerId ||
        (Boolean(r.is_mentor_case) &&
          viewerUserId != null &&
          String(viewerUserId) === f.caseManagerId),
    )
  }
  if (f.therapistId === 'unassigned') {
    list = list.filter((r) => !r.therapist_user_id)
  } else if (f.therapistId !== 'all') {
    list = list.filter((r) => String(r.therapist_user_id) === f.therapistId)
  }
  if (f.childId !== 'all') {
    list = list.filter((r) => String(r.child_id) === f.childId)
  }
  if (f.operationalStage !== 'all') {
    list = list.filter((r) => r.operational_stage === f.operationalStage)
  }

  const { from: openedFrom, to: openedTo } = openedDateBounds(f.openedPreset, f.dateFrom, f.dateTo)
  if (openedFrom) {
    list = list.filter((r) => {
      const d = rowCreatedDay(r)
      return d && d >= openedFrom
    })
  }
  if (openedTo) {
    list = list.filter((r) => {
      const d = rowCreatedDay(r)
      return d && d <= openedTo
    })
  }

  if (f.openedYear && f.openedYear !== 'all') {
    list = list.filter((r) => {
      const d = rowCreatedDay(r)
      return d && d.slice(0, 4) === f.openedYear
    })
  }
  if (f.openedMonth && f.openedMonth !== 'all') {
    list = list.filter((r) => {
      const d = rowCreatedDay(r)
      return d && d.slice(5, 7) === f.openedMonth
    })
  }

  if (f.unassignedCmOnly) {
    list = list.filter((r) => !r.case_manager_user_id)
  }
  if (f.unassignedTherapistOnly) {
    list = list.filter((r) => !r.therapist_user_id)
  }

  const q = f.search.trim().toLowerCase()
  if (q) {
    list = list.filter((r) => {
      const hay = [
        r.case_code,
        r.parent_name,
        r.child_name,
        r.service_type,
        r.therapist_name,
        r.case_manager_name,
        r.next_action,
        r.operational_stage,
        r.status,
        r.in_transition ? 'transition in transition handover' : '',
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
      return hay.includes(q)
    })
  }

  if (f.queue === 'needs_action') {
    list = list.filter((r) => r.pipeline_column !== 'closed' && r.pipeline_column !== 'active')
  } else if (f.queue === 'allotment') {
    list = list.filter((r) => ['pending_allotment', 'needs_therapist'].includes(r.pipeline_column))
  } else if (f.queue === 'assignment') {
    list = list.filter((r) => ['needs_therapist', 'reassignment'].includes(r.pipeline_column))
  } else if (f.queue === 'review') {
    list = list.filter((r) => ['reports_logs', 'iep'].includes(r.pipeline_column))
  } else if (f.queue === 'compliance') {
    list = list.filter((r) => r.pipeline_column === 'compliance')
  } else if (f.queue === 'active') {
    list = list.filter((r) => r.pipeline_column === 'active')
  } else if (f.queue === 'closed') {
    list = list.filter((r) => r.pipeline_column === 'closed' || r.status === 'CLOSED')
  }

  return list
}

export function countActivePipelineFilters(filters = {}) {
  const f = defaultPipelineFilters(filters)
  let n = 0
  if (f.productModule !== 'all') n += 1
  if (f.caseState !== 'all') n += 1
  if (f.caseManagerId !== 'all') n += 1
  if (f.therapistId !== 'all') n += 1
  if (f.childId !== 'all') n += 1
  if (f.openedPreset !== 'all') n += 1
  if (f.openedMonth !== 'all') n += 1
  if (f.openedYear !== 'all') n += 1
  if (f.operationalStage !== 'all') n += 1
  if (f.unassignedCmOnly) n += 1
  if (f.unassignedTherapistOnly) n += 1
  return n
}

/** Apply filters for queue tab badge counts (excludes queue + case state so tabs stay meaningful). */
export function filterPipelineRowsForQueueCounts(rows, filters = {}, opts = {}) {
  return filterPipelineRows(
    rows,
    { ...defaultPipelineFilters(filters), queue: 'all', caseState: 'all' },
    opts,
  )
}

/** Rows matching all filters except the queue tab (for "in scope" counts). */
export function filterPipelineRowsWithoutQueue(rows, filters = {}, opts = {}) {
  return filterPipelineRows(rows, { ...defaultPipelineFilters(filters), queue: 'all' }, opts)
}

export function pipelineQueueCounts(rows) {
  const counts = {
    needs_action: 0,
    allotment: 0,
    assignment: 0,
    review: 0,
    compliance: 0,
    closed: 0,
    all: rows.length,
  }
  for (const r of rows) {
    if (r.pipeline_column !== 'closed' && r.pipeline_column !== 'active') counts.needs_action += 1
    if (r.pipeline_column === 'pending_allotment' || r.pipeline_column === 'needs_therapist') counts.allotment += 1
    if (['needs_therapist', 'reassignment'].includes(r.pipeline_column)) counts.assignment += 1
    if (['reports_logs', 'iep'].includes(r.pipeline_column)) counts.review += 1
    if (r.pipeline_column === 'compliance') counts.compliance += 1
    if (r.pipeline_column === 'closed' || r.status === 'CLOSED') counts.closed += 1
  }
  return counts
}

/** Activate a pending-allotment case (sends invites; status → ACTIVE). */
export async function activateCaseAllotment(caseId) {
  return apiFetch(`/api/v1/admin/cases/${caseId}/activate-allotment`, {
    method: 'POST',
    timeoutMs: 45_000,
  })
}

/**
 * Primary + secondary actions for a pipeline row (no navigation on row click).
 */
export function buildPipelineActions(row, { canAssign, canUpdate, canCreate, canWrite = true, detailsOnly = false }) {
  if (detailsOnly) {
    return [{ id: 'case', label: 'Details', variant: 'ghost', href: `/admin/cases/${row.id}` }]
  }
  if (row.in_transition) {
    const actions = [
      {
        id: 'transition',
        label: 'Manage transition',
        variant: 'primary',
        href: `/admin/cases/${row.id}?tab=scheduling`,
      },
      { id: 'case', label: 'Details', variant: 'ghost', href: `/admin/cases/${row.id}` },
    ]
    if (row.open_incidents > 0) {
      actions.push({
        id: 'incidents',
        label: `Incidents (${row.open_incidents})`,
        variant: 'ghost',
        href: '/admin/support?tab=incidents',
      })
    }
    return actions
  }
  const actions = []
  const col = row.pipeline_column
  const write = canWrite && canAssign
  const writeCase = canWrite && canUpdate
  const writeCreate = canWrite && canCreate

  if (col === 'pending_allotment') {
    if (writeCreate && row.therapist_user_id) {
      actions.push({ id: 'allot', label: 'Allot', variant: 'primary' })
    } else if (write && !row.therapist_user_id) {
      actions.push({ id: 'reallot', label: 'Assign therapist', variant: 'primary' })
    }
  }
  if (write && (col === 'needs_therapist' || col === 'reassignment')) {
    actions.push({ id: 'reallot', label: col === 'reassignment' ? 'Reallot' : 'Assign', variant: 'primary' })
  }
  if (col === 'reports_logs') {
    if (row.missing_logs > 0) {
      actions.push({
        id: 'review_logs',
        label: `Logs (${row.missing_logs})`,
        variant: 'primary',
        href: `/admin/cases/${row.id}?tab=logs`,
      })
    }
    if (row.reports_under_review > 0) {
      actions.push({
        id: 'review_reports',
        label: `Reports (${row.reports_under_review})`,
        variant: 'primary',
        href: '/admin/reports?tab=queue',
      })
    }
  }
  if (col === 'iep') {
    actions.push({ id: 'iep', label: 'IEP workspace', variant: 'primary', href: '/admin/iep' })
  }
  if (col === 'compliance') {
    if (row.open_tickets > 0) {
      actions.push({
        id: 'tickets',
        label: `Tickets (${row.open_tickets})`,
        variant: 'primary',
        href: '/admin/support?tab=tickets',
      })
    }
    if (row.open_incidents > 0) {
      actions.push({
        id: 'incidents',
        label: `Incidents (${row.open_incidents})`,
        variant: 'primary',
        href: '/admin/support?tab=incidents',
      })
    }
    if (!row.open_tickets && !row.open_incidents) {
      actions.push({ id: 'open_case', label: 'Review case', variant: 'primary', href: `/admin/cases/${row.id}` })
    }
  }

  actions.push({ id: 'case', label: 'Details', variant: 'ghost', href: `/admin/cases/${row.id}` })

  if (writeCase && col !== 'closed') {
    actions.push({ id: 'close', label: 'Close', variant: 'danger' })
  }

  return actions
}

export function pipelineStatusBadgeVariant(tone) {
  if (tone === 'danger') return 'danger'
  if (tone === 'warning') return 'warning'
  if (tone === 'success') return 'success'
  if (tone === 'purple') return 'neutral'
  return 'neutral'
}
