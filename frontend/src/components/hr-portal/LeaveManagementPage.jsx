import { useEffect, useState } from 'react'
import { apiDownload, apiFetch } from '../../lib/apiClient.js'

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
  const [leaves, setLeaves] = useState([])
  const [loading, setLoading] = useState(true)
  const [mainTab, setMainTab] = useState('review')
  const [tab, setTab] = useState('PENDING')
  const [reviewNote, setReviewNote] = useState({})
  const [processing, setProcessing] = useState({})
  const [error, setError] = useState('')
  const [reportYear, setReportYear] = useState(new Date().getFullYear())
  const [reportGranularity, setReportGranularity] = useState('monthly')
  const [reportRows, setReportRows] = useState([])
  const [reportLoading, setReportLoading] = useState(false)

  const eyebrow = portal === 'admin' ? 'Admin' : 'HR'
  const title = 'Leave Management'

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

  async function reviewLeave(id, status) {
    setProcessing((p) => ({ ...p, [id]: true }))
    setError('')
    try {
      await apiFetch(`/api/v1/leave/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status, review_note: reviewNote[id] || null }),
      })
      setReviewNote((n) => {
        const c = { ...n }
        delete c[id]
        return c
      })
      load()
    } catch (err) {
      setError(err.message || 'Could not update leave status')
    } finally {
      setProcessing((p) => ({ ...p, [id]: false }))
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

  const displayed = tab === 'ALL' ? leaves : leaves.filter((l) => l.status === tab)

  const counts = {
    PENDING: leaves.filter((l) => l.status === 'PENDING').length,
    APPROVED: leaves.filter((l) => l.status === 'APPROVED').length,
    REJECTED: leaves.filter((l) => l.status === 'REJECTED').length,
    ALL: leaves.length,
  }

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', padding: '2rem 1rem' }}>
      <header style={{ marginBottom: 24 }}>
        <p
          style={{
            fontSize: '0.75rem',
            fontWeight: 600,
            color: '#6366f1',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            marginBottom: 4,
          }}
        >
          {eyebrow}
        </p>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>{title}</h1>
        <p style={{ fontSize: '0.875rem', color: '#6b7280', marginTop: 4 }}>
          Review therapist leave requests and export monthly or yearly reports.
        </p>
      </header>

      {error ? (
        <div
          style={{
            background: '#fef2f2',
            border: '1px solid #fca5a5',
            borderRadius: 8,
            padding: '10px 14px',
            marginBottom: 16,
            color: '#b91c1c',
            fontSize: '0.875rem',
          }}
        >
          {error}
        </div>
      ) : null}

      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        {[
          ['review', 'Approvals'],
          ['report', 'Report'],
        ].map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setMainTab(id)}
            style={{
              padding: '8px 18px',
              borderRadius: 8,
              fontWeight: 600,
              fontSize: '0.875rem',
              border: 'none',
              cursor: 'pointer',
              background: mainTab === id ? '#6366f1' : '#f3f4f6',
              color: mainTab === id ? '#fff' : '#374151',
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {mainTab === 'review' ? (
        <>
          <div
            style={{
              display: 'flex',
              gap: 8,
              marginBottom: 20,
              borderBottom: '1px solid #e5e7eb',
              paddingBottom: 12,
              flexWrap: 'wrap',
            }}
          >
            {REVIEW_TABS.map(([val, label]) => (
              <button
                key={val}
                type="button"
                onClick={() => setTab(val)}
                style={{
                  padding: '6px 16px',
                  borderRadius: 20,
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  border: 'none',
                  background: tab === val ? '#6366f1' : '#f3f4f6',
                  color: tab === val ? '#fff' : '#374151',
                }}
              >
                {label} ({counts[val]})
              </button>
            ))}
          </div>

          {loading ? (
            <div style={{ padding: 32, textAlign: 'center', color: '#9ca3af' }}>Loading…</div>
          ) : displayed.length === 0 ? (
            <div
              style={{
                padding: 48,
                textAlign: 'center',
                background: '#fff',
                borderRadius: 12,
                border: '1px solid #e5e7eb',
                color: '#6b7280',
              }}
            >
              <p style={{ fontWeight: 600 }}>No leave requests</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {displayed.map((l) => {
                const sc = STATUS_COLORS[l.status] || STATUS_COLORS.PENDING
                return (
                  <div
                    key={l.id}
                    style={{
                      background: '#fff',
                      border: '1px solid #e5e7eb',
                      borderRadius: 12,
                      padding: '18px 20px',
                    }}
                  >
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
                      <span
                        style={{
                          background: '#eef2ff',
                          color: '#3730a3',
                          fontSize: '0.72rem',
                          fontWeight: 700,
                          padding: '2px 8px',
                          borderRadius: 20,
                        }}
                      >
                        {l.leave_type}
                      </span>
                      <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>
                        {l.therapist_name || `Therapist #${l.therapist_user_id}`}
                      </span>
                      <span style={{ marginLeft: 'auto', fontSize: '0.75rem', color: '#9ca3af' }}>
                        {l.day_count} day{l.day_count === 1 ? '' : 's'}
                      </span>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 10 }}>
                      <div>
                        <p style={{ fontSize: '0.72rem', color: '#9ca3af', marginBottom: 2 }}>From</p>
                        <p style={{ fontWeight: 600, margin: 0 }}>{l.start_date}</p>
                      </div>
                      <div>
                        <p style={{ fontSize: '0.72rem', color: '#9ca3af', marginBottom: 2 }}>To</p>
                        <p style={{ fontWeight: 600, margin: 0 }}>{l.end_date}</p>
                      </div>
                    </div>
                    {l.reason ? (
                      <p style={{ fontSize: '0.8rem', color: '#6b7280', marginBottom: 10 }}>{l.reason}</p>
                    ) : null}
                    {l.review_note ? (
                      <p
                        style={{
                          fontSize: '0.8rem',
                          color: '#6b7280',
                          background: '#f9fafb',
                          padding: '6px 10px',
                          borderRadius: 6,
                        }}
                      >
                        <strong>Review note:</strong> {l.review_note}
                        {l.reviewer_name ? ` (${l.reviewer_name})` : ''}
                      </p>
                    ) : null}

                    {l.status === 'PENDING' && (
                      <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
                        <input
                          value={reviewNote[l.id] || ''}
                          onChange={(e) => setReviewNote((n) => ({ ...n, [l.id]: e.target.value }))}
                          placeholder="Add a review note (optional)…"
                          style={{
                            padding: '7px 12px',
                            borderRadius: 8,
                            border: '1px solid #d1d5db',
                            fontSize: '0.875rem',
                          }}
                        />
                        <div style={{ display: 'flex', gap: 8 }}>
                          <button
                            type="button"
                            onClick={() => reviewLeave(l.id, 'APPROVED')}
                            disabled={processing[l.id]}
                            style={{
                              flex: 1,
                              padding: '8px',
                              background: '#f0fdf4',
                              color: '#15803d',
                              border: '1px solid #86efac',
                              borderRadius: 8,
                              fontWeight: 600,
                              cursor: 'pointer',
                              fontSize: '0.875rem',
                            }}
                          >
                            Approve
                          </button>
                          <button
                            type="button"
                            onClick={() => reviewLeave(l.id, 'REJECTED')}
                            disabled={processing[l.id]}
                            style={{
                              flex: 1,
                              padding: '8px',
                              background: '#fef2f2',
                              color: '#b91c1c',
                              border: '1px solid #fca5a5',
                              borderRadius: 8,
                              fontWeight: 600,
                              cursor: 'pointer',
                              fontSize: '0.875rem',
                            }}
                          >
                            Reject
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </>
      ) : (
        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 20 }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'flex-end', marginBottom: 16 }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.8rem' }}>
              Year
              <select
                value={reportYear}
                onChange={(e) => setReportYear(Number(e.target.value))}
                style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db' }}
              >
                {[reportYear - 1, reportYear, reportYear + 1].map((y) => (
                  <option key={y} value={y}>
                    {y}
                  </option>
                ))}
              </select>
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.8rem' }}>
              View
              <select
                value={reportGranularity}
                onChange={(e) => setReportGranularity(e.target.value)}
                style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db' }}
              >
                <option value="monthly">Monthly</option>
                <option value="yearly">Yearly</option>
              </select>
            </label>
            <button
              type="button"
              onClick={exportCsv}
              style={{
                padding: '8px 16px',
                background: '#6366f1',
                color: '#fff',
                border: 'none',
                borderRadius: 8,
                fontWeight: 600,
                cursor: 'pointer',
                fontSize: '0.875rem',
              }}
            >
              Export CSV
            </button>
          </div>
          {reportLoading ? (
            <p style={{ color: '#9ca3af' }}>Loading report…</p>
          ) : reportRows.length === 0 ? (
            <p style={{ color: '#6b7280' }}>No leave data for this period.</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                <thead>
                  <tr style={{ background: '#f9fafb', textAlign: 'left' }}>
                    {['Therapist', 'Period', 'Type', 'Status', 'Days', 'From', 'To'].map((h) => (
                      <th key={h} style={{ padding: '10px 12px', fontWeight: 600, color: '#6b7280' }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {reportRows.map((r, idx) => (
                    <tr key={`${r.therapist_user_id}-${r.period}-${r.leave_type}-${idx}`} style={{ borderTop: '1px solid #f3f4f6' }}>
                      <td style={{ padding: '10px 12px' }}>{r.therapist_name}</td>
                      <td style={{ padding: '10px 12px' }}>{r.period}</td>
                      <td style={{ padding: '10px 12px' }}>{r.leave_type}</td>
                      <td style={{ padding: '10px 12px' }}>{r.status}</td>
                      <td style={{ padding: '10px 12px' }}>{r.days}</td>
                      <td style={{ padding: '10px 12px' }}>{r.start_date}</td>
                      <td style={{ padding: '10px 12px' }}>{r.end_date}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
