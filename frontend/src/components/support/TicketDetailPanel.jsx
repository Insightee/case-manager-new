import { useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { replyStaffTicket } from '../../lib/ticketFormUtils.js'
import { TicketAttachmentList } from './TicketAttachmentList.jsx'
import { TicketFileInput } from './TicketFileInput.jsx'

export async function loadStaffTicketDetail(ticketId) {
  return apiFetch(`/api/v1/tickets/${ticketId}`)
}

async function patchResolved(ticketId) {
  await apiFetch(`/api/v1/tickets/${ticketId}`, {
    method: 'PATCH',
    body: JSON.stringify({ status: 'RESOLVED' }),
  })
}

const STATUS_META = {
  OPEN: { label: 'Open', bg: '#fef3c7', color: '#b45309' },
  IN_PROGRESS: { label: 'In progress', bg: '#dbeafe', color: '#1d4ed8' },
  RESOLVED: { label: 'Resolved — awaiting client acceptance', bg: '#d1fae5', color: '#047857' },
  CLOSED: { label: 'Closed', bg: '#f1f5f9', color: '#64748b' },
}

function StatusPill({ status }) {
  const meta = STATUS_META[status] || STATUS_META.OPEN
  return (
    <span style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', padding: '3px 9px', borderRadius: 6, background: meta.bg, color: meta.color }}>
      {meta.label}
    </span>
  )
}

function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const today = new Date()
  const isToday = d.toDateString() === today.toDateString()
  return isToday
    ? d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
    : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) + ' · ' + d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
}

export function TicketDetailPanel({ ticket, onUpdated, showResolve = false }) {
  const [reply, setReply] = useState('')
  const [replyFiles, setReplyFiles] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  if (!ticket?.messages) {
    return <p style={{ fontSize: '0.875rem', color: '#9ca3af', padding: '12px 0' }}>Loading thread…</p>
  }

  const isClosed = ticket.status === 'RESOLVED' || ticket.status === 'CLOSED'

  async function refreshDetail() {
    const refreshed = await loadStaffTicketDetail(ticket.id)
    onUpdated?.(refreshed)
  }

  async function sendReply(e) {
    e?.preventDefault()
    if (!reply.trim()) return
    setBusy(true)
    setError('')
    try {
      await replyStaffTicket(ticket.id, reply.trim(), replyFiles)
      setReply('')
      setReplyFiles([])
      await refreshDetail()
    } catch (err) {
      setError(err.message || 'Could not send reply')
    } finally {
      setBusy(false)
    }
  }

  async function sendAndResolve() {
    setBusy(true)
    setError('')
    try {
      if (reply.trim()) {
        await replyStaffTicket(ticket.id, reply.trim(), replyFiles)
        setReply('')
        setReplyFiles([])
      }
      await patchResolved(ticket.id)
      await refreshDetail()
    } catch (err) {
      setError(err.message || 'Could not resolve ticket')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="ticket-detail-panel">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <StatusPill status={ticket.status} />
        {ticket.assigned_to_name ? (
          <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>Assigned to {ticket.assigned_to_name}</span>
        ) : null}
        {ticket.escalation_level > 0 ? (
          <span style={{ fontSize: '0.7rem', background: '#fde8d8', color: '#9a3412', fontWeight: 700, padding: '2px 7px', borderRadius: 6 }}>
            Level {ticket.escalation_level} escalation
          </span>
        ) : null}
      </div>

      {/* Ticket-level attachments */}
      {ticket.attachments?.filter((a) => !a.message_id).length > 0 ? (
        <div style={{ marginBottom: 14 }}>
          <p style={{ fontSize: '0.72rem', fontWeight: 600, color: '#64748b', marginBottom: 6 }}>Attachments</p>
          <TicketAttachmentList attachments={ticket.attachments.filter((a) => !a.message_id)} />
        </div>
      ) : null}

      {/* Message thread */}
      <div className="ticket-thread">
        {ticket.messages.map((m) => (
          <div key={m.id} className={`ticket-bubble ${m.is_raiser ? 'ticket-bubble--raiser' : 'ticket-bubble--staff'}`}>
            <div className="ticket-bubble__meta">
              {m.author_name} · {fmtTime(m.created_at)}
            </div>
            <div className="ticket-bubble__body">{m.body}</div>
            {m.attachments?.length > 0 ? (
              <div style={{ marginTop: 6 }}>
                <TicketAttachmentList attachments={m.attachments} />
              </div>
            ) : null}
          </div>
        ))}
      </div>

      {/* Status hint after resolve */}
      {ticket.status === 'RESOLVED' ? (
        <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 10, padding: '10px 14px', fontSize: '0.8rem', color: '#166534', marginBottom: 12 }}>
          <strong>Waiting for client.</strong> The client can accept this resolution to close the ticket, or reply to reopen it.
        </div>
      ) : null}

      {ticket.status === 'CLOSED' ? (
        <div style={{ background: '#f1f5f9', border: '1px solid #e2e8f0', borderRadius: 10, padding: '10px 14px', fontSize: '0.8rem', color: '#475569', marginBottom: 12 }}>
          This ticket is closed. The client accepted the resolution.
          {ticket.parent_satisfaction_rating ? ` Rated ${ticket.parent_satisfaction_rating}/5.` : ''}
        </div>
      ) : null}

      {/* Compose */}
      {!isClosed ? (
        <div className="ticket-compose">
          <textarea
            className="ticket-compose__input"
            placeholder={showResolve ? 'Write a reply or resolution message…' : 'Reply…'}
            value={reply}
            onChange={(e) => setReply(e.target.value)}
            rows={3}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) sendReply(e)
            }}
          />
          <TicketFileInput files={replyFiles} onChange={setReplyFiles} disabled={busy} />
          {error ? <p style={{ color: '#b91c1c', fontSize: '0.78rem', margin: '6px 0 0' }}>{error}</p> : null}
          <div className="ticket-compose__actions">
            <button
              type="button"
              disabled={busy || !reply.trim()}
              onClick={sendReply}
              className="ticket-compose__send"
            >
              {busy ? 'Sending…' : 'Send reply'}
            </button>
            {showResolve ? (
              <button
                type="button"
                disabled={busy}
                onClick={sendAndResolve}
                className="ticket-compose__resolve"
              >
                {reply.trim() ? 'Send & Mark resolved' : 'Mark resolved'}
              </button>
            ) : null}
          </div>
        </div>
      ) : (
        <div className="ticket-compose">
          <p style={{ fontSize: '0.78rem', color: '#94a3b8', padding: '4px 0' }}>This ticket is closed — no further replies.</p>
        </div>
      )}
    </div>
  )
}
