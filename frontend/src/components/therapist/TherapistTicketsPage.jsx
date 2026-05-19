import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

const CATEGORIES = ['FINANCE', 'HR', 'SERVICE', 'POSH', 'CPP', 'OTHER']

const STATUS_COLORS = {
  OPEN: { bg: '#eff6ff', color: '#1d4ed8' },
  IN_PROGRESS: { bg: '#fefce8', color: '#a16207' },
  RESOLVED: { bg: '#f0fdf4', color: '#15803d' },
  CLOSED: { bg: '#f4f4f5', color: '#71717a' },
}

const CAT_COLORS = {
  FINANCE: '#dbeafe',
  HR: '#fce7f3',
  SERVICE: '#d1fae5',
  POSH: '#fde8d8',
  CPP: '#ede9fe',
  OTHER: '#f3f4f6',
}

export function TherapistTicketsPage() {
  const [tickets, setTickets] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeTicket, setActiveTicket] = useState(null)
  const [messages, setMessages] = useState([])
  const [newMsg, setNewMsg] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ subject: '', body: '', category: 'OTHER' })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  async function loadTickets() {
    setLoading(true)
    try {
      const data = await apiFetch('/api/v1/tickets')
      setTickets(data)
    } catch {
      setTickets([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadTickets() }, [])

  async function createTicket(e) {
    e.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      await apiFetch('/api/v1/tickets', {
        method: 'POST',
        body: JSON.stringify({ subject: form.subject, body: form.body, category: form.category }),
      })
      setForm({ subject: '', body: '', category: 'OTHER' })
      setShowForm(false)
      loadTickets()
    } catch (err) {
      setError(err.message || 'Could not create ticket')
    } finally {
      setSubmitting(false)
    }
  }

  async function sendMessage(e) {
    e.preventDefault()
    if (!newMsg.trim() || !activeTicket) return
    try {
      await apiFetch(`/api/v1/tickets/${activeTicket.id}/messages`, {
        method: 'POST',
        body: JSON.stringify({ body: newMsg }),
      })
      setNewMsg('')
    } catch {}
  }

  const s = (key) => ({ ...panelStyle })

  return (
    <div style={{ maxWidth: 760, margin: '0 auto', padding: '2rem 1rem' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 28, gap: 12, flexWrap: 'wrap' }}>
        <div>
          <p style={{ fontSize: '0.75rem', fontWeight: 600, color: '#6366f1', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
            Support
          </p>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>My Tickets</h1>
          <p style={{ fontSize: '0.875rem', color: '#6b7280', marginTop: 4 }}>Raise and track support requests.</p>
        </div>
        <button
          type="button"
          onClick={() => setShowForm(!showForm)}
          style={{ padding: '8px 18px', background: '#6366f1', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 600, fontSize: '0.875rem', cursor: 'pointer' }}
        >
          {showForm ? 'Cancel' : '+ New ticket'}
        </button>
      </div>

      {error ? (
        <div style={{ background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 8, padding: '10px 14px', marginBottom: 16, color: '#b91c1c', fontSize: '0.875rem' }}>
          {error}
        </div>
      ) : null}

      {showForm && (
        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 24, marginBottom: 20 }}>
          <p style={{ fontWeight: 600, marginBottom: 16 }}>New support ticket</p>
          <form onSubmit={createTicket} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
              Category
              <select
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
                style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem' }}
              >
                {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
              Subject
              <input
                value={form.subject}
                onChange={(e) => setForm({ ...form, subject: e.target.value })}
                required
                style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem' }}
              />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
              Details
              <textarea
                value={form.body}
                onChange={(e) => setForm({ ...form, body: e.target.value })}
                rows={4}
                required
                style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem', resize: 'vertical' }}
              />
            </label>
            <button
              type="submit"
              disabled={submitting}
              style={{ padding: '10px', background: '#6366f1', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 600, cursor: submitting ? 'not-allowed' : 'pointer', opacity: submitting ? 0.7 : 1 }}
            >
              {submitting ? 'Submitting…' : 'Submit ticket'}
            </button>
          </form>
        </div>
      )}

      {loading ? (
        <div style={{ padding: 32, textAlign: 'center', color: '#9ca3af' }}>Loading…</div>
      ) : tickets.length === 0 ? (
        <div style={{ padding: 48, textAlign: 'center', background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb', color: '#6b7280' }}>
          <p style={{ fontWeight: 600, marginBottom: 6 }}>No tickets yet</p>
          <p style={{ fontSize: '0.875rem' }}>Raise a support ticket using the button above.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {tickets.map((t) => {
            const sc = STATUS_COLORS[t.status] || STATUS_COLORS.OPEN
            const cc = CAT_COLORS[t.category] || CAT_COLORS.OTHER
            return (
              <div
                key={t.id}
                onClick={() => setActiveTicket(activeTicket?.id === t.id ? null : t)}
                style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: '16px 20px', cursor: 'pointer', transition: 'box-shadow 0.15s', boxShadow: activeTicket?.id === t.id ? '0 0 0 2px #6366f1' : 'none' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <span style={{ background: cc, color: '#374151', fontSize: '0.7rem', fontWeight: 700, padding: '2px 8px', borderRadius: 20 }}>
                    {t.category}
                  </span>
                  <span style={{ background: sc.bg, color: sc.color, fontSize: '0.7rem', fontWeight: 700, padding: '2px 8px', borderRadius: 20 }}>
                    {t.status}
                  </span>
                  <span style={{ marginLeft: 'auto', fontSize: '0.75rem', color: '#9ca3af' }}>
                    {new Date(t.created_at).toLocaleDateString()}
                  </span>
                </div>
                <p style={{ fontWeight: 600, marginBottom: 4 }}>{t.subject}</p>
                <p style={{ fontSize: '0.8rem', color: '#6b7280', margin: 0 }}>{t.body?.slice(0, 120)}{t.body?.length > 120 ? '…' : ''}</p>

                {activeTicket?.id === t.id && (
                  <div style={{ marginTop: 16, borderTop: '1px solid #e5e7eb', paddingTop: 14 }}>
                    <form onSubmit={sendMessage} style={{ display: 'flex', gap: 8 }}>
                      <input
                        value={newMsg}
                        onChange={(e) => setNewMsg(e.target.value)}
                        placeholder="Add a message…"
                        onClick={(e) => e.stopPropagation()}
                        style={{ flex: 1, padding: '7px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem' }}
                      />
                      <button
                        type="submit"
                        onClick={(e) => e.stopPropagation()}
                        style={{ padding: '7px 14px', background: '#6366f1', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 600, cursor: 'pointer', fontSize: '0.875rem' }}
                      >
                        Send
                      </button>
                    </form>
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
