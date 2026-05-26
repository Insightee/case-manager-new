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

export function LeaveManagementPage({ portal = 'hr' }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const mainTab = searchParams.get('tab') === 'report' ? 'report' : 'approvals'
  const tab = searchParams.get('status') || 'PENDING'

  const [leaves, setLeaves] = useState([])
  const [loading, setLoading] = useState(true)
  const [rejectingId, setRejectingId] = useState(null)
  const [rejectComment, setRejectComment] = useState('')
  const [processing, setProcessing] = useState({})
  const [error, setError] = useState('')
  const [reportYear, setReportYear] = useState(new Date().getFullYear())
  const [reportGranularity, setReportGranularity] = useState('monthly')
  const [reportRows, setReportRows] = useState([])
  const [reportLoading, setReportLoading] = useState(false)

  const eyebrow = portal === 'admin' ? 'Admin' : 'HR'

  async function load() {
    setLoading(true)
    try {
      const data = await apiFetch('/api/v1/leave')
      setLeaves(Array.isArray(data) ? data : [])
    } catch {
      setLeaves([])
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

  async function reviewLeave(id, status, note = null) {
    setProcessing((p) => ({ ...p, [id]: true }))
    setError('')
    try {
      await apiFetch(`/api/v1/leave/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status, review_note: note }),
      })
      if (rejectingId === id) {
        setRejectingId(null)
        setRejectComment('')
      }
      load()
    } catch (err) {
      setError(err.message || 'Could not update leave status')
    } finally {
      setProcessing((p) => ({ ...p, [id]: false }))
    }
  }

  function startReject(id) {
    setRejectingId(id)
    setRejectComment('')
  }

  function cancelReject() {
    setRejectingId(null)
    setRejectComment('')
  }

  function confirmReject(id) {
    const note = rejectComment.trim()
    if (!note) {
      setError('Add a comment explaining why this leave was rejected.')
      return
    }
    reviewLeave(id, 'REJECTED', note)
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

  const displayed = tab === 'ALL' ? leaves : leaves.filter((l) => l.status === tab)

  const counts = {
    PENDING: leaves.filter((l) => l.status === 'PENDING').length,
    APPROVED: leaves.filter((l) => l.status === 'APPROVED').length,
    REJECTED: leaves.filter((l) => l.status === 'REJECTED').length,
    ALL: leaves.length,
  }

  return (
    <div className="admin-page leave-mgmt">
      <AdminPageHeader
        eyebrow={eyebrow}
        title="Leave management"
        subtitle="Review therapist leave requests and export monthly or yearly reports."
      />

      {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}

      <PortalTabBar
        ariaLabel="Leave sections"
        activeId={mainTab}
        onChange={setMainTab}
        tabs={[
          { id: 'approvals', label: 'Approvals', badge: counts.PENDING || null },
          { id: 'report', label: 'Report' },
        ]}
      />

      {mainTab === 'approvals' ? (
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

          <AdminPanel title={`${displayed.length} requests`} padded={false}>
            <div className="admin-panel__body" style={{ padding: '0 16px 16px' }}>
              {loading ? (
                <div className="admin-skeleton" />
              ) : displayed.length === 0 ? (
                <AdminEmptyState title="No leave requests" description="Nothing matches this filter." />
              ) : (
                <div>
                  {displayed.map((l) => {
                    const sc = STATUS_COLORS[l.status] || STATUS_COLORS.PENDING
                    return (
                      <div key={l.id} className="leave-mgmt__card">
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
                            {l.status}
                          </span>
                          <span className="admin-chip admin-chip--sm">{l.leave_type}</span>
                          <span className="admin-table__primary">
                            {l.therapist_name || `Therapist #${l.therapist_user_id}`}
                          </span>
                          <span className="admin-muted" style={{ marginLeft: 'auto', fontSize: '0.75rem' }}>
                            {l.day_count} day{l.day_count === 1 ? '' : 's'}
                          </span>
                        </div>
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
                        {l.reason ? (
                          <p className="admin-muted" style={{ fontSize: '0.85rem', marginBottom: 10 }}>{l.reason}</p>
                        ) : null}
                        {l.status === 'REJECTED' && l.review_note ? (
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
                        {l.status === 'PENDING' ? (
                          <RejectWithComment
                            rejecting={rejectingId === l.id}
                            comment={rejectingId === l.id ? rejectComment : ''}
                            onCommentChange={setRejectComment}
                            onStartReject={() => startReject(l.id)}
                            onCancelReject={cancelReject}
                            onConfirmReject={() => confirmReject(l.id)}
                            onApprove={() => reviewLeave(l.id, 'APPROVED', null)}
                            processing={processing[l.id]}
                            placeholder="Why is this leave rejected? (required)"
                          />
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
