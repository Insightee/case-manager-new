import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { PoliciesBotButton } from '../support/PoliciesBotButton.jsx'
import { TicketDetailPanel, loadStaffTicketDetail } from '../support/TicketDetailPanel.jsx'
import '../support/support-tickets.css'

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
  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState('')

  async function load() {
    setLoading(true)
    try {
      const data = await apiFetch('/api/v1/tickets?page_size=100')
      setTickets(unwrapList(data))
    } catch {
      setTickets([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function openTicket(t) {
    if (activeId === t.id) {
      setActiveId(null)
      setDetail(null)
      return
    }
    setActiveId(t.id)
    setDetailLoading(true)
    try {
      setDetail(await loadStaffTicketDetail(t.id))
    } catch {
      setDetail(null)
    } finally {
      setDetailLoading(false)
    }
  }

  async function onDetailUpdated(updated) {
    setDetail(updated)
    load()
  }

  const filtered = tickets.filter((t) => {
    const q = search.trim().toLowerCase()
    const matchSearch = !q || t.subject?.toLowerCase().includes(q) || t.body?.toLowerCase().includes(q)
    const matchCat = !catFilter || t.category === catFilter
    return matchSearch && matchCat
  })

  return (
    <div style={{ maxWidth: 860, margin: '0 auto', padding: '2rem 1rem' }}>
      <header style={{ marginBottom: 24, display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start' }}>
        <div>
          <p style={{ fontSize: '0.75rem', fontWeight: 600, color: '#6366f1', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>HR</p>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>Support Tickets</h1>
          <p style={{ fontSize: '0.875rem', color: '#6b7280', marginTop: 4 }}>View, clarify, and resolve support tickets.</p>
        </div>
        <PoliciesBotButton />
      </header>

      {error ? (
        <div style={{ background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 8, padding: '10px 14px', marginBottom: 16, color: '#b91c1c', fontSize: '0.875rem' }}>{error}</div>
      ) : null}

      <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search tickets…"
          style={{ flex: 1, minWidth: 200, padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem' }}
        />
        <select
          value={catFilter}
          onChange={(e) => setCatFilter(e.target.value)}
          style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem', background: '#fff' }}
        >
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c || 'All categories'}
            </option>
          ))}
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
              <div
                key={t.id}
                style={{
                  background: '#fff',
                  border: '1px solid #e5e7eb',
                  borderRadius: 12,
                  overflow: 'hidden',
                  boxShadow: isActive ? '0 0 0 2px #6366f1' : 'none',
                }}
              >
                <button
                  type="button"
                  onClick={() => openTicket(t)}
                  style={{ width: '100%', padding: '16px 20px', cursor: 'pointer', textAlign: 'left', background: 'none', border: 'none' }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <span style={{ background: cc, color: '#374151', fontSize: '0.7rem', fontWeight: 700, padding: '2px 8px', borderRadius: 20 }}>{t.category}</span>
                    <span style={{ background: sc.bg, color: sc.color, fontSize: '0.7rem', fontWeight: 700, padding: '2px 8px', borderRadius: 20 }}>{t.status}</span>
                    {t.attachment_count > 0 ? (
                      <span style={{ fontSize: '0.7rem', color: '#6366f1' }}>{t.attachment_count} file(s)</span>
                    ) : null}
                    <span style={{ marginLeft: 'auto', fontSize: '0.75rem', color: '#9ca3af' }}>{new Date(t.created_at).toLocaleDateString()}</span>
                  </div>
                  <p style={{ fontWeight: 600, marginBottom: 4 }}>{t.subject}</p>
                  <p style={{ fontSize: '0.8rem', color: '#6b7280', margin: 0 }}>{t.body?.slice(0, 100)}{t.body?.length > 100 ? '…' : ''}</p>
                </button>

                {isActive ? (
                  <div style={{ padding: '0 20px 16px', borderTop: '1px solid #f3f4f6' }}>
                    {detailLoading ? (
                      <p style={{ color: '#9ca3af', fontSize: '0.875rem', marginTop: 12 }}>Loading thread…</p>
                    ) : detail ? (
                      <TicketDetailPanel
                        ticket={detail}
                        showResolve={detail.status !== 'RESOLVED' && detail.status !== 'CLOSED'}
                        onUpdated={onDetailUpdated}
                      />
                    ) : null}
                  </div>
                ) : null}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
