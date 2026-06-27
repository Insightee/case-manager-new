import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { formatDisplayDateTimeRange } from '../../lib/datetime.js'

export function AbsentNotifications({ listPath = '/api/v1/parent/absence-requests' }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [disputeId, setDisputeId] = useState(null)
  const [disputeComment, setDisputeComment] = useState('')
  const [disputeBusy, setDisputeBusy] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await apiFetch(listPath)
      setItems(data?.items ?? [])
    } catch (err) {
      setError(err.message || 'Could not load absent notifications')
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [listPath])

  useEffect(() => {
    load()
  }, [load])

  async function submitDispute(row) {
    const comment = disputeComment.trim()
    if (!comment) return
    setDisputeBusy(true)
    setError('')
    try {
      await apiFetch(`/api/v1/parent/session-logs/${row.session_id}/dispute`, {
        method: 'POST',
        body: JSON.stringify({ comment }),
      })
      setDisputeId(null)
      setDisputeComment('')
      await load()
    } catch (err) {
      setError(err.message || 'Could not submit dispute')
    } finally {
      setDisputeBusy(false)
    }
  }

  if (loading) {
    return <p style={{ color: '#64748b', fontSize: 14 }}>Loading absent notifications…</p>
  }

  if (!items.length) {
    return (
      <p style={{ color: '#9ca3af', fontSize: 14 }}>
        No recent absent notifications for your child.
      </p>
    )
  }

  return (
    <section style={{ marginTop: 0 }}>
      {error ? (
        <p role="alert" style={{ color: '#b91c1c', fontSize: 14 }}>
          {error}
        </p>
      ) : null}
      <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
        {items.map((row) => {
          const isDisputed = row.dispute_status === 'DISPUTED'
          const showForm = disputeId === row.id
          return (
            <li
              key={row.id}
              style={{
                border: '1px solid #e5e7eb',
                borderRadius: 10,
                padding: 14,
                background: '#fff',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                <div>
                  <p style={{ margin: 0, fontWeight: 600 }}>
                    Child absent
                    {row.child_name ? ` · ${row.child_name}` : ''}
                  </p>
                  <p style={{ margin: '4px 0 0', fontSize: 13, color: '#64748b' }}>
                    {formatDisplayDateTimeRange(row.scheduled_date, row.start_time, row.end_time)}
                    {row.therapist_name ? ` · ${row.therapist_name}` : ''}
                  </p>
                  {row.reason ? (
                    <p style={{ margin: '8px 0 0', fontSize: 13, color: '#475569' }}>{row.reason}</p>
                  ) : null}
                </div>
                {isDisputed ? (
                  <span style={{ color: '#dc2626', fontWeight: 600, fontSize: 13 }}>Disputed</span>
                ) : (
                  <button
                    type="button"
                    className="ic-btn ic-btn--ghost"
                    style={{ borderColor: '#dc2626', color: '#dc2626' }}
                    onClick={() => {
                      setDisputeId(row.id)
                      setDisputeComment('')
                      setError('')
                    }}
                  >
                    Dispute
                  </button>
                )}
              </div>

              {showForm ? (
                <div
                  style={{
                    marginTop: 12,
                    padding: 12,
                    background: '#fef2f2',
                    border: '1px solid #fca5a5',
                    borderRadius: 8,
                  }}
                >
                  <p style={{ margin: '0 0 8px', fontSize: 14, fontWeight: 600, color: '#991b1b' }}>
                    Raise a concern
                  </p>
                  <textarea
                    value={disputeComment}
                    onChange={(e) => setDisputeComment(e.target.value)}
                    rows={3}
                    placeholder="Tell us why your child was not absent…"
                    style={{
                      width: '100%',
                      padding: 8,
                      fontSize: 14,
                      borderRadius: 6,
                      border: '1px solid #d1d5db',
                      marginBottom: 8,
                      background: '#fff',
                    }}
                  />
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button
                      type="button"
                      className="ic-btn ic-btn--primary"
                      style={{ background: '#dc2626', borderColor: '#dc2626' }}
                      disabled={disputeBusy || !disputeComment.trim()}
                      onClick={() => submitDispute(row)}
                    >
                      {disputeBusy ? 'Submitting…' : 'Submit ticket'}
                    </button>
                    <button
                      type="button"
                      className="ic-btn ic-btn--ghost"
                      disabled={disputeBusy}
                      onClick={() => {
                        setDisputeId(null)
                        setDisputeComment('')
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : null}
            </li>
          )
        })}
      </ul>
    </section>
  )
}
