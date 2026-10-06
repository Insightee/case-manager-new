import { formatDateIN, formatTimeIST } from '../../lib/datetime.js'
import { formatDurationSeconds } from '../../lib/staffAttendanceApi.js'
import { AdminEmptyState, AdminPanel, StatusBadge } from './ui/index.js'

const STATUS_TONE = {
  COMPLETED: 'green',
  IN_PROGRESS: 'blue',
  AUTO_CLOSED: 'zinc',
}

export function StaffAttendanceHistory({ rows = [], loading = false, title = 'Session history' }) {
  return (
    <AdminPanel title={title} padded={false}>
      {loading ? (
        <p className="admin-muted staff-attendance-history__loading">Loading…</p>
      ) : rows.length === 0 ? (
        <AdminEmptyState
          title="No sessions yet"
          description="Clock in from your dashboard to start tracking."
        />
      ) : (
        <>
          <div className="staff-attendance-table-wrap admin-hide-mobile">
            <table className="staff-attendance-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Mode</th>
                  <th>Status</th>
                  <th>Start</th>
                  <th>End</th>
                  <th>Total</th>
                  <th>Summary</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>{formatDateIN(`${row.work_date}T12:00:00Z`) || row.work_date}</td>
                    <td>{row.work_mode === 'WFH' ? 'WFH' : row.work_mode === 'OFFICE' ? 'Office' : '—'}</td>
                    <td>
                      <StatusBadge tone={STATUS_TONE[row.status] || 'zinc'}>
                        {row.status?.replace(/_/g, ' ') || '—'}
                      </StatusBadge>
                    </td>
                    <td>{row.clock_in_at ? formatTimeIST(row.clock_in_at) : '—'}</td>
                    <td>{row.clock_out_at ? formatTimeIST(row.clock_out_at) : '—'}</td>
                    <td>{formatDurationSeconds(row.total_work_seconds)}</td>
                    <td>{row.work_summary || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="admin-data-list__cards admin-show-mobile staff-attendance-history__mobile">
            {rows.map((row) => (
              <li key={row.id} className="staff-attendance-mobile-card">
                <div className="staff-attendance-mobile-card__meta">
                  <strong>{formatDateIN(`${row.work_date}T12:00:00Z`) || row.work_date}</strong>
                  <StatusBadge tone={STATUS_TONE[row.status] || 'zinc'}>
                    {row.status?.replace(/_/g, ' ') || '—'}
                  </StatusBadge>
                </div>
                <p className="admin-muted" style={{ margin: '0 0 6px' }}>
                  {row.work_mode === 'WFH' ? 'WFH' : row.work_mode === 'OFFICE' ? 'Office' : '—'}
                  {' · '}
                  {row.clock_in_at ? formatTimeIST(row.clock_in_at) : '—'}
                  {' → '}
                  {row.clock_out_at ? formatTimeIST(row.clock_out_at) : '—'}
                  {' · '}
                  {formatDurationSeconds(row.total_work_seconds)}
                </p>
                {row.work_summary ? <p style={{ margin: 0 }}>{row.work_summary}</p> : null}
              </li>
            ))}
          </ul>
        </>
      )}
    </AdminPanel>
  )
}
