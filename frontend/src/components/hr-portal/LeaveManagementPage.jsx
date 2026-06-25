import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiDownload, apiFetch } from '../../lib/apiClient.js'
import {
  AdminPageHeader,
  AdminPanel,
  AdminEmptyState,
  AdminToolbar,
  PortalTabBar,
  RejectWithComment,
  StatusBadge,
} from '../admin-portal/ui/index.js'
import './leave-management.css'
import { formatLeaveRecordSplit } from '../../lib/leaveFormUtils.js'
import { leaveRetroactiveHint } from '../../lib/leaveMigration.js'
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

const TYPE_TABS = [
  ['ALL', 'All types'],
  ['CHILD_ABSENCE', 'Child absence'],
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

export function LeaveManagementPage({ portal = 'hr' }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const tabParam = searchParams.get('tab')
  const mainTab = tabParam === 'report' || tabParam === 'manual' ? tabParam : 'approvals'
  const tab = searchParams.get('status') || 'PENDING'
  const typeTab = searchParams.get('type') || 'ALL'

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

  const eyebrow = portal === 'admin' ? 'Admin' : 'HR'

  async function load() {
    setLoading(true)
    try {
      const [data, childData, migration] = await Promise.all([
        apiFetch('/api/v1/leave'),
        apiFetch('/api/v1/leave/child-absence').catch(() => ({ items: [] })),
        apiFetch('/api/v1/leave/migration-info').catch(() => null),
      ])
      setLeaves(Array.isArray(data) ? data : [])
      setChildAbsences(Array.isArray(childData?.items) ? childData.items : [])
      setMigrationInfo(migration)
      return true
    } catch (err) {
      setError(err.message || 'Could not load leave requests')
      return false
    } finally {
      setLoading(false)
    }
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
    load()
  }, [])

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

  function setTypeTab(next) {
    const nextParams = new URLSearchParams(searchParams)
    nextParams.set('tab', 'approvals')
    if (next === 'ALL') nextParams.delete('type')
    else nextParams.set('type', next)
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

  const allRequests = [
    ...leaves.map(normalizeLeaveRow),
    ...childAbsences.map(normalizeChildAbsenceRow),
  ]

  const typeFiltered =
    typeTab === 'CHILD_ABSENCE'
      ? allRequests.filter((r) => r.record_type === 'child_absence')
      : allRequests

  const displayed =
    tab === 'ALL' ? typeFiltered : typeFiltered.filter((r) => r.display_status === tab)

  const counts = {
    PENDING: allRequests.filter((r) => r.display_status === 'PENDING').length,
    APPROVED: allRequests.filter((r) => r.display_status === 'APPROVED').length,
    REJECTED: allRequests.filter((r) => r.display_status === 'REJECTED').length,
    ALL: allRequests.length,
  }

  const childAbsenceCount = allRequests.filter((r) => r.record_type === 'child_absence').length

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
          { id: 'approvals', label: 'Approvals', badge: counts.PENDING || null },
          { id: 'manual', label: 'Manual' },
          { id: 'report', label: 'Report' },
        ]}
      />

      {mainTab === 'manual' ? (
        <>
          <AdminToolbar>
            <label className="admin-muted" style={{ fontSize: '0.75rem' }}>
              Balance year
              <select
                className="admin-select"
                style={{ display: 'block', marginTop: 4 }}
                value={manualYear}
                onChange={(e) => setManualYear(Number(e.target.value))}
              >
                {[manualYear - 1, manualYear, manualYear + 1].map((y) => (
                  <option key={y} value={y}>
                    {y}
                  </option>
                ))}
              </select>
            </label>
          </AdminToolbar>
          <ManualLeaveTab year={manualYear} onLeaveRecorded={load} />
        </>
      ) : mainTab === 'approvals' ? (
        <>
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

          <div className="leave-mgmt__status-row" role="group" aria-label="Filter by request type">
            {TYPE_TABS.map(([val, label]) => (
              <button
                key={val}
                type="button"
                className={`leave-mgmt__status-pill ${typeTab === val ? 'is-active' : ''}`}
                onClick={() => setTypeTab(val)}
              >
                {label}
                {val === 'CHILD_ABSENCE' && childAbsenceCount ? ` (${childAbsenceCount})` : ''}
              </button>
            ))}
          </div>

          <AdminPanel title={`${displayed.length} requests`} padded={false}>
            <div className="leave-mgmt__list">
              {loading ? (
                <div className="admin-skeleton" />
              ) : displayed.length === 0 ? (
                <AdminEmptyState title="No requests" description="Nothing matches this filter." />
              ) : (
                <div>
                  {displayed.map((l) => {
                    const key = rowKey(l)
                    const sc = STATUS_COLORS[l.display_status] || STATUS_COLORS.PENDING
                    const retroHint = l.record_type === 'leave' ? leaveRetroactiveHint(l, migrationInfo) : null
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
                            <span className="leave-mgmt__retro-badge">Previous leave</span>
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
