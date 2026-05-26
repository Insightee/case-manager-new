import { Link } from 'react-router-dom'
import { categoryLabel } from '../../lib/reportCategories.js'
import './admin-reports.css'

function statusPillClass(status) {
  const key = String(status || '').toLowerCase()
  return `admin-reports__status-pill admin-reports__status-pill--${key}`
}

export function AdminReportsTable({
  rows,
  loading,
  selected,
  onToggle,
  onToggleAll,
  onView,
  onApprove,
  onReject,
  canReviewRow = () => true,
}) {
  const allSelected = rows.length > 0 && rows.every((r) => selected.has(`${r.report_type}:${r.id}`))

  return (
    <div className="admin-reports__table-wrap">
      <table className="admin-table">
        <thead>
          <tr>
            <th style={{ width: 36 }}>
              <input
                type="checkbox"
                checked={allSelected}
                onChange={(e) => onToggleAll(e.target.checked)}
                aria-label="Select all"
              />
            </th>
            <th>Type</th>
            <th>Case / child</th>
            <th>Label</th>
            <th>Category</th>
            <th>Status</th>
            <th>Therapist</th>
            <th>Updated</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr>
              <td colSpan={9}>Loading…</td>
            </tr>
          ) : rows.length === 0 ? (
            <tr>
              <td colSpan={9}>No reports match your filters.</td>
            </tr>
          ) : (
            rows.map((r) => {
              const key = `${r.report_type}:${r.id}`
              return (
                <tr key={key}>
                  <td>
                    <input
                      type="checkbox"
                      checked={selected.has(key)}
                      onChange={() => onToggle(key)}
                      aria-label={`Select ${r.label}`}
                    />
                  </td>
                  <td>{r.report_type === 'observation' ? 'Observation' : 'Monthly'}</td>
                  <td>
                    {r.case_id ? (
                      <Link
                        to={`/admin/cases/${r.case_id}?tab=reports`}
                        style={{ color: 'inherit', textDecoration: 'none' }}
                      >
                        <div>{r.case_code}</div>
                        <div style={{ fontSize: '0.8rem', color: '#6366f1' }}>{r.child_name}</div>
                      </Link>
                    ) : (
                      <>
                        <div>{r.case_code}</div>
                        <div style={{ fontSize: '0.8rem', color: '#64748b' }}>{r.child_name}</div>
                      </>
                    )}
                  </td>
                  <td>{r.label}</td>
                  <td style={{ fontSize: '0.8rem', color: '#64748b' }}>
                    {r.category ? categoryLabel(r.category) : '—'}
                  </td>
                  <td>
                    <span className={statusPillClass(r.status)}>{r.status}</span>
                    {r.parent_review_status === 'CHANGES_REQUESTED' ? (
                      <span className="admin-reports__parent-badge">Parent changes</span>
                    ) : null}
                    {r.parent_review_status === 'PENDING' ? (
                      <span className="admin-reports__parent-badge">Parent pending</span>
                    ) : null}
                  </td>
                  <td>{r.therapist_name || '—'}</td>
                  <td>{r.updated_at ? new Date(r.updated_at).toLocaleString() : '—'}</td>
                  <td>
                    <div className="admin-btn-group">
                      <button
                        type="button"
                        className="admin-btn admin-btn--ghost admin-btn--sm"
                        onClick={() => onView(r)}
                      >
                        View
                      </button>
                      {canReviewRow(r) &&
                      (r.status === 'UNDER_REVIEW' ||
                        r.parent_review_status === 'CHANGES_REQUESTED') ? (
                        <>
                          <button
                            type="button"
                            className="admin-btn admin-btn--primary admin-btn--sm"
                            onClick={() => onApprove(r)}
                          >
                            Approve
                          </button>
                          {r.status === 'UNDER_REVIEW' ? (
                            <button
                              type="button"
                              className="admin-btn admin-btn--sm"
                              onClick={() => onReject(r)}
                            >
                              Reject
                            </button>
                          ) : null}
                        </>
                      ) : null}
                    </div>
                  </td>
                </tr>
              )
            })
          )}
        </tbody>
      </table>
    </div>
  )
}
