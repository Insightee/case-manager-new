import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { createStaffTicket } from '../../lib/ticketFormUtils.js'
import {
  requestTypeByValue,
  THERAPIST_REQUEST_TYPES,
} from '../../lib/therapistTicketOptions.js'
import { formatTimestampDateIN } from '../../lib/datetime.js'
import { PoliciesBotButton } from '../support/PoliciesBotButton.jsx'
import { TicketDetailPanel, loadStaffTicketDetail } from '../support/TicketDetailPanel.jsx'
import { TicketFileInput } from '../support/TicketFileInput.jsx'
import '../support/support-tickets.css'
import '../client-portal/parent-support.css'

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

function topicToRequestType(topic) {
  const match = THERAPIST_REQUEST_TYPES.find((t) => t.topic === topic)
  return match?.value || 'OTHER'
}

export function TherapistTicketsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [tickets, setTickets] = useState([])
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeTicket, setActiveTicket] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [formPanel, setFormPanel] = useState('ticket')
  const [form, setForm] = useState({
    requestType: 'OTHER',
    case_id: '',
    subject: '',
    body: '',
  })
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
    apiFetch('/api/v1/cases?assigned=true&page_size=100')
      .then((data) => setCases(unwrapList(data)))
      .catch(() => setCases([]))
  }, [])

  useEffect(() => {
    const openNew = searchParams.get('new') === '1'
    const topic = searchParams.get('topic')
    const caseId = searchParams.get('case_id') || ''
    if (!openNew && !topic && !caseId) return

    setShowForm(true)
    setFormPanel('ticket')
    setForm((prev) => ({
      ...prev,
      requestType: topic ? topicToRequestType(topic) : prev.requestType,
      case_id: caseId,
    }))
  }, [searchParams])

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

  function clearPrefillParams() {
    const next = new URLSearchParams(searchParams)
    next.delete('new')
    next.delete('topic')
    next.delete('case_id')
    setSearchParams(next, { replace: true })
  }

  async function createTicket(e) {
    e.preventDefault()
    setSubmitting(true)
    setError('')
    setSuccess('')
    const type = requestTypeByValue(form.requestType)
    try {
      await createStaffTicket({
        subject: form.subject,
        body: form.body,
        category: type.category,
        topic: type.topic,
        case_id: form.case_id || undefined,
        files: formFiles,
      })
      setForm({ requestType: 'OTHER', case_id: '', subject: '', body: '' })
      setFormFiles([])
      setShowForm(false)
      clearPrefillParams()
      setSuccess('Ticket submitted. Your case manager or support team will respond in the thread below.')
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
      <section className="parent-support__form-card">
        <div className="parent-support__form-card-head">
          <h2>Raise a new ticket</h2>
          <button
            type="button"
            className="parent-support__form-toggle"
            data-cancel={showForm ? 'true' : undefined}
            style={showForm ? { background: '#f1f5f9', color: '#475569' } : undefined}
            onClick={() => {
              setShowForm((v) => !v)
              setError('')
              setSuccess('')
              if (!showForm) {
                setFormPanel('ticket')
              } else {
                clearPrefillParams()
              }
            }}
          >
            {showForm ? 'Cancel' : '+ New ticket'}
          </button>
        </div>
        <p className="parent-support__hint">
          Choose who should handle your request. Link a case when the concern is about a specific client, or leave
          case blank for general support.
        </p>

        {showForm ? (
          <>
            <nav className="parent-support-hub__tabs parent-support-hub__tabs--inner" aria-label="Ticket actions">
              <button
                type="button"
                className={`parent-support-hub__tab${formPanel === 'ticket' ? ' is-active' : ''}`}
                onClick={() => setFormPanel('ticket')}
              >
                New ticket
              </button>
              <button
                type="button"
                className={`parent-support-hub__tab${formPanel === 'policies' ? ' is-active' : ''}`}
                onClick={() => setFormPanel('policies')}
              >
                Policies bot
              </button>
            </nav>
            {formPanel === 'ticket' ? (
              <form onSubmit={createTicket} className="parent-support__form-body">
                <label className="parent-support__field">
                  Request type
                  <select
                    value={form.requestType}
                    onChange={(e) => setForm({ ...form, requestType: e.target.value })}
                  >
                    {THERAPIST_REQUEST_TYPES.map((t) => (
                      <option key={t.value} value={t.value}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                </label>
                {form.requestType === 'CASE_MANAGER' ? (
                  <p className="parent-support__hint" style={{ margin: '-4px 0 8px' }}>
                    Routed to your case manager when a case is linked; otherwise to the case manager desk.
                  </p>
                ) : null}
                <label className="parent-support__field">
                  Related case (optional)
                  <select
                    value={form.case_id}
                    onChange={(e) => setForm({ ...form, case_id: e.target.value })}
                  >
                    <option value="">No specific case</option>
                    {cases.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.child_name || c.case_code}
                        {c.case_code && c.child_name ? ` · ${c.case_code}` : ''}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="parent-support__field">
                  Subject
                  <input
                    value={form.subject}
                    onChange={(e) => setForm({ ...form, subject: e.target.value })}
                    required
                    placeholder={
                      form.requestType === 'CASE_MANAGER'
                        ? 'e.g. Log review for visit on…'
                        : 'Brief summary'
                    }
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
            ) : (
              <div className="parent-support__policies-panel">
                <p className="parent-support__hint">
                  Ask policy and HR clarification questions through the policies bot when it is enabled for your org.
                </p>
                <PoliciesBotButton />
              </div>
            )}
          </>
        ) : null}

        {error ? <p style={{ color: '#b91c1c', marginTop: 10, fontSize: '0.875rem' }}>{error}</p> : null}
        {success ? <p style={{ color: '#15803d', marginTop: 10, fontSize: '0.875rem' }}>{success}</p> : null}
      </section>

      <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 12 }}>Open tickets ({openTickets.length})</h2>
      {loading ? (
        <p style={{ color: '#94a3b8', fontSize: '0.875rem', marginBottom: 24 }}>Loading…</p>
      ) : openTickets.length === 0 ? (
        <p style={{ color: '#94a3b8', fontSize: '0.875rem', marginBottom: 24 }}>No open tickets.</p>
      ) : (
        openTickets.map((t) => (
          <TicketRow
            key={t.id}
            ticket={t}
            activeTicket={activeTicket}
            detailLoading={detailLoading}
            onOpen={openTicket}
            onUpdated={(updated) => {
              setActiveTicket(updated)
              loadTickets()
            }}
          />
        ))
      )}

      {closedTickets.length > 0 ? (
        <>
          <h2 style={{ fontSize: '1rem', fontWeight: 600, margin: '24px 0 12px' }}>Closed / resolved</h2>
          {closedTickets.map((t) => (
            <TicketRow
              key={t.id}
              ticket={t}
              activeTicket={activeTicket}
              detailLoading={detailLoading}
              onOpen={openTicket}
              onUpdated={(updated) => {
                setActiveTicket(updated)
                loadTickets()
              }}
            />
          ))}
        </>
      ) : null}
    </div>
  )
}

function TicketRow({ ticket: t, activeTicket, detailLoading, onOpen, onUpdated }) {
  const expanded = activeTicket?.id === t.id
  const sc = STATUS_META[t.status] || STATUS_META.OPEN
  const cc = CAT_COLORS[t.category] || CAT_COLORS.OTHER
  const typeLabel = t.topic_label && t.topic !== 'OTHER' ? t.topic_label : t.category

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
            <span
              style={{
                fontSize: '0.68rem',
                fontWeight: 700,
                padding: '2px 8px',
                borderRadius: 20,
                background: cc,
                color: '#374151',
              }}
            >
              {typeLabel}
            </span>
            <span
              style={{
                fontSize: '0.68rem',
                fontWeight: 700,
                padding: '2px 8px',
                borderRadius: 20,
                background: sc.bg,
                color: sc.color,
              }}
            >
              {sc.label}
            </span>
            {t.case_code ? (
              <span style={{ fontSize: '0.7rem', color: '#6366f1', fontWeight: 600 }}>
                {t.child_name ? `${t.child_name} · ` : ''}
                {t.case_code}
              </span>
            ) : null}
            {t.attachment_count > 0 ? (
              <span style={{ fontSize: '0.7rem', color: '#6366f1' }}>
                {t.attachment_count} file{t.attachment_count !== 1 ? 's' : ''}
              </span>
            ) : null}
            <span style={{ marginLeft: 'auto', fontSize: '0.75rem', color: '#9ca3af' }}>
              {formatTimestampDateIN(t.created_at)}
            </span>
          </div>
          <p style={{ margin: '0 0 4px', fontWeight: 600 }}>{t.subject}</p>
          {t.body ? (
            <p style={{ margin: 0, fontSize: '0.8rem', color: '#6b7280' }}>
              {t.body.slice(0, 100)}
              {t.body.length > 100 ? '…' : ''}
            </p>
          ) : null}
        </div>
        <span style={{ color: '#94a3b8', marginLeft: 8 }}>{expanded ? '▲' : '▼'}</span>
      </div>

      {expanded ? (
        <div className="ticket-detail-panel">
          {detailLoading || (activeTicket?.id === t.id && !activeTicket?.messages) ? (
            <p style={{ color: '#9ca3af', fontSize: '0.875rem' }}>Loading thread…</p>
          ) : (
            <TicketDetailPanel ticket={activeTicket} onUpdated={onUpdated} />
          )}
        </div>
      ) : null}
    </div>
  )
}
