import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiDownload, apiFetch } from '../../lib/apiClient.js'
import {
  AdminPageHeader,
  AdminPanel,
  AdminEmptyState,
  AdminSearchInput,
  AdminToolbar,
  PortalTabBar,
  RejectWithComment,
  StatusBadge,
} from '../admin-portal/ui/index.js'
import { PeopleListPagination } from '../admin-portal/ui/PeopleListPagination.jsx'
import './leave-management.css'
import { formatLeaveRecordSplit } from '../../lib/leaveFormUtils.js'
import { leaveRetroactiveHint, absenceRetroactiveHint } from '../../lib/leaveMigration.js'
import { ManualLeaveTab } from './ManualLeaveTab.jsx'

const STATUS_COLORS = {
  PENDING: { bg: '#fefce8', color: '#a16207', border: '#fde047' },
  APPROVED: { bg: '#f0fdf4', color: '#15803d', border: '#86efac' },
  REJECTED: { bg: '#fef2f2', color: '#b91c1c', border: '#fca5a5' },
  CANCELLED: { bg: '#f4f4f5', color: '#71717a', border: '#d4d4d8' },
}

const REVIEW_TABS = [
  ['PENDING', 'Pending'],
  ['APPROVED', 'Approved'],
  ['REJECTED', 'Rejected'],
  ['ALL', 'All'],
]

const REQUEST_VIEWS = [
  { id: 'leave', label: 'Leave requests' },
  { id: 'child_absence', label: 'Child absence' },
]

function normalizeLeaveRow(row) {
  return { ...row, record_type: 'leave', display_status: row.status }
}

function normalizeChildAbsenceRow(row) {
  return {
    ...row,
    record_type: 'child_absence',
    display_status: row.leave_status || row.status,
    start_date: row.scheduled_date,
    end_date: row.scheduled_date,
    day_count: 1,
    leave_type: 'CHILD_ABSENT',
  }
}

function resolveRequestView(searchParams) {
  const view = searchParams.get('view')
  if (view === 'child_absence') return 'child_absence'
  if (searchParams.get('type') === 'CHILD_ABSENCE') return 'child_absence'
  return 'leave'
}

const APPROVALS_PAGE_SIZE = 25
const SEARCH_MIN_LEN = 2

const EMPTY_COUNTS = { PENDING: 0, APPROVED: 0, REJECTED: 0, ALL: 0 }

export function LeaveManagementPage({ portal = 'hr' }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const tabParam = searchParams.get('tab')
  const mainTab = tabParam === 'report' || tabParam === 'manual' ? tabParam : 'approvals'
  const tab = searchParams.get('status') || 'PENDING'
  const requestView = resolveRequestView(searchParams)

  const [leaves, setLeaves] = useState([])
  const [childAbsences, setChildAbsences] = useState([])
  const [loading, setLoading] = useState(true)
  const [rejectingKey, setRejectingKey] = useState(null)
  const [rejectComment, setRejectComment] = useState('')
  const [processing, setProcessing] = useState({})
  const [error, setError] = useState('')
  const [reportYear, setReportYear] = useState(new Date().getFullYear())
  const [manualYear, setManualYear] = useState(new Date().getFullYear())
  const [reportGranularity, setReportGranularity] = useState('monthly')
  const [reportRows, setReportRows] = useState([])
  const [reportLoading, setReportLoading] = useState(false)
  const [migrationInfo, setMigrationInfo] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [statusCounts, setStatusCounts] = useState(EMPTY_COUNTS)

  const eyebrow = portal === 'admin' ? 'Admin' : 'HR'
  const searchActive = debouncedSearch.trim().length >= SEARCH_MIN_LEN

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(searchQuery), 300)
    return () => window.clearTimeout(timer)
  }, [searchQuery])

  useEffect(() => {
    setPage(1)
  }, [debouncedSearch, tab, requestView])

  async function loadMigrationInfo() {
    try {
      const migration = await apiFetch('/api/v1/leave/migration-info')
      setMigrationInfo(migration)
    } catch {
      setMigrationInfo(null)
    }
  }

  async function loadApprovals() {
    setLoading(true)
    setError('')
    try {
      const params = new URLSearchParams()
      params.set('page', searchActive ? '1' : String(page))
      params.set('page_size', searchActive ? '500' : String(APPROVALS_PAGE_SIZE))
      if (searchActive) params.set('search', debouncedSearch.trim())
      if (tab !== 'ALL') {
        if (requestView === 'leave') params.set('leave_status', tab)
        else params.set('absence_status', tab)
      }

      if (requestView === 'leave') {
        const data = await apiFetch(`/api/v1/leave?${params}`)
        const items = Array.isArray(data) ? data : data?.items || []
        setLeaves(items)
        setTotal(Array.isArray(data) ? items.length : Number(data?.total || items.length))
        setStatusCounts(data?.counts || EMPTY_COUNTS)
      } else {
        const data = await apiFetch(`/api/v1/leave/child-absence?${params}`)
        setChildAbsences(Array.isArray(data?.items) ? data.items : [])
        setTotal(Number(data?.total || 0))
        setStatusCounts(data?.counts || EMPTY_COUNTS)
      }
      return true
    } catch (err) {
      setError(err.message || 'Could not load leave requests')
      return false
    } finally {
      setLoading(false)
    }
  }

  async function load() {
    return loadApprovals()
  }

  async function loadReport() {
    setReportLoading(true)
    setError('')
    try {
      const data = await apiFetch(
        `/api/v1/leave/report?year=${reportYear}&granularity=${reportGranularity}`,
      )
      setReportRows(data.rows || [])
    } catch (err) {
      setReportRows([])
      setError(err.message || 'Could not load report')
    } finally {
      setReportLoading(false)
    }
  }

  useEffect(() => {
    loadMigrationInfo()
  }, [])

  useEffect(() => {
    if (mainTab === 'approvals') loadApprovals()
  }, [mainTab, requestView, tab, page, debouncedSearch])

  useEffect(() => {
    if (mainTab === 'report') loadReport()
  }, [mainTab, reportYear, reportGranularity])

  function setMainTab(next) {
    const nextParams = new URLSearchParams(searchParams)
    nextParams.set('tab', next)
    if (next === 'report') nextParams.delete('status')
    setSearchParams(nextParams, { replace: true })
  }

  function setStatusTab(next) {
    const nextParams = new URLSearchParams(searchParams)
    nextParams.set('tab', 'approvals')
    if (next === 'PENDING') nextParams.delete('status')
    else nextParams.set('status', next)
    setSearchParams(nextParams, { replace: true })
  }

  function setRequestView(next) {
    const nextParams = new URLSearchParams(searchParams)
    nextParams.set('tab', 'approvals')
    nextParams.delete('type')
    if (next === 'leave') nextParams.delete('view')
    else nextParams.set('view', 'child_absence')
    setSearchParams(nextParams, { replace: true })
  }

  function rowKey(row) {
    return `${row.record_type}-${row.id}`
  }

  async function reviewLeave(id, status, note = null) {
    const key = `leave-${id}`
    setProcessing((p) => ({ ...p, [key]: true }))
    setError('')
    try {
      const updated = await apiFetch(`/api/v1/leave/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status, review_note: note }),
      })
      if (rejectingKey === key) {
        setRejectingKey(null)
        setRejectComment('')
      }
      if (updated?.id) {
        setLeaves((prev) =>
          prev.map((row) =>
            row.id === id
              ? {
                  ...row,
                  status: updated.status ?? status,
                  review_note: updated.review_note ?? note,
                  reviewer_name: updated.reviewer_name ?? row.reviewer_name,
                }
              : row,
          ),
        )
      }
      await load()
    } catch (err) {
      setError(err.message || 'Could not update leave status')
    } finally {
      setProcessing((p) => ({ ...p, [key]: false }))
    }
  }

  async function reviewChildAbsence(id, action, note = null) {
    const key = `child_absence-${id}`
    setProcessing((p) => ({ ...p, [key]: true }))
    setError('')
    try {
      await apiFetch(`/api/v1/sessions/absence/${id}/${action}`, {
        method: 'POST',
        body: JSON.stringify({ review_note: note }),
      })
      if (rejectingKey === key) {
        setRejectingKey(null)
        setRejectComment('')
      }
      await load()
    } catch (err) {
      setError(err.message || 'Could not update child absence status')
    } finally {
      setProcessing((p) => ({ ...p, [key]: false }))
    }
  }

  function startReject(key) {
    setRejectingKey(key)
    setRejectComment('')
  }

  function cancelReject() {
    setRejectingKey(null)
    setRejectComment('')
  }

  async function confirmReject(row) {
    const note = rejectComment.trim()
    if (!note) {
      setError('Add a comment explaining why this request was rejected.')
      return
    }
    const key = rowKey(row)
    if (row.record_type === 'child_absence') {
      await reviewChildAbsence(row.id, 'reject', note)
    } else {
      await reviewLeave(row.id, 'REJECTED', note)
    }
    if (rejectingKey === key) {
      setRejectingKey(null)
      setRejectComment('')
    }
  }

  async function approveRow(row) {
    if (row.record_type === 'child_absence') {
      await reviewChildAbsence(row.id, 'approve')
    } else {
      await reviewLeave(row.id, 'APPROVED', null)
    }
  }

  async function exportCsv() {
    try {
      await apiDownload(
        `/api/v1/leave/report?year=${reportYear}&granularity=${reportGranularity}&format=csv`,
        `leave-report-${reportYear}.csv`,
      )
    } catch (err) {
      setError(err.message || 'Export failed')
    }
  }

  const displayed =
    requestView === 'child_absence'
      ? childAbsences.map(normalizeChildAbsenceRow)
      : leaves.map(normalizeLeaveRow)

  const counts = statusCounts
  const totalPages = searchActive ? 1 : Math.max(1, Math.ceil(total / APPROVALS_PAGE_SIZE))
  const rangeStart = total === 0 ? 0 : searchActive ? 1 : (page - 1) * APPROVALS_PAGE_SIZE + 1
  const rangeEnd = searchActive ? total : Math.min(page * APPROVALS_PAGE_SIZE, total)

  const panelTitle =
    requestView === 'child_absence'
      ? `${total} child absence request${total === 1 ? '' : 's'}${searchActive ? ' matching search' : ''}`
      : `${total} leave request${total === 1 ? '' : 's'}${searchActive ? ' matching search' : ''}`

  return (
    <div className="admin-page leave-mgmt">
      <AdminPageHeader
        eyebrow={eyebrow}
        title="Leave management"
        subtitle="Review therapist leave and child absence requests, record leave manually, and export reports."
      />

      {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}

      <PortalTabBar
        ariaLabel="Leave sections"
        activeId={mainTab}
        onChange={setMainTab}
        tabs={[
          { id: 'approvals', label: 'Approvals' },
          { id: 'manual', label: 'Manual' },
          { id: 'report', label: 'Report' },
        ]}
      />

      {mainTab === 'manual' ? (
        <ManualLeaveTab year={manualYear} onYearChange={setManualYear} onLeaveRecorded={loadApprovals} />
      ) : mainTab === 'approvals' ? (
        <>
          <PortalTabBar
            ariaLabel="Request type"
            activeId={requestView}
            onChange={setRequestView}
            className="leave-mgmt__view-tabs"
            tabs={REQUEST_VIEWS}
          />

          <div className="leave-mgmt__filter-section">
            <div className="leave-mgmt__status-row" role="group" aria-label="Filter by status">
              {REVIEW_TABS.map(([val, label]) => (
                <button
                  key={val}
                  type="button"
                  className={`leave-mgmt__status-pill ${tab === val ? 'is-active' : ''}`}
                  onClick={() => setStatusTab(val)}
                >
                  {label} ({counts[val]})
                </button>
              ))}
            </div>
          </div>

          <div className="leave-mgmt__search-row">
            <AdminSearchInput
              value={searchQuery}
              onChange={setSearchQuery}
              placeholder={
                requestView === 'child_absence'
                  ? 'Search child, therapist, case, email…'
                  : 'Search therapist name, email, reason…'
              }
            />
            {searchQuery.trim().length > 0 && searchQuery.trim().length < SEARCH_MIN_LEN ? (
              <p className="leave-mgmt-manual__results-empty" style={{ marginTop: 8 }}>
                Type at least {SEARCH_MIN_LEN} characters to search across all matching records.
              </p>
            ) : null}
          </div>

          <AdminPanel title={panelTitle} padded={false}>
            <div className="leave-mgmt__list">
              {loading ? (
                <div className="admin-skeleton" />
              ) : displayed.length === 0 ? (
                <AdminEmptyState
                  title="No requests"
                  description={
                    searchQuery.trim()
                      ? 'Nothing matches your search. Try a different name or keyword.'
                      : 'Nothing matches this filter.'
                  }
                />
              ) : (
                <div>
                  {displayed.map((l) => {
                    const key = rowKey(l)
                    const sc = STATUS_COLORS[l.display_status] || STATUS_COLORS.PENDING
                    const retroHint =
                      l.record_type === 'leave'
                        ? leaveRetroactiveHint(l, migrationInfo)
                        : absenceRetroactiveHint(l, migrationInfo)
                    const isChildAbsence = l.record_type === 'child_absence'
                    return (
                      <div key={key} className="leave-mgmt__card">
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10, flexWrap: 'wrap' }}>
                          <span
                            style={{
                              background: sc.bg,
                              color: sc.color,
                              border: `1px solid ${sc.border}`,
                              fontSize: '0.72rem',
                              fontWeight: 700,
                              padding: '2px 8px',
                              borderRadius: 20,
                            }}
                          >
                            {l.display_status}
                          </span>
                          {isChildAbsence ? (
                            <span className="leave-mgmt__retro-badge">Child absent</span>
                          ) : null}
                          {l.is_retroactive ? (
                            <span className="leave-mgmt__retro-badge">
                              {isChildAbsence ? 'Previous absence' : 'Previous leave'}
                            </span>
                          ) : null}
                          {!isChildAbsence ? (
                            <span className="admin-chip admin-chip--sm">{l.leave_type}</span>
                          ) : null}
                          <span className="admin-table__primary">
                            {isChildAbsence
                              ? `${l.child_name || 'Child'} · ${l.therapist_name || `Therapist #${l.therapist_user_id}`}`
                              : l.therapist_name || `Therapist #${l.therapist_user_id}`}
                          </span>
                          <span className="admin-muted" style={{ marginLeft: 'auto', fontSize: '0.75rem' }}>
                            {isChildAbsence
                              ? `${l.start_date}${l.start_time ? ` · ${String(l.start_time).slice(0, 5)}` : ''}`
                              : `${formatLeaveRecordSplit(l)} · ${l.day_count} day${l.day_count === 1 ? '' : 's'}`}
                          </span>
                        </div>
                        {!isChildAbsence ? (
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 10 }}>
                            <div>
                              <p className="admin-muted" style={{ fontSize: '0.72rem', margin: 0 }}>From</p>
                              <p style={{ fontWeight: 600, margin: '2px 0 0' }}>{l.start_date}</p>
                            </div>
                            <div>
                              <p className="admin-muted" style={{ fontSize: '0.72rem', margin: 0 }}>To</p>
                              <p style={{ fontWeight: 600, margin: '2px 0 0' }}>{l.end_date}</p>
                            </div>
                          </div>
                        ) : (
                          <div style={{ marginBottom: 10 }}>
                            <p className="admin-muted" style={{ fontSize: '0.72rem', margin: 0 }}>Session date</p>
                            <p style={{ fontWeight: 600, margin: '2px 0 0' }}>{l.start_date}</p>
                            {l.case_code ? (
                              <p className="admin-muted" style={{ fontSize: '0.8rem', margin: '6px 0 0' }}>
                                Case {l.case_code}
                              </p>
                            ) : null}
                          </div>
                        )}
                        {!isChildAbsence && l.consulted_with_parents ? (
                          <p
                            className="admin-muted"
                            style={{
                              fontSize: '0.8rem',
                              marginBottom: 10,
                              padding: '6px 10px',
                              background: '#f0fdf4',
                              borderRadius: 8,
                              border: '1px solid #bbf7d0',
                            }}
                          >
                            Consulted with parents
                          </p>
                        ) : null}
                        {!isChildAbsence && Array.isArray(l.case_ids) && l.case_ids.length > 1 ? (
                          <p className="admin-muted" style={{ fontSize: '0.8rem', marginBottom: 10 }}>
                            {l.case_ids.length} cases on this request
                          </p>
                        ) : null}
                        {l.reason ? (
                          <p className="admin-muted" style={{ fontSize: '0.85rem', marginBottom: 10 }}>{l.reason}</p>
                        ) : null}
                        {retroHint && l.display_status === 'PENDING' ? (
                          <p className="leave-mgmt__retro-note" role="note">
                            {retroHint}
                          </p>
                        ) : null}
                        {l.display_status === 'REJECTED' && l.review_note ? (
                          <p
                            className="admin-muted"
                            style={{
                              fontSize: '0.85rem',
                              marginBottom: 10,
                              padding: '8px 10px',
                              background: '#fef2f2',
                              borderRadius: 8,
                              border: '1px solid #fecaca',
                            }}
                          >
                            <strong>Rejection note:</strong> {l.review_note}
                          </p>
                        ) : null}
                        {l.display_status === 'PENDING' ? (
                          <div className="leave-mgmt__card-actions">
                            {rejectingKey === key && !rejectComment.trim() ? (
                              <p className="leave-mgmt__inline-error">
                                Add a rejection comment, then confirm reject.
                              </p>
                            ) : null}
                            <RejectWithComment
                              rejecting={rejectingKey === key}
                              comment={rejectingKey === key ? rejectComment : ''}
                              onCommentChange={setRejectComment}
                              onStartReject={() => startReject(key)}
                              onCancelReject={cancelReject}
                              onConfirmReject={() => confirmReject(l)}
                              onApprove={() => approveRow(l)}
                              processing={!!processing[key]}
                              placeholder={
                                isChildAbsence
                                  ? 'Why is this child absence rejected? (required)'
                                  : 'Why is this leave rejected? (required)'
                              }
                            />
                          </div>
                        ) : null}
                      </div>
                    )
                  })}
                </div>
              )}
              {!loading && !searchActive && total > APPROVALS_PAGE_SIZE ? (
                <PeopleListPagination
                  page={page}
                  totalPages={totalPages}
                  total={total}
                  rangeStart={rangeStart}
                  rangeEnd={rangeEnd}
                  onPageChange={setPage}
                />
              ) : null}
            </div>
          </AdminPanel>
        </>
      ) : (
        <AdminPanel title="Leave report" padded={false}>
          <div className="admin-panel__body">
            <AdminToolbar>
              <label className="admin-muted" style={{ fontSize: '0.75rem' }}>
                Year
                <select
                  className="admin-select"
                  style={{ display: 'block', marginTop: 4 }}
                  value={reportYear}
                  onChange={(e) => setReportYear(Number(e.target.value))}
                >
                  {[reportYear - 1, reportYear, reportYear + 1].map((y) => (
                    <option key={y} value={y}>
                      {y}
                    </option>
                  ))}
                </select>
              </label>
              <label className="admin-muted" style={{ fontSize: '0.75rem' }}>
                View
                <select
                  className="admin-select"
                  style={{ display: 'block', marginTop: 4 }}
                  value={reportGranularity}
                  onChange={(e) => setReportGranularity(e.target.value)}
                >
                  <option value="monthly">Monthly</option>
                  <option value="yearly">Yearly</option>
                </select>
              </label>
              <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={exportCsv}>
                Export CSV
              </button>
            </AdminToolbar>
            {reportLoading ? (
              <div className="admin-skeleton" />
            ) : reportRows.length === 0 ? (
              <AdminEmptyState title="No data" description="No leave records for this period." />
            ) : (
              <div className="admin-table-wrap">
                <table className="admin-table admin-table--compact">
                  <thead>
                    <tr>
                      <th>Therapist</th>
                      <th>Period</th>
                      <th>Type</th>
                      <th>Status</th>
                      <th>Days</th>
                      <th>From</th>
                      <th>To</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reportRows.map((r, idx) => (
                      <tr key={`${r.therapist_user_id}-${r.period}-${idx}`}>
                        <td>{r.therapist_name}</td>
                        <td>{r.period}</td>
                        <td>{r.leave_type}</td>
                        <td>
                          <StatusBadge status={r.status} />
                        </td>
                        <td>{r.days}</td>
                        <td>{r.start_date}</td>
                        <td>{r.end_date}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </AdminPanel>
      )}
    </div>
  )
}
