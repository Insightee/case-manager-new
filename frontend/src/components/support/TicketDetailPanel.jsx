import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { replyStaffTicket } from '../../lib/ticketFormUtils.js'
import { TicketAttachmentList } from './TicketAttachmentList.jsx'
import { TicketFileInput } from './TicketFileInput.jsx'
import { TicketFlowDialog } from './TicketFlowDialog.jsx'

export async function loadStaffTicketDetail(ticketId) {
  return apiFetch(`/api/v1/tickets/${ticketId}`)
}

const STATUS_META = {
  OPEN: { label: 'Open', bg: '#fef3c7', color: '#b45309' },
  IN_PROGRESS: { label: 'In progress', bg: '#dbeafe', color: '#1d4ed8' },
  RESOLVED: { label: 'Resolved — awaiting your confirmation', bg: '#d1fae5', color: '#047857' },
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

const STAFF_ROLES = new Set(['SUPER_ADMIN', 'ADMIN', 'CASE_MANAGER', 'SUPERVISOR'])

export function TicketDetailPanel({ ticket, onUpdated, showResolve = false, apiBase = '/api/v1/tickets' }) {
  const { user } = useAuth()
  const [reply, setReply] = useState('')
  const [replyFiles, setReplyFiles] = useState([])
  const [internalNote, setInternalNote] = useState(false)
  const [staffUsers, setStaffUsers] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [dialog, setDialog] = useState(null)

  const isRaiser = ticket?.is_raiser ?? ticket?.raised_by_user_id === user?.id
  const isTerminal = ticket?.status === 'CLOSED'
  const canReply = ticket?.can_reply !== false && !isTerminal

  useEffect(() => {
    if (!showResolve) return
    apiFetch('/api/v1/admin/users?page_size=100')
      .then((users) => {
        const list = unwrapList(users)
        setStaffUsers(
          list.filter((u) => u.roles?.some((r) => STAFF_ROLES.has(r)) && u.is_active !== false),
        )
      })
      .catch(() => setStaffUsers([]))
  }, [showResolve])

  if (!ticket?.messages) {
    return <p style={{ fontSize: '0.875rem', color: '#9ca3af', padding: '12px 0' }}>Loading thread…</p>
  }

  async function refreshDetail() {
    const refreshed = await apiFetch(`${apiBase}/${ticket.id}`)
    onUpdated?.(refreshed)
  }

  async function sendReply(e) {
    e?.preventDefault()
    if (!reply.trim()) return
    setBusy(true)
    setError('')
    try {
      if (showResolve) {
        await replyStaffTicket(ticket.id, reply.trim(), replyFiles, { isInternal: internalNote })
      } else {
        await apiFetch(`${apiBase}/${ticket.id}/messages`, {
          method: 'POST',
          body: JSON.stringify({ body: reply.trim() }),
        })
      }
      setReply('')
      setReplyFiles([])
      await refreshDetail()
    } catch (err) {
      setError(err.message || 'Could not send reply')
    } finally {
      setBusy(false)
    }
  }

  async function patchAssign(assigneeId) {
    setBusy(true)
    setError('')
    try {
      const updated = await apiFetch(`${apiBase}/${ticket.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ assigned_to_user_id: assigneeId }),
      })
      onUpdated?.(updated)
    } catch (err) {
      setError(err.message || 'Could not update assignee')
    } finally {
      setBusy(false)
    }
  }

  async function runFlow(action, note, extra = {}) {
    setBusy(true)
    setError('')
    setDialog(null)
    try {
      const updated = await apiFetch(`${apiBase}/${ticket.id}/${action}`, {
        method: 'POST',
        body: JSON.stringify({ note, ...extra }),
      })
      onUpdated?.(updated)
    } catch (err) {
      setError(err.message || `Could not ${action} ticket`)
    } finally {
      setBusy(false)
    }
  }

  async function sendAndResolve(note) {
    setBusy(true)
    setError('')
    setDialog(null)
    try {
      if (reply.trim()) {
        await replyStaffTicket(ticket.id, reply.trim(), replyFiles, { isInternal: internalNote })
        setReply('')
        setReplyFiles([])
      }
      const updated = await apiFetch(`${apiBase}/${ticket.id}/resolve`, {
        method: 'POST',
        body: JSON.stringify({ note: note || reply.trim() || undefined }),
      })
      onUpdated?.(updated)
    } catch (err) {
      setError(err.message || 'Could not resolve ticket')
    } finally {
      setBusy(false)
    }
  }

  const nextRole = ticket.escalation_next_role
    ? String(ticket.escalation_next_role).replace(/_/g, ' ')
    : 'the next level'

  return (
    <div className="ticket-detail-panel">
      <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
        <StatusPill status={ticket.status} />
        {ticket.product_module ? (
          <span style={{ fontSize: '0.72rem', color: '#64748b', textTransform: 'capitalize' }}>
            {String(ticket.product_module).replace(/_/g, ' ')}
          </span>
        ) : null}
        {showResolve ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            <select
              value={ticket.assigned_to_user_id ?? ''}
              onChange={(e) => patchAssign(e.target.value ? Number(e.target.value) : null)}
              disabled={busy}
              style={{ fontSize: '0.78rem', padding: '4px 8px', borderRadius: 8, border: '1px solid #d1d5db' }}
            >
              <option value="">Unassigned</option>
              {staffUsers.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.full_name}
                </option>
              ))}
            </select>
            {user?.id && ticket.assigned_to_user_id !== user.id ? (
              <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" disabled={busy} onClick={() => patchAssign(user.id)}>
                Take
              </button>
            ) : null}
            {ticket.can_escalate || (ticket.escalation_level ?? 0) < (ticket.escalation_max_level ?? 2) ? (
              <button
                type="button"
                className="admin-btn admin-btn--secondary admin-btn--sm"
                disabled={busy}
                onClick={() =>
                  setDialog({
                    action: 'escalate',
                    title: 'Escalate ticket',
                    description: `Route this ticket to ${nextRole} for further review.`,
                    confirmLabel: 'Escalate',
                    requireNote: false,
                    noteLabel: 'Reason (optional)',
                  })
                }
              >
                Escalate
              </button>
            ) : null}
          </div>
        ) : ticket.assigned_to_name ? (
          <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>Assigned to {ticket.assigned_to_name}</span>
        ) : null}
        {(ticket.escalation_level ?? 0) > 0 ? (
          <span style={{ fontSize: '0.7rem', background: '#fde8d8', color: '#9a3412', fontWeight: 700, padding: '2px 7px', borderRadius: 6 }}>
            Level {ticket.escalation_level} · {ticket.escalation_chain?.[ticket.escalation_level] || 'escalated'}
          </span>
        ) : null}
      </div>

      {ticket.attachments?.filter((a) => !a.message_id).length > 0 ? (
        <div style={{ marginBottom: 14 }}>
          <p style={{ fontSize: '0.72rem', fontWeight: 600, color: '#64748b', marginBottom: 6 }}>Attachments</p>
          <TicketAttachmentList attachments={ticket.attachments.filter((a) => !a.message_id)} />
        </div>
      ) : null}

      <div className="ticket-thread">
        {ticket.messages.map((m) => (
          <div
            key={m.id}
            className={`ticket-bubble ${m.is_raiser || m.is_parent ? 'ticket-bubble--raiser' : 'ticket-bubble--staff'}`}
            style={m.is_internal ? { borderLeft: '3px solid #f59e0b', background: '#fffbeb' } : undefined}
          >
            <div className="ticket-bubble__meta">
              {m.author_name} · {fmtTime(m.created_at)}
              {m.is_internal ? (
                <span style={{ marginLeft: 6, fontSize: '0.65rem', fontWeight: 700, color: '#b45309' }}>INTERNAL</span>
              ) : null}
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

      {ticket.status === 'RESOLVED' && isRaiser ? (
        <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 10, padding: '10px 14px', fontSize: '0.8rem', color: '#166534', marginBottom: 12 }}>
          <strong>Support marked this resolved.</strong> Accept to close the ticket, reply to reopen, or escalate if the answer is not satisfactory.
        </div>
      ) : null}

      {ticket.status === 'RESOLVED' && showResolve ? (
        <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 10, padding: '10px 14px', fontSize: '0.8rem', color: '#166534', marginBottom: 12 }}>
          <strong>Waiting for the person who raised this ticket.</strong> They can accept the resolution, reply to reopen, or escalate.
        </div>
      ) : null}

      {isTerminal ? (
        <div style={{ background: '#f1f5f9', border: '1px solid #e2e8f0', borderRadius: 10, padding: '10px 14px', fontSize: '0.8rem', color: '#475569', marginBottom: 12 }}>
          This ticket is closed.
          {ticket.parent_satisfaction_rating ? ` Rated ${ticket.parent_satisfaction_rating}/5.` : ''}
        </div>
      ) : null}

      {isRaiser && !showResolve && !ticket.has_staff_reply && ticket.status !== 'RESOLVED' ? (
        <p style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: 10 }}>
          Waiting for the first response from support. You can escalate after they reply if needed.
        </p>
      ) : null}

      {canReply ? (
        <div className="ticket-compose">
          <textarea
            className="ticket-compose__input"
            placeholder={
              showResolve
                ? 'Write a reply or resolution message…'
                : ticket.status === 'RESOLVED'
                  ? 'Not satisfied? Reply to reopen…'
                  : 'Reply…'
            }
            value={reply}
            onChange={(e) => setReply(e.target.value)}
            rows={3}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) sendReply(e)
            }}
          />
          {showResolve ? <TicketFileInput files={replyFiles} onChange={setReplyFiles} disabled={busy} /> : null}
          {showResolve ? (
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.78rem', color: '#64748b', marginTop: 8 }}>
              <input type="checkbox" checked={internalNote} onChange={(e) => setInternalNote(e.target.checked)} />
              Internal note (staff only)
            </label>
          ) : null}
          {error ? <p style={{ color: '#b91c1c', fontSize: '0.78rem', margin: '6px 0 0' }}>{error}</p> : null}
          <div className="ticket-compose__actions">
            <button type="button" disabled={busy || !reply.trim()} onClick={sendReply} className="ticket-compose__send">
              {busy ? 'Sending…' : 'Send reply'}
            </button>

            {showResolve && ticket.can_resolve ? (
              <button
                type="button"
                disabled={busy}
                onClick={() =>
                  setDialog({
                    action: 'resolve',
                    title: 'Mark ticket resolved',
                    description: 'The person who raised this ticket will be asked to accept or reply. Add an optional resolution message.',
                    confirmLabel: reply.trim() ? 'Send & resolve' : 'Mark resolved',
                    requireNote: false,
                    noteLabel: 'Resolution message (optional)',
                  })
                }
                className="ticket-compose__resolve"
              >
                Mark resolved…
              </button>
            ) : null}

            {showResolve && ticket.can_close_staff ? (
              <button
                type="button"
                disabled={busy}
                className="admin-btn admin-btn--ghost admin-btn--sm"
                onClick={() =>
                  setDialog({
                    action: 'close',
                    title: 'Close ticket',
                    description: 'Close without waiting for acceptance. Use for duplicates or when no further action is needed.',
                    confirmLabel: 'Close ticket',
                    requireNote: true,
                    noteLabel: 'Closing note',
                    notePlaceholder: 'Why this ticket is being closed…',
                  })
                }
              >
                Close…
              </button>
            ) : null}

            {isRaiser && ticket.can_accept ? (
              <button
                type="button"
                disabled={busy}
                className="ticket-compose__resolve"
                onClick={() =>
                  setDialog({
                    action: 'close',
                    title: 'Accept resolution & close',
                    description: 'Confirm that support has addressed your issue. You can add optional feedback.',
                    confirmLabel: 'Accept & close',
                    requireNote: false,
                    noteLabel: 'Feedback (optional)',
                    extra: { accept_resolution: true },
                  })
                }
              >
                Accept & close…
              </button>
            ) : null}

            {isRaiser && ticket.can_escalate ? (
              <button
                type="button"
                disabled={busy}
                className="admin-btn admin-btn--secondary admin-btn--sm"
                onClick={() =>
                  setDialog({
                    action: 'escalate',
                    title: 'Escalate to senior support',
                    description: `Not satisfied with the response? Escalate to ${nextRole}.`,
                    confirmLabel: 'Escalate',
                    requireNote: false,
                    noteLabel: 'What was missing? (optional)',
                  })
                }
              >
                Escalate…
              </button>
            ) : null}

            {isRaiser && ticket.can_close_raiser && !ticket.can_accept ? (
              <button
                type="button"
                disabled={busy}
                className="admin-btn admin-btn--ghost admin-btn--sm"
                onClick={() =>
                  setDialog({
                    action: 'close',
                    title: 'Close ticket',
                    description: 'Close this ticket if you no longer need help (e.g. issue solved another way).',
                    confirmLabel: 'Close ticket',
                    requireNote: true,
                    noteLabel: 'Closing note',
                    notePlaceholder: 'Brief reason for closing…',
                  })
                }
              >
                Close…
              </button>
            ) : null}
          </div>
        </div>
      ) : (
        <p style={{ fontSize: '0.78rem', color: '#94a3b8', padding: '4px 0' }}>This ticket is closed — no further replies.</p>
      )}

      <TicketFlowDialog
        open={!!dialog}
        title={dialog?.title}
        description={dialog?.description}
        confirmLabel={dialog?.confirmLabel}
        requireNote={dialog?.requireNote}
        noteLabel={dialog?.noteLabel}
        notePlaceholder={dialog?.notePlaceholder}
        onCancel={() => setDialog(null)}
        onConfirm={(note) => {
          if (dialog?.action === 'resolve') sendAndResolve(note)
          else if (dialog?.action === 'escalate') runFlow('escalate', note, { reason: note })
          else if (dialog?.action === 'close') runFlow('close', note, dialog?.extra || {})
        }}
      />
    </div>
  )
}
