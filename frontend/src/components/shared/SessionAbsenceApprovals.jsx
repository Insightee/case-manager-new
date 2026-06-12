import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { formatDisplayDateTimeRange } from '../../lib/datetime.js'

export function SessionAbsenceApprovals({ listPath, emptyLabel = 'No pending absence requests.' }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [actingId, setActingId] = useState(null)
  const [error, setError] = useState('')
  const [notes, setNotes] = useState({})

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await apiFetch(listPath)
      setItems(data?.items ?? [])
    } catch (err) {
      setError(err.message || 'Could not load absence requests')
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [listPath])

  useEffect(() => {
    load()
  }, [load])

  async function review(id, action) {
    setActingId(id)
    setError('')
    try {
      await apiFetch(`/api/v1/sessions/absence/${id}/${action}`, {
        method: 'POST',
        body: JSON.stringify({ review_note: notes[id]?.trim() || null }),
      })
      await load()
    } catch (err) {
      setError(err.message || 'Action failed')
    } finally {
      setActingId(null)
    }
  }

  if (loading) return <p style={{ color: '#64748b', fontSize: 14 }}>Loading absence requests…</p>
  if (!items.length) return <p style={{ color: '#9ca3af', fontSize: 14 }}>{emptyLabel}</p>

  return (
    <section style={{ marginTop: 16 }}>
      {error ? (
        <p role="alert" style={{ color: '#b91c1c', fontSize: 14 }}>
          {error}
        </p>
      ) : null}
      <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
        {items.map((row) => (
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
                  {row.absence_type === 'CLIENT_ABSENT' ? 'Child absent' : 'Therapist leave'}
                  {row.child_name ? ` · ${row.child_name}` : ''}
                </p>
                <p style={{ margin: '4px 0 0', fontSize: 13, color: '#64748b' }}>
                  {formatDisplayDateTimeRange(row.scheduled_date, row.start_time, row.end_time)}
                  {row.therapist_name ? ` · ${row.therapist_name}` : ''}
                </p>
                {row.reason ? (
                  <p style={{ margin: '8px 0 0', fontSize: 13 }}>{row.reason}</p>
                ) : null}
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                <button
                  type="button"
                  className="ic-btn ic-btn--primary"
                  disabled={actingId === row.id}
                  onClick={() => review(row.id, 'approve')}
                >
                  Approve
                </button>
                <button
                  type="button"
                  className="ic-btn ic-btn--ghost"
                  disabled={actingId === row.id}
                  onClick={() => review(row.id, 'reject')}
                >
                  Decline
                </button>
              </div>
            </div>
            <label style={{ display: 'block', marginTop: 10, fontSize: 13 }}>
              Note (optional)
              <input
                value={notes[row.id] || ''}
                onChange={(e) => setNotes((n) => ({ ...n, [row.id]: e.target.value }))}
                style={{ display: 'block', width: '100%', marginTop: 4, padding: 8 }}
                placeholder="Optional message to therapist"
              />
            </label>
          </li>
        ))}
      </ul>
    </section>
  )
}
