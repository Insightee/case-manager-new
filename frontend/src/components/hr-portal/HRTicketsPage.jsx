import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

const CATEGORIES = ['', 'FINANCE', 'HR', 'SERVICE', 'POSH', 'CPP', 'OTHER']

const STATUS_COLORS = {
  OPEN: { bg: '#eff6ff', color: '#1d4ed8' },
  IN_PROGRESS: { bg: '#fefce8', color: '#a16207' },
  RESOLVED: { bg: '#f0fdf4', color: '#15803d' },
  CLOSED: { bg: '#f4f4f5', color: '#71717a' },
}

const CAT_COLORS = {
  FINANCE: '#dbeafe', HR: '#fce7f3', SERVICE: '#d1fae5', POSH: '#fde8d8', CPP: '#ede9fe', OTHER: '#f3f4f6',
}

export function HRTicketsPage() {
  const [tickets, setTickets] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [catFilter, setCatFilter] = useState('')
  const [activeId, setActiveId] = useState(null)
  const [replyText, setReplyText] = useState('')
  const [processing, setProcessing] = useState({})
  const [error, setError] = useState('')

  async function load() {
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

  useEffect(() => { load() }, [])

  async function resolve(id) {
    setProcessing((p) => ({ ...p, [id]: true }))
    setError('')
    try {
      await apiFetch(`/api/v1/tickets/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: 'RESOLVED' }),
      })
      load()
    } catch (err) {
      setError(err.message || 'Could not resolve ticket')
    } finally {
      setProcessing((p) => ({ ...p, [id]: false }))
    }
  }

  async function sendReply(id, e) {
    e.preventDefault()
    if (!replyText.trim()) return
    try {
      await apiFetch(`/api/v1/tickets/${id}/messages`, {
        method: 'POST',
        body: JSON.stringify({ body: replyText }),
      })
      setReplyText('')
    } catch {}
  }

  const filtered = tickets.filter((t) => {
    const q = search.trim().toLowerCase()
    const matchSearch = !q || t.subject?.toLowerCase().includes(q) || t.body?.toLowerCase().includes(q)
    const matchCat = !catFilter || t.category === catFilter
    return matchSearch && matchCat
  })

  return (
    <div style={{ maxWidth: 860, margin: '0 auto', padding: '2rem 1rem' }}>
      <header style={{ marginBottom: 24 }}>
        <p style={{ fontSize: '0.75rem', fontWeight: 600, color: '#6366f1', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>HR</p>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>Support Tickets</h1>
        <p style={{ fontSize: '0.875rem', color: '#6b7280', marginTop: 4 }}>View, clarify, and resolve support tickets.</p>
      </header>

      {error ? <div style={{ background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 8, padding: '10px 14px', marginBottom: 16, color: '#b91c1c', fontSize: '0.875rem' }}>{error}</div> : null}

      <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search tickets…"
          style={{ flex: 1, minWidth: 200, padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem' }} />
        <select value={catFilter} onChange={(e) => setCatFilter(e.target.value)}
          style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem', background: '#fff' }}>
          {CATEGORIES.map((c) => <option key={c} value={c}>{c || 'All categories'}</option>)}
        </select>
      </div>

      {loading ? (
        <div style={{ padding: 32, textAlign: 'center', color: '#9ca3af' }}>Loading…</div>
      ) : filtered.length === 0 ? (
        <div style={{ padding: 48, textAlign: 'center', background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb', color: '#6b7280' }}>
          <p style={{ fontWeight: 600 }}>No tickets found</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {filtered.map((t) => {
            const sc = STATUS_COLORS[t.status] || STATUS_COLORS.OPEN
            const cc = CAT_COLORS[t.category] || CAT_COLORS.OTHER
            const isActive = activeId === t.id
            return (
              <div key={t.id} style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, overflow: 'hidden', boxShadow: isActive ? '0 0 0 2px #6366f1' : 'none' }}>
                <div onClick={() => setActiveId(isActive ? null : t.id)} style={{ padding: '16px 20px', cursor: 'pointer' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <span style={{ background: cc, color: '#374151', fontSize: '0.7rem', fontWeight: 700, padding: '2px 8px', borderRadius: 20 }}>{t.category}</span>
                    <span style={{ background: sc.bg, color: sc.color, fontSize: '0.7rem', fontWeight: 700, padding: '2px 8px', borderRadius: 20 }}>{t.status}</span>
                    <span style={{ marginLeft: 'auto', fontSize: '0.75rem', color: '#9ca3af' }}>{new Date(t.created_at).toLocaleDateString()}</span>
                  </div>
                  <p style={{ fontWeight: 600, marginBottom: 4 }}>{t.subject}</p>
                  <p style={{ fontSize: '0.8rem', color: '#6b7280', margin: 0 }}>{t.body?.slice(0, 100)}{t.body?.length > 100 ? '…' : ''}</p>
                </div>

                {isActive && (
                  <div style={{ padding: '0 20px 16px', borderTop: '1px solid #f3f4f6' }}>
                    <p style={{ fontSize: '0.8rem', color: '#6b7280', marginTop: 12, marginBottom: 10, whiteSpace: 'pre-wrap' }}>{t.body}</p>
                    <form onSubmit={(e) => sendReply(t.id, e)} style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
                      <input value={replyText} onChange={(e) => setReplyText(e.target.value)} placeholder="Add a clarification or reply…"
                        style={{ flex: 1, padding: '7px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem' }} />
                      <button type="submit"
                        style={{ padding: '7px 14px', background: '#6366f1', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 600, cursor: 'pointer', fontSize: '0.875rem' }}>
                        Reply
                      </button>
                    </form>
                    {t.status !== 'RESOLVED' && t.status !== 'CLOSED' && (
                      <button type="button" onClick={() => resolve(t.id)} disabled={processing[t.id]}
                        style={{ fontSize: '0.8rem', padding: '6px 14px', background: '#f0fdf4', color: '#15803d', border: '1px solid #86efac', borderRadius: 8, fontWeight: 600, cursor: 'pointer' }}>
                        Mark as resolved
                      </button>
                    )}
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
