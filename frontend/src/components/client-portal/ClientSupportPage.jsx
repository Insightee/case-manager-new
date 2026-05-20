import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { createParentTicket, replyParentTicket } from '../../lib/ticketFormUtils.js'
import { PoliciesBotButton } from '../support/PoliciesBotButton.jsx'
import { TicketAttachmentList } from '../support/TicketAttachmentList.jsx'
import { TicketFileInput } from '../support/TicketFileInput.jsx'
import '../support/support-tickets.css'
import './parent-support.css'

function statusClass(status) {
  const s = (status || '').toLowerCase()
  if (s === 'open') return 'parent-support__status parent-support__status--open'
  if (s === 'in_progress') return 'parent-support__status parent-support__status--in_progress'
  if (s === 'resolved') return 'parent-support__status parent-support__status--resolved'
  return 'parent-support__status parent-support__status--closed'
}

function TicketThread({ ticket, onRefresh }) {
  const [reply, setReply] = useState('')
  const [replyFiles, setReplyFiles] = useState([])
  const [rate, setRate] = useState(ticket.parent_satisfaction_rating || 0)
  const [rateNote, setRateNote] = useState(ticket.parent_resolution_feedback || '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function sendReply() {
    if (!reply.trim()) return
    setBusy(true)
    setError('')
    try {
      await replyParentTicket(ticket.id, reply.trim(), replyFiles)
      setReply('')
      setReplyFiles([])
      await onRefresh()
    } catch (err) {
      setError(err.message || 'Could not send reply')
    } finally {
      setBusy(false)
    }
  }

  async function escalate() {
    setBusy(true)
    setError('')
    try {
      await apiFetch(`/api/v1/parent/support/tickets/${ticket.id}/escalate`, { method: 'POST' })
      await onRefresh()
    } catch (err) {
      setError(err.message || 'Could not escalate')
    } finally {
      setBusy(false)
    }
  }

  async function accept() {
    setBusy(true)
    try {
      await apiFetch(`/api/v1/parent/support/tickets/${ticket.id}/accept`, {
        method: 'POST',
        body: JSON.stringify({ feedback: rateNote.trim() || undefined }),
      })
      await onRefresh()
    } catch (err) {
      setError(err.message || 'Could not accept resolution')
    } finally {
      setBusy(false)
    }
  }

  async function submitRating() {
    if (!rate) return
    setBusy(true)
    try {
      await apiFetch(`/api/v1/parent/support/tickets/${ticket.id}/rate`, {
        method: 'POST',
        body: JSON.stringify({ rating: rate, feedback: rateNote.trim() || undefined }),
      })
      await onRefresh()
    } catch (err) {
      setError(err.message || 'Could not submit rating')
    } finally {
      setBusy(false)
    }
  }

  const open = ticket.status !== 'CLOSED'

  return (
    <div className="parent-support__thread">
      {/* Ticket-level attachments */}
      {ticket.attachments?.filter((a) => !a.message_id).length > 0 ? (
        <div style={{ marginBottom: 10 }}>
          <p style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748b', margin: '0 0 6px' }}>Attachments</p>
          <TicketAttachmentList attachments={ticket.attachments.filter((a) => !a.message_id)} />
        </div>
      ) : null}

      {/* Message bubbles */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {(ticket.messages || []).map((m) => (
          <div
            key={m.id}
            className={`parent-support__msg ${m.is_parent ? 'parent-support__msg--parent' : 'parent-support__msg--staff'}`}
          >
            <div style={{ fontSize: '0.68rem', color: '#94a3b8', marginBottom: 4 }}>
              {m.author_name} · {new Date(m.created_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
            </div>
            <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{m.body}</div>
            {m.attachments?.length > 0 ? (
              <div style={{ marginTop: 6 }}>
                <TicketAttachmentList attachments={m.attachments} />
              </div>
            ) : null}
          </div>
        ))}
      </div>

      {/* Resolution prompt banner */}
      {ticket.can_accept ? (
        <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 12, padding: '14px 16px', marginTop: 14 }}>
          <p style={{ fontWeight: 700, color: '#166534', fontSize: '0.9rem', margin: '0 0 4px' }}>The care team has resolved your ticket</p>
          <p style={{ fontSize: '0.8rem', color: '#166534', margin: '0 0 12px' }}>
            If the issue is sorted, accept the resolution to close this ticket. Not satisfied? Send a reply and it will reopen for the team.
          </p>
          <button
            type="button"
            className="parent-support__btn parent-support__btn--primary"
            onClick={accept}
            disabled={busy}
            style={{ width: '100%' }}
          >
            {busy ? 'Closing…' : '✓ Accept resolution & close ticket'}
          </button>
        </div>
      ) : null}

      {/* Reply compose */}
      {open ? (
        <div style={{ marginTop: 14 }}>
          <textarea
            className="parent-support__field"
            style={{ width: '100%', minHeight: 72, boxSizing: 'border-box' }}
            placeholder={ticket.status === 'RESOLVED' ? 'Not happy with the resolution? Reply to reopen…' : 'Reply to the care team…'}
            value={reply}
            onChange={(e) => setReply(e.target.value)}
          />
          <TicketFileInput files={replyFiles} onChange={setReplyFiles} disabled={busy} />
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
            <button
              type="button"
              className="parent-support__btn parent-support__btn--primary"
              onClick={sendReply}
              disabled={busy || !reply.trim()}
            >
              {busy ? 'Sending…' : 'Send reply'}
            </button>
            {ticket.can_escalate ? (
              <button type="button" className="parent-support__btn" onClick={escalate} disabled={busy}>
                Escalate (level {(ticket.escalation_level || 0) + 1})
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      {error ? <p style={{ color: '#b91c1c', fontSize: '0.8rem', marginTop: 8 }}>{error}</p> : null}

      {(ticket.can_rate || ticket.parent_satisfaction_rating) && ticket.status !== 'OPEN' ? (
        <div style={{ marginTop: 16 }}>
          <p style={{ fontSize: '0.8125rem', fontWeight: 600, marginBottom: 8 }}>Rate support</p>
          <div style={{ display: 'flex', gap: 6 }}>
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                key={n}
                type="button"
                className="parent-support__star"
                style={{ width: 32, height: 32 }}
                onClick={() => setRate(n)}
                disabled={!!ticket.parent_satisfaction_rating}
              >
                ★
              </button>
            ))}
          </div>
          <textarea
            style={{ width: '100%', marginTop: 8, padding: 8, borderRadius: 8, border: '1px solid #cbd5e1' }}
            placeholder="Optional feedback on how we handled this"
            value={rateNote}
            onChange={(e) => setRateNote(e.target.value)}
            disabled={!!ticket.parent_satisfaction_rating}
          />
          {!ticket.parent_satisfaction_rating ? (
            <button type="button" className="parent-support__btn" onClick={submitRating} disabled={busy || !rate}>
              Submit rating
            </button>
          ) : (
            <p style={{ fontSize: '0.8rem', color: '#15803d' }}>Rated {ticket.parent_satisfaction_rating}/5</p>
          )}
        </div>
      ) : null}
    </div>
  )
}

export function ClientSupportPage({ cases = [] }) {
  const [portalInfo, setPortalInfo] = useState(null)
  const [tickets, setTickets] = useState([])
  const [expandedId, setExpandedId] = useState(null)
  const [topic, setTopic] = useState('OTHER')
  const [subject, setSubject] = useState('')
  const [message, setMessage] = useState('')
  const [caseId, setCaseId] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [newFiles, setNewFiles] = useState([])

  const loadTickets = useCallback(async () => {
    try {
      const rows = await apiFetch('/api/v1/parent/support/tickets')
      setTickets(rows || [])
    } catch {
      setTickets([])
    }
  }, [])

  useEffect(() => {
    apiFetch('/api/v1/parent/portal-info').then(setPortalInfo).catch(() => setPortalInfo(null))
    loadTickets()
  }, [loadTickets])

  const caseOptions = useMemo(() => {
    const map = new Map()
    for (const c of cases) {
      if (!map.has(c.childName)) map.set(c.childName, c)
    }
    return [...map.values()]
  }, [cases])

  const openTickets = tickets.filter((t) => t.status === 'OPEN' || t.status === 'IN_PROGRESS')
  const closedTickets = tickets.filter((t) => t.status === 'RESOLVED' || t.status === 'CLOSED')

  async function handleSubmit(e) {
    e.preventDefault()
    if (!subject.trim() || !message.trim()) return
    setSubmitting(true)
    setError('')
    setSuccess('')
    try {
      const created = await createParentTicket({
        subject: subject.trim(),
        message: message.trim(),
        case_id: caseId ? Number(caseId) : undefined,
        topic,
        files: newFiles,
      })
      setSuccess('Request submitted. Our team will respond based on the topic you selected.')
      setSubject('')
      setMessage('')
      setCaseId('')
      setNewFiles([])
      setExpandedId(created.id)
      await loadTickets()
    } catch (err) {
      setError(err.message || 'Could not submit request')
    } finally {
      setSubmitting(false)
    }
  }

  async function loadTicketDetail(id) {
    const detail = await apiFetch(`/api/v1/parent/support/tickets/${id}`)
    setTickets((prev) => prev.map((t) => (t.id === id ? { ...t, ...detail, messages: detail.messages } : t)))
  }

  async function toggleTicket(id) {
    if (expandedId === id) {
      setExpandedId(null)
      return
    }
    setExpandedId(id)
    await loadTicketDetail(id)
  }

  const topics = portalInfo?.ticket_topics || [
    { id: 'BILLING_PAYMENT', label: 'Billing / payment' },
    { id: 'THERAPIST', label: 'Therapist related' },
    { id: 'CASE_MANAGER', label: 'Case manager' },
    { id: 'OTHER', label: 'Other' },
  ]

  return (
    <div className="parent-support">
      <section id="parent-support-form" className="parent-support__form-card">
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 8 }}>
          <h2 style={{ margin: 0 }}>Raise a new ticket</h2>
          <PoliciesBotButton policiesBotUrl={portalInfo?.policies_bot_url} />
        </div>
        <p className="parent-support__hint">
          Choose a topic so your request goes to the right team. You can reply, escalate, and rate resolution on open
          tickets below.
        </p>
        <form onSubmit={handleSubmit}>
          <div className="parent-support__field">
            Topic
            <div className="parent-support__topics">
              {topics.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  className={`parent-support__topic ${topic === t.id ? 'is-selected' : ''}`}
                  onClick={() => setTopic(t.id)}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {caseOptions.length > 0 ? (
            <label className="parent-support__field">
              Child (optional)
              <select value={caseId} onChange={(e) => setCaseId(e.target.value)}>
                <option value="">Not linked to a specific child</option>
                {caseOptions.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.childName} · {c.serviceType} ({c.caseId})
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          <label className="parent-support__field">
            Subject
            <input value={subject} onChange={(e) => setSubject(e.target.value)} required placeholder="Brief summary" />
          </label>
          <label className="parent-support__field">
            Details
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              required
              placeholder="Describe your concern…"
            />
          </label>
          <TicketFileInput files={newFiles} onChange={setNewFiles} disabled={submitting} />
          <button type="submit" className="parent-support__submit" disabled={submitting}>
            {submitting ? 'Submitting…' : 'Submit ticket'}
          </button>
        </form>
        {error ? <p style={{ color: '#b91c1c', marginTop: 12, fontSize: '0.875rem' }}>{error}</p> : null}
        {success ? <p style={{ color: '#15803d', marginTop: 12, fontSize: '0.875rem' }}>{success}</p> : null}
      </section>

      {portalInfo?.escalation_matrix ? (
        <details className="parent-support__matrix">
          <summary>Escalation levels (how tickets are routed)</summary>
          <ul style={{ margin: '8px 0 0', paddingLeft: 18 }}>
            {Object.entries(portalInfo.escalation_matrix).map(([key, val]) => (
              <li key={key} style={{ marginBottom: 6 }}>
                <strong>{topics.find((t) => t.id === key)?.label || key}:</strong>{' '}
                {(val.levels || []).join(' → ')}
              </li>
            ))}
          </ul>
          <p style={{ marginTop: 8, fontStyle: 'italic' }}>
            Use the Policies bot above for quick policy clarifications before opening a ticket.
          </p>
        </details>
      ) : null}

      <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 12 }}>Open tickets ({openTickets.length})</h2>
      {openTickets.length === 0 ? (
        <p style={{ color: '#94a3b8', fontSize: '0.875rem', marginBottom: 24 }}>No open tickets.</p>
      ) : (
        openTickets.map((t) => (
          <div key={t.id} className="parent-support__ticket">
            <div className="parent-support__ticket-head" onClick={() => toggleTicket(t.id)} role="button" tabIndex={0}>
              <div>
                <span className={statusClass(t.status)}>{t.status.replace('_', ' ')}</span>
                <p style={{ margin: '8px 0 4px', fontWeight: 600 }}>{t.subject}</p>
                <p style={{ margin: 0, fontSize: '0.8rem', color: '#64748b' }}>
                  {t.topic_label}
                  {t.child_name ? ` · ${t.child_name}` : ''}
                  {t.assigned_to_name ? ` · ${t.assigned_to_name}` : ''}
                </p>
              </div>
              <span style={{ color: '#94a3b8' }}>{expandedId === t.id ? '▲' : '▼'}</span>
            </div>
            {expandedId === t.id ? <TicketThread ticket={t} onRefresh={() => loadTicketDetail(t.id)} /> : null}
          </div>
        ))
      )}

      {closedTickets.length > 0 ? (
        <>
          <h2 style={{ fontSize: '1rem', fontWeight: 600, margin: '24px 0 12px' }}>Closed / resolved</h2>
          {closedTickets.map((t) => (
            <div key={t.id} className="parent-support__ticket">
              <div className="parent-support__ticket-head" onClick={() => toggleTicket(t.id)} role="button" tabIndex={0}>
                <div>
                  <span className={statusClass(t.status)}>{t.status}</span>
                  <p style={{ margin: '8px 0 4px', fontWeight: 600 }}>{t.subject}</p>
                  <p style={{ margin: 0, fontSize: '0.8rem', color: '#64748b' }}>{t.topic_label}</p>
                </div>
                <span style={{ color: '#94a3b8' }}>{expandedId === t.id ? '▲' : '▼'}</span>
              </div>
              {expandedId === t.id ? <TicketThread ticket={t} onRefresh={() => loadTicketDetail(t.id)} /> : null}
            </div>
          ))}
        </>
      ) : null}

      <footer className="parent-support__footer">
        <p>
          <strong>Insighte support</strong>
          {portalInfo?.office_address ? ` · ${portalInfo.office_address}` : ''}
        </p>
        <div className="parent-support__footer-links">
          {portalInfo?.support_email ? (
            <a href={`mailto:${portalInfo.support_email}`}>{portalInfo.support_email}</a>
          ) : null}
          {portalInfo?.support_phone ? <a href={`tel:${portalInfo.support_phone}`}>{portalInfo.support_phone}</a> : null}
          {portalInfo?.grievance_policy_url ? (
            <a href={portalInfo.grievance_policy_url} target="_blank" rel="noreferrer">
              Grievance policy
            </a>
          ) : null}
        </div>
      </footer>
    </div>
  )
}
