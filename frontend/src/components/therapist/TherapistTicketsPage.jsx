import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { createStaffTicket } from '../../lib/ticketFormUtils.js'
import { PoliciesBotButton } from '../support/PoliciesBotButton.jsx'
import { TicketDetailPanel, loadStaffTicketDetail } from '../support/TicketDetailPanel.jsx'
import { TicketFileInput } from '../support/TicketFileInput.jsx'
import '../support/support-tickets.css'

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
  const [detailLoading, setDetailLoading] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ subject: '', body: '', category: 'OTHER' })
  const [formFiles, setFormFiles] = useState([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  async function loadTickets() {
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
    loadTickets()
  }, [])

  async function openTicket(t) {
    if (activeTicket?.id === t.id) {
      setActiveTicket(null)
      return
    }
    setDetailLoading(true)
    setActiveTicket({ id: t.id })
    try {
      const detail = await loadStaffTicketDetail(t.id)
      setActiveTicket(detail)
    } catch {
      setActiveTicket(t)
    } finally {
      setDetailLoading(false)
    }
  }

  async function createTicket(e) {
    e.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      await createStaffTicket({
        subject: form.subject,
        body: form.body,
        category: form.category,
        files: formFiles,
      })
      setForm({ subject: '', body: '', category: 'OTHER' })
      setFormFiles([])
      setShowForm(false)
      loadTickets()
    } catch (err) {
      setError(err.message || 'Could not create ticket')
    } finally {
      setSubmitting(false)
    }
  }

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
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <PoliciesBotButton />
          <button
            type="button"
            onClick={() => setShowForm(!showForm)}
            style={{ padding: '8px 18px', background: '#6366f1', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 600, fontSize: '0.875rem', cursor: 'pointer' }}
          >
            {showForm ? 'Cancel' : '+ New ticket'}
          </button>
        </div>
      </div>

      {error ? (
        <div style={{ background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 8, padding: '10px 14px', marginBottom: 16, color: '#b91c1c', fontSize: '0.875rem' }}>
          {error}
        </div>
      ) : null}

      {showForm ? (
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
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
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
            <TicketFileInput files={formFiles} onChange={setFormFiles} disabled={submitting} />
            <button
              type="submit"
              disabled={submitting}
              style={{ padding: '10px', background: '#6366f1', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 600, cursor: submitting ? 'not-allowed' : 'pointer', opacity: submitting ? 0.7 : 1 }}
            >
              {submitting ? 'Submitting…' : 'Submit ticket'}
            </button>
          </form>
        </div>
      ) : null}

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
            const expanded = activeTicket?.id === t.id
            return (
              <div
                key={t.id}
                style={{
                  background: '#fff',
                  border: '1px solid #e5e7eb',
                  borderRadius: 12,
                  padding: '16px 20px',
                  boxShadow: expanded ? '0 0 0 2px #6366f1' : 'none',
                }}
              >
                <button
                  type="button"
                  onClick={() => openTicket(t)}
                  style={{ width: '100%', textAlign: 'left', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    <span style={{ background: cc, color: '#374151', fontSize: '0.7rem', fontWeight: 700, padding: '2px 8px', borderRadius: 20 }}>
                      {t.category}
                    </span>
                    <span style={{ background: sc.bg, color: sc.color, fontSize: '0.7rem', fontWeight: 700, padding: '2px 8px', borderRadius: 20 }}>
                      {t.status}
                    </span>
                    {t.attachment_count > 0 ? (
                      <span style={{ fontSize: '0.7rem', color: '#6366f1' }}>{t.attachment_count} file{t.attachment_count !== 1 ? 's' : ''}</span>
                    ) : null}
                    <span style={{ marginLeft: 'auto', fontSize: '0.75rem', color: '#9ca3af' }}>
                      {new Date(t.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  <p style={{ fontWeight: 600, marginBottom: 4 }}>{t.subject}</p>
                  <p style={{ fontSize: '0.8rem', color: '#6b7280', margin: 0 }}>{t.body?.slice(0, 120)}{t.body?.length > 120 ? '…' : ''}</p>
                </button>
                {expanded ? (
                  <div className="ticket-detail-panel">
                    {detailLoading ? (
                      <p style={{ color: '#9ca3af', fontSize: '0.875rem' }}>Loading thread…</p>
                    ) : (
                      <TicketDetailPanel
                        ticket={activeTicket}
                        onUpdated={(updated) => {
                          setActiveTicket(updated)
                          loadTickets()
                        }}
                      />
                    )}
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
