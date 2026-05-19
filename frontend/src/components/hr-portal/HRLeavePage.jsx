import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

const STATUS_COLORS = {
  PENDING: { bg: '#fefce8', color: '#a16207', border: '#fde047' },
  APPROVED: { bg: '#f0fdf4', color: '#15803d', border: '#86efac' },
  REJECTED: { bg: '#fef2f2', color: '#b91c1c', border: '#fca5a5' },
  CANCELLED: { bg: '#f4f4f5', color: '#71717a', border: '#d4d4d8' },
}

export function HRLeavePage() {
  const [leaves, setLeaves] = useState([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('PENDING')
  const [reviewNote, setReviewNote] = useState({})
  const [processing, setProcessing] = useState({})
  const [error, setError] = useState('')

  async function load() {
    setLoading(true)
    try {
      const data = await apiFetch('/api/v1/leave')
      setLeaves(data)
    } catch {
      setLeaves([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  async function reviewLeave(id, status) {
    setProcessing((p) => ({ ...p, [id]: true }))
    setError('')
    try {
      await apiFetch(`/api/v1/leave/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status, review_note: reviewNote[id] || null }),
      })
      setReviewNote((n) => { const c = { ...n }; delete c[id]; return c })
      load()
    } catch (err) {
      setError(err.message || 'Could not update leave status')
    } finally {
      setProcessing((p) => ({ ...p, [id]: false }))
    }
  }

  const displayed = tab === 'ALL' ? leaves : leaves.filter((l) => l.status === tab)

  const counts = {
    PENDING: leaves.filter((l) => l.status === 'PENDING').length,
    APPROVED: leaves.filter((l) => l.status === 'APPROVED').length,
    ALL: leaves.length,
  }

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '2rem 1rem' }}>
      <header style={{ marginBottom: 24 }}>
        <p style={{ fontSize: '0.75rem', fontWeight: 600, color: '#6366f1', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>HR</p>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>Leave Management</h1>
        <p style={{ fontSize: '0.875rem', color: '#6b7280', marginTop: 4 }}>Review and approve therapist leave requests.</p>
      </header>

      {error ? (
        <div style={{ background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 8, padding: '10px 14px', marginBottom: 16, color: '#b91c1c', fontSize: '0.875rem' }}>{error}</div>
      ) : null}

      <div style={{ display: 'flex', gap: 8, marginBottom: 20, borderBottom: '1px solid #e5e7eb', paddingBottom: 12 }}>
        {[['PENDING', `Pending (${counts.PENDING})`], ['APPROVED', `Approved (${counts.APPROVED})`], ['ALL', `All (${counts.ALL})`]].map(([val, label]) => (
          <button key={val} type="button" onClick={() => setTab(val)}
            style={{ padding: '6px 16px', borderRadius: 20, fontSize: '0.8rem', fontWeight: 600, cursor: 'pointer', border: 'none', background: tab === val ? '#6366f1' : '#f3f4f6', color: tab === val ? '#fff' : '#374151' }}>
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ padding: 32, textAlign: 'center', color: '#9ca3af' }}>Loading…</div>
      ) : displayed.length === 0 ? (
        <div style={{ padding: 48, textAlign: 'center', background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb', color: '#6b7280' }}>
          <p style={{ fontWeight: 600 }}>No leave requests</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {displayed.map((l) => {
            const sc = STATUS_COLORS[l.status] || STATUS_COLORS.PENDING
            return (
              <div key={l.id} style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: '18px 20px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                  <span style={{ background: sc.bg, color: sc.color, border: `1px solid ${sc.border}`, fontSize: '0.72rem', fontWeight: 700, padding: '2px 8px', borderRadius: 20 }}>{l.status}</span>
                  <span style={{ background: '#eef2ff', color: '#3730a3', fontSize: '0.72rem', fontWeight: 700, padding: '2px 8px', borderRadius: 20 }}>{l.leave_type}</span>
                  <span style={{ marginLeft: 'auto', fontSize: '0.75rem', color: '#9ca3af' }}>Therapist #{l.therapist_user_id}</span>
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
                {l.reason ? <p style={{ fontSize: '0.8rem', color: '#6b7280', marginBottom: 10 }}>{l.reason}</p> : null}
                {l.review_note ? (
                  <p style={{ fontSize: '0.8rem', color: '#6b7280', background: '#f9fafb', padding: '6px 10px', borderRadius: 6 }}>
                    <strong>Review note:</strong> {l.review_note}
                  </p>
                ) : null}

                {l.status === 'PENDING' && (
                  <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <input
                      value={reviewNote[l.id] || ''}
                      onChange={(e) => setReviewNote((n) => ({ ...n, [l.id]: e.target.value }))}
                      placeholder="Add a review note (optional)…"
                      style={{ padding: '7px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem' }}
                    />
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button type="button"
                        onClick={() => reviewLeave(l.id, 'APPROVED')}
                        disabled={processing[l.id]}
                        style={{ flex: 1, padding: '8px', background: '#f0fdf4', color: '#15803d', border: '1px solid #86efac', borderRadius: 8, fontWeight: 600, cursor: 'pointer', fontSize: '0.875rem' }}>
                        Approve
                      </button>
                      <button type="button"
                        onClick={() => reviewLeave(l.id, 'REJECTED')}
                        disabled={processing[l.id]}
                        style={{ flex: 1, padding: '8px', background: '#fef2f2', color: '#b91c1c', border: '1px solid #fca5a5', borderRadius: 8, fontWeight: 600, cursor: 'pointer', fontSize: '0.875rem' }}>
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
    </div>
  )
}
