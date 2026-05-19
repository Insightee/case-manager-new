import { Fragment, useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { AdminPageHeader, AdminPanel, AdminEmptyState, AdminToolbar, AdminSearchInput, StatusBadge } from './ui/index.js'

function buildLogsUrl({ approvalStatus, lateOnly }) {
  const params = new URLSearchParams()
  if (approvalStatus) params.set('approval_status', approvalStatus)
  if (lateOnly) params.set('late_addition', 'true')
  const qs = params.toString()
  return qs ? `/api/v1/daily-logs?${qs}` : '/api/v1/daily-logs'
}

export function AdminSessionLogsPage() {
  const [logs, setLogs] = useState([])
  const [search, setSearch] = useState('')
  const [approvalFilter, setApprovalFilter] = useState('')
  const [lateOnly, setLateOnly] = useState(false)
  const [loading, setLoading] = useState(true)
  const [actingId, setActingId] = useState(null)
  const [expandedId, setExpandedId] = useState(null)

  const loadLogs = useCallback(() => {
    setLoading(true)
    return apiFetch(
      buildLogsUrl({
        approvalStatus: approvalFilter || undefined,
        lateOnly,
      }),
    )
      .then(setLogs)
      .catch(() => setLogs([]))
      .finally(() => setLoading(false))
  }, [approvalFilter, lateOnly])

  useEffect(() => {
    loadLogs()
  }, [loadLogs])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return logs
    return logs.filter(
      (log) =>
        String(log.id).includes(q) ||
        String(log.session_id).includes(q) ||
        String(log.case_id).includes(q) ||
        log.attendance_status?.toLowerCase().includes(q) ||
        log.late_reason?.toLowerCase().includes(q),
    )
  }, [logs, search])

  async function exportCsv() {
    const csv = await apiFetch('/api/v1/admin/session-logs/export')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'session_logs.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  async function reviewLog(logId, action) {
    setActingId(logId)
    try {
      await apiFetch(`/api/v1/daily-logs/${logId}/${action}`, { method: 'POST' })
      await loadLogs()
    } catch {
      /* keep list */
    } finally {
      setActingId(null)
    }
  }

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="Clinical ops"
        title="Session logs"
        subtitle="Daily logs linked to validated therapy sessions. Approve to share parent notes with families."
        actions={
          <button type="button" className="admin-btn admin-btn--primary" onClick={exportCsv}>
            Export CSV
          </button>
        }
      />

      <AdminPanel title={`${filtered.length} log${filtered.length === 1 ? '' : 's'}`} padded={false}>
        <div className="admin-panel__body">
          <AdminToolbar>
            <AdminSearchInput value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search log, session, or case…" />
            <select
              className="admin-input"
              value={approvalFilter}
              onChange={(e) => setApprovalFilter(e.target.value)}
              aria-label="Filter by approval status"
            >
              <option value="">All statuses</option>
              <option value="PENDING">Pending</option>
              <option value="APPROVED">Approved</option>
              <option value="REJECTED">Rejected</option>
            </select>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14, color: 'var(--admin-text-muted, #64748b)' }}>
              <input type="checkbox" checked={lateOnly} onChange={(e) => setLateOnly(e.target.checked)} />
              Late additions only
            </label>
          </AdminToolbar>

          {loading ? (
            <div className="admin-skeleton" style={{ margin: '0 0 16px' }} />
          ) : filtered.length === 0 ? (
            <AdminEmptyState title="No session logs" description="Logs appear when therapists submit daily entries." />
          ) : (
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Log</th>
                    <th>Case</th>
                    <th>Attendance</th>
                    <th>Flags</th>
                    <th>Approval</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((log) => (
                    <Fragment key={log.id}>
                      <tr>
                        <td>
                          <span className="admin-table__primary">#{log.id}</span>
                          <span className="admin-table__meta">Session {log.session_id}</span>
                        </td>
                        <td>
                          {log.case_id ? (
                            <Link to={`/admin/cases/${log.case_id}?tab=logs`} className="admin-table__primary">
                              Case {log.case_id}
                            </Link>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td>{log.attendance_status ?? '—'}</td>
                        <td>
                          {log.late_addition ? (
                            <span className="admin-badge admin-badge--warning" title={log.late_reason || ''}>
                              Late
                            </span>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td>
                          <StatusBadge status={log.approval_status} />
                        </td>
                        <td>
                          <div className="admin-table__actions">
                            <button
                              type="button"
                              className="admin-btn admin-btn--ghost admin-btn--sm"
                              onClick={() => setExpandedId(expandedId === log.id ? null : log.id)}
                            >
                              {expandedId === log.id ? 'Hide' : 'Details'}
                            </button>
                            {log.approval_status === 'PENDING' ? (
                              <>
                                <button
                                  type="button"
                                  className="admin-btn admin-btn--sm admin-btn--primary"
                                  disabled={actingId === log.id}
                                  onClick={() => reviewLog(log.id, 'approve')}
                                >
                                  Approve
                                </button>
                                <button
                                  type="button"
                                  className="admin-btn admin-btn--sm"
                                  disabled={actingId === log.id}
                                  onClick={() => reviewLog(log.id, 'reject')}
                                >
                                  Reject
                                </button>
                              </>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                      {expandedId === log.id ? (
                        <tr key={`${log.id}-detail`}>
                          <td colSpan={6} style={{ background: '#f8fafc', fontSize: '0.875rem' }}>
                            {log.session_notes ? (
                              <p style={{ margin: '4px 0' }}>
                                <strong>Internal notes:</strong> {log.session_notes}
                              </p>
                            ) : null}
                            {log.observations ? (
                              <p style={{ margin: '4px 0' }}>
                                <strong>Observations:</strong> {log.observations}
                              </p>
                            ) : null}
                            {log.parent_notes ? (
                              <p style={{ margin: '4px 0' }}>
                                <strong>Notes for family:</strong> {log.parent_notes}
                              </p>
                            ) : null}
                            {[log.activities_done, log.goals_addressed, log.follow_ups].filter(Boolean).length ? (
                              <p style={{ margin: '4px 0', color: '#64748b' }}>
                                {[log.activities_done, log.goals_addressed, log.follow_ups].filter(Boolean).join(' · ')}
                              </p>
                            ) : null}
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </AdminPanel>
    </div>
  )
}
