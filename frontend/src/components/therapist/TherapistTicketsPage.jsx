import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { createStaffTicket } from '../../lib/ticketFormUtils.js'
import { PoliciesBotButton } from '../support/PoliciesBotButton.jsx'
import { TicketDetailPanel, loadStaffTicketDetail } from '../support/TicketDetailPanel.jsx'
import { TicketFileInput } from '../support/TicketFileInput.jsx'
import '../support/support-tickets.css'
import '../client-portal/parent-support.css'

const CATEGORIES = ['FINANCE', 'HR', 'SERVICE', 'POSH', 'CPP', 'OTHER']

const STATUS_META = {
  OPEN: { label: 'Open', bg: '#eff6ff', color: '#1d4ed8' },
  IN_PROGRESS: { label: 'In progress', bg: '#fefce8', color: '#a16207' },
  RESOLVED: { label: 'Resolved', bg: '#f0fdf4', color: '#15803d' },
  CLOSED: { label: 'Closed', bg: '#f4f4f5', color: '#71717a' },
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
  const [success, setSuccess] = useState('')

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
    setSuccess('')
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
      setSuccess('Ticket submitted. The team will respond shortly.')
      loadTickets()
    } catch (err) {
      setError(err.message || 'Could not create ticket')
    } finally {
      setSubmitting(false)
    }
  }

  const openTickets = tickets.filter((t) => t.status === 'OPEN' || t.status === 'IN_PROGRESS')
  const closedTickets = tickets.filter((t) => t.status === 'RESOLVED' || t.status === 'CLOSED')

  return (
    <div className="parent-support">
      {/* Form card */}
      <section className="parent-support__form-card">
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 8 }}>
          <h2 style={{ margin: 0 }}>Raise a new ticket</h2>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <PoliciesBotButton />
            <button
              type="button"
              onClick={() => { setShowForm((v) => !v); setError(''); setSuccess('') }}
              style={{ padding: '7px 16px', background: showForm ? '#f1f5f9' : '#6366f1', color: showForm ? '#475569' : '#fff', border: 'none', borderRadius: 8, fontWeight: 600, fontSize: '0.8rem', cursor: 'pointer' }}
            >
              {showForm ? 'Cancel' : '+ New ticket'}
            </button>
          </div>
        </div>
        <p className="parent-support__hint">
          Choose a category so your request reaches the right team. You can track and reply on tickets below.
        </p>

        {showForm ? (
          <form onSubmit={createTicket} style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <label className="parent-support__field">
              Category
              <select
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
              >
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </label>
            <label className="parent-support__field">
              Subject
              <input
                value={form.subject}
                onChange={(e) => setForm({ ...form, subject: e.target.value })}
                required
                placeholder="Brief summary"
              />
            </label>
            <label className="parent-support__field">
              Details
              <textarea
                value={form.body}
                onChange={(e) => setForm({ ...form, body: e.target.value })}
                rows={4}
                required
                placeholder="Describe your concern…"
              />
            </label>
            <TicketFileInput files={formFiles} onChange={setFormFiles} disabled={submitting} />
            <button type="submit" className="parent-support__submit" disabled={submitting}>
              {submitting ? 'Submitting…' : 'Submit ticket'}
            </button>
          </form>
        ) : null}

        {error ? <p style={{ color: '#b91c1c', marginTop: 10, fontSize: '0.875rem' }}>{error}</p> : null}
        {success ? <p style={{ color: '#15803d', marginTop: 10, fontSize: '0.875rem' }}>{success}</p> : null}
      </section>

      {/* Open tickets */}
      <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 12 }}>Open tickets ({openTickets.length})</h2>
      {loading ? (
        <p style={{ color: '#94a3b8', fontSize: '0.875rem', marginBottom: 24 }}>Loading…</p>
      ) : openTickets.length === 0 ? (
        <p style={{ color: '#94a3b8', fontSize: '0.875rem', marginBottom: 24 }}>No open tickets.</p>
      ) : (
        openTickets.map((t) => <TicketRow key={t.id} ticket={t} activeTicket={activeTicket} detailLoading={detailLoading} onOpen={openTicket} onUpdated={(updated) => { setActiveTicket(updated); loadTickets() }} />)
      )}

      {/* Closed tickets */}
      {closedTickets.length > 0 ? (
        <>
          <h2 style={{ fontSize: '1rem', fontWeight: 600, margin: '24px 0 12px' }}>Closed / resolved</h2>
          {closedTickets.map((t) => <TicketRow key={t.id} ticket={t} activeTicket={activeTicket} detailLoading={detailLoading} onOpen={openTicket} onUpdated={(updated) => { setActiveTicket(updated); loadTickets() }} />)}
        </>
      ) : null}
    </div>
  )
}

function TicketRow({ ticket: t, activeTicket, detailLoading, onOpen, onUpdated }) {
  const expanded = activeTicket?.id === t.id
  const sc = STATUS_META[t.status] || STATUS_META.OPEN
  const cc = CAT_COLORS[t.category] || CAT_COLORS.OTHER

  return (
    <div className="parent-support__ticket" style={{ boxShadow: expanded ? '0 0 0 2px #6366f1' : undefined }}>
      <div
        className="parent-support__ticket-head"
        onClick={() => onOpen(t)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && onOpen(t)}
      >
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.68rem', fontWeight: 700, padding: '2px 8px', borderRadius: 20, background: cc, color: '#374151' }}>{t.category}</span>
            <span style={{ fontSize: '0.68rem', fontWeight: 700, padding: '2px 8px', borderRadius: 20, background: sc.bg, color: sc.color }}>{sc.label}</span>
            {t.attachment_count > 0 ? (
              <span style={{ fontSize: '0.7rem', color: '#6366f1' }}>{t.attachment_count} file{t.attachment_count !== 1 ? 's' : ''}</span>
            ) : null}
            <span style={{ marginLeft: 'auto', fontSize: '0.75rem', color: '#9ca3af' }}>
              {new Date(t.created_at).toLocaleDateString()}
            </span>
          </div>
          <p style={{ margin: '0 0 4px', fontWeight: 600 }}>{t.subject}</p>
          {t.body ? (
            <p style={{ margin: 0, fontSize: '0.8rem', color: '#6b7280' }}>{t.body.slice(0, 100)}{t.body.length > 100 ? '…' : ''}</p>
          ) : null}
        </div>
        <span style={{ color: '#94a3b8', marginLeft: 8 }}>{expanded ? '▲' : '▼'}</span>
      </div>

      {expanded ? (
        <div className="ticket-detail-panel">
          {detailLoading || activeTicket?.id === t.id && !activeTicket?.messages ? (
            <p style={{ color: '#9ca3af', fontSize: '0.875rem' }}>Loading thread…</p>
          ) : (
            <TicketDetailPanel ticket={activeTicket} onUpdated={onUpdated} />
          )}
        </div>
      ) : null}
    </div>
  )
}
