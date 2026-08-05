import { useEffect, useRef, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'
import { replyStaffTicket } from '../../lib/ticketFormUtils.js'
import { TicketAttachmentList } from './TicketAttachmentList.jsx'
import { formatTimestampDateIN } from '../../lib/datetime.js'
import { TicketFileInput } from './TicketFileInput.jsx'
import { TicketFlowDialog } from './TicketFlowDialog.jsx'
import { TicketEscalatePicker } from './TicketEscalatePicker.jsx'

export async function loadStaffTicketDetail(ticketId) {
  return apiFetch(`/api/v1/tickets/${ticketId}`)
}

const STATUS_META = {
  OPEN: { label: 'Open', bg: '#fef3c7', color: '#b45309' },
  IN_PROGRESS: { label: 'In review', bg: '#dbeafe', color: '#1d4ed8' },
  RESOLVED: { label: 'Resolved', bg: '#d1fae5', color: '#047857' },
  CLOSED: { label: 'Closed', bg: '#f1f5f9', color: '#64748b' },
}

const MIN_MESSAGE_CHARS = 3

function StatusPill({ status }) {
  const meta = STATUS_META[status] || STATUS_META.OPEN
  return (
    <span
      style={{
        fontSize: '0.7rem',
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
        padding: '3px 9px',
        borderRadius: 6,
        background: meta.bg,
        color: meta.color,
      }}
    >
      {meta.label}
    </span>
  )
}

function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const today = new Date()
  const isToday = d.toDateString() === today.toDateString()
  const time = d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
  return isToday ? time : `${formatTimestampDateIN(iso) || ''} · ${time}`
}

function ActionMenu({ label, items, disabled, variant = 'ghost' }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    function onDoc(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        type="button"
        className={variant === 'primary' ? 'ticket-compose__send' : 'admin-btn admin-btn--ghost admin-btn--sm'}
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        {label} ▾
      </button>
      {open ? (
        <div
          role="menu"
          style={{
            position: 'absolute',
            bottom: '100%',
            left: 0,
            marginBottom: 4,
            minWidth: 200,
            maxHeight: 280,
            overflowY: 'auto',
            background: '#fff',
            border: '1px solid #e2e8f0',
            borderRadius: 8,
            boxShadow: '0 8px 24px rgba(15,23,42,0.12)',
            zIndex: 20,
            padding: 4,
          }}
        >
          {items.map((item) => (
            <button
              key={item.key}
              type="button"
              role="menuitem"
              disabled={item.disabled}
              className="admin-btn admin-btn--ghost admin-btn--sm"
              style={{ width: '100%', justifyContent: 'flex-start', marginBottom: 2, textAlign: 'left' }}
              onClick={() => {
                setOpen(false)
                item.onClick()
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function TicketMetaRow({ label, children }) {
  return (
    <div style={{ display: 'flex', gap: 8, fontSize: '0.78rem', lineHeight: 1.4 }}>
      <span style={{ color: '#94a3b8', minWidth: 72, flexShrink: 0 }}>{label}</span>
      <span style={{ color: '#334155' }}>{children}</span>
    </div>
  )
}

function participantLine(p) {
  if (!p) return '—'
  const roles = (p.role_labels || []).join(', ')
  return (
    <>
      <strong>{p.full_name}</strong>
      {p.portal_label ? ` · ${p.portal_label}` : ''}
      {roles ? ` (${roles})` : ''}
      {p.email ? (
        <span style={{ display: 'block', color: '#94a3b8', fontSize: '0.72rem' }}>{p.email}</span>
      ) : null}
    </>
  )
}

export function TicketDetailPanel({ ticket, onUpdated, showResolve = false, apiBase = '/api/v1/tickets' }) {
  const { user } = useAuth()
  const { canManageTickets } = useModuleWrite()
  const isTherapist = user?.roles?.includes('THERAPIST')
  const staffWrite = showResolve && (canManageTickets(ticket?.product_module || 'homecare') || isTherapist)
  const [reply, setReply] = useState('')
  const [replyFiles, setReplyFiles] = useState([])
  const [internalNote, setInternalNote] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [dialog, setDialog] = useState(null)
  const [assignBanner, setAssignBanner] = useState(null)

  const isRaiser = ticket?.is_raiser ?? ticket?.raised_by_user_id === user?.id
  const isTerminal = ticket?.status === 'CLOSED'
  const canReply = ticket?.can_reply !== false && !isTerminal

  const raisedBy = ticket?.raised_by || {
    full_name: ticket?.raised_by_name,
    portal_label: ticket?.raised_by_portal,
    role_labels: ticket?.raised_by_role_labels,
  }
  const assignee = ticket?.assignee || {
    full_name: ticket?.assigned_to_name,
    role_labels: ticket?.assignee_role_labels,
  }

  if (!ticket?.messages) {
    return <p style={{ fontSize: '0.875rem', color: '#9ca3af', padding: '12px 0' }}>Loading thread…</p>
  }

  async function refreshDetail() {
    const refreshed = await apiFetch(`${apiBase}/${ticket.id}`)
    onUpdated?.(refreshed)
  }

  const replyOk = reply.trim().length >= MIN_MESSAGE_CHARS

  async function sendReply(e) {
    e?.preventDefault()
    if (!replyOk) {
      setError(`Please enter at least ${MIN_MESSAGE_CHARS} characters before sending.`)
      return
    }
    setBusy(true)
    setError('')
    try {
      if (staffWrite) {
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

  async function patchTicket(body) {
    setBusy(true)
    setError('')
    try {
      const updated = await apiFetch(`${apiBase}/${ticket.id}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      })
      onUpdated?.(updated)
    } catch (err) {
      setError(err.message || 'Could not update ticket')
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
        body: JSON.stringify({ note, reason: note, ...extra }),
      })
      onUpdated?.(updated)
    } catch (err) {
      setError(err.message || `Could not ${action} ticket`)
    } finally {
      setBusy(false)
    }
  }

  function handleStatusPick(statusKey) {
    if (statusKey === 'CLOSED') {
      setDialog({
        action: 'close',
        title: 'Close ticket',
        description: 'Close this ticket. Add a note for the requester.',
        confirmLabel: 'Close ticket',
        requireNote: true,
        noteLabel: 'Closing note',
      })
      return
    }
    if (statusKey === 'RESOLVED') {
      setDialog({
        action: 'resolve',
        title: 'Mark resolved',
        description: 'The person who raised this ticket can accept or reply to reopen.',
        confirmLabel: 'Mark resolved',
        requireNote: true,
        noteLabel: 'Resolution message',
        notePlaceholder: 'Summarize what was done for the requester…',
      })
      return
    }
    patchTicket({ status: statusKey })
  }

  const statusMenuItems = [
    { key: 'OPEN', label: 'Open', onClick: () => handleStatusPick('OPEN') },
    { key: 'IN_PROGRESS', label: 'In review', onClick: () => handleStatusPick('IN_PROGRESS') },
    { key: 'RESOLVED', label: 'Resolved', onClick: () => handleStatusPick('RESOLVED') },
    { key: 'CLOSED', label: 'Closed', onClick: () => handleStatusPick('CLOSED') },
  ]

  async function handleEscalate(payload) {
    setBusy(true)
    setError('')
    try {
      const updated = await apiFetch(`${apiBase}/${ticket.id}/escalate`, {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      onUpdated?.(updated)
      if (updated?.escalated_to_department_label) {
        setAssignBanner(`Escalated — routed to ${updated.escalated_to_department_label} queue`)
      } else {
        const assigneeName = updated?.assignee?.full_name || updated?.assigned_to_name
        if (assigneeName) setAssignBanner(`Escalated — now assigned to ${assigneeName}`)
      }
    } catch (err) {
      setError(err.message || 'Could not escalate ticket')
      throw err
    } finally {
      setBusy(false)
    }
  }

  async function pickUpTicket() {
    setBusy(true)
    setError('')
    try {
      const updated = await apiFetch(`${apiBase}/${ticket.id}/pick-up`, { method: 'POST' })
      onUpdated?.(updated)
      setAssignBanner('You picked up this ticket from the department queue.')
    } catch (err) {
      setError(err.message || 'Could not pick up ticket')
    } finally {
      setBusy(false)
    }
  }

  const assignedLabel = ticket.escalated_to_department_label
    ? `${ticket.escalated_to_department_label} queue (unassigned)`
    : participantLine(assignee)

  const ticketLevelAttachments = (ticket.attachments || []).filter((a) => !a.message_id)

  return (
    <div className="ticket-detail-panel">
      <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
        <StatusPill status={ticket.status} />
        {ticket.product_module ? (
          <span style={{ fontSize: '0.72rem', color: '#64748b', textTransform: 'capitalize' }}>
            {String(ticket.product_module).replace(/_/g, ' ')}
          </span>
        ) : null}
        {(ticket.escalation_level ?? 0) > 0 ? (
          <span
            style={{
              fontSize: '0.7rem',
              background: '#fde8d8',
              color: '#9a3412',
              fontWeight: 700,
              padding: '2px 7px',
              borderRadius: 6,
            }}
          >
            Escalation L{ticket.escalation_level}
            {ticket.escalation_chain?.[ticket.escalation_level]
              ? ` · ${String(ticket.escalation_chain[ticket.escalation_level]).replace(/_/g, ' ')}`
              : ''}
          </span>
        ) : null}
        {ticket.escalated_to_department_label ? (
          <span
            style={{
              fontSize: '0.7rem',
              background: '#ede9fe',
              color: '#5b21b6',
              fontWeight: 700,
              padding: '2px 7px',
              borderRadius: 6,
            }}
          >
            {ticket.escalated_to_department_label} queue
          </span>
        ) : null}
      </div>

      <div
        style={{
          background: '#f8fafc',
          border: '1px solid #e2e8f0',
          borderRadius: 10,
          padding: '10px 12px',
          marginBottom: 12,
          display: 'grid',
          gap: 6,
        }}
      >
        <TicketMetaRow label="Raised by">{participantLine(raisedBy)}</TicketMetaRow>
        <TicketMetaRow label="Assigned to">{assignedLabel}</TicketMetaRow>
        {ticket.topic_label ? <TicketMetaRow label="Topic">{ticket.topic_label}</TicketMetaRow> : null}
        {ticket.category_label ? <TicketMetaRow label="Category">{ticket.category_label}</TicketMetaRow> : null}
        {ticket.case_code || ticket.child_name ? (
          <TicketMetaRow label="Case">
            {ticket.case_code}
            {ticket.child_name ? ` · ${ticket.child_name}` : ''}
          </TicketMetaRow>
        ) : null}
        <TicketMetaRow label="Created">{ticket.created_at ? fmtTime(ticket.created_at) : '—'}</TicketMetaRow>
      </div>

      {assignBanner ? (
        <div
          style={{
            background: '#eef2ff',
            border: '1px solid #c7d2fe',
            borderRadius: 10,
            padding: '8px 12px',
            fontSize: '0.8rem',
            color: '#3730a3',
            marginBottom: 12,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <span>{assignBanner}</span>
          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setAssignBanner(null)}>
            Dismiss
          </button>
        </div>
      ) : null}

      {ticket.can_pick_up ? (
        <div
          style={{
            background: '#f5f3ff',
            border: '1px solid #ddd6fe',
            borderRadius: 10,
            padding: '10px 12px',
            marginBottom: 12,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 8,
            flexWrap: 'wrap',
          }}
        >
          <span style={{ fontSize: '0.8rem', color: '#5b21b6' }}>
            This ticket is waiting in the <strong>{ticket.escalated_to_department_label}</strong> queue.
          </span>
          <button
            type="button"
            className="admin-btn admin-btn--primary admin-btn--sm"
            disabled={busy}
            onClick={pickUpTicket}
          >
            Pick up ticket
          </button>
        </div>
      ) : null}

      <div className="ticket-thread">
        {ticket.messages.map((m) => {
          const isOwn = m.author_user_id === user?.id
          const bubbleClass = isOwn ? 'ticket-bubble--own' : 'ticket-bubble--other'
          return (
            <div
              key={m.id}
              className={`ticket-bubble ${bubbleClass} ${m.is_internal ? 'ticket-bubble--internal' : ''}`}
            >
              {!isOwn && (
                <span className="ticket-bubble__author">
                  {m.author_name}
                  {m.is_internal ? (
                    <span style={{ marginLeft: 6, fontSize: '0.65rem', fontWeight: 700, color: '#b45309', background: '#fef3c7', padding: '1px 4px', borderRadius: 4 }}>INTERNAL</span>
                  ) : null}
                </span>
              )}
              {isOwn && m.is_internal && (
                <span className="ticket-bubble__author" style={{ color: '#b45309' }}>
                  INTERNAL NOTE
                </span>
              )}
              <div className="ticket-bubble__body">
                {m.body}
                <span className="ticket-bubble__time">{fmtTime(m.created_at)}</span>
              </div>
              {m.attachments?.length > 0 ? (
                <div style={{ marginTop: 6, clear: 'both' }}>
                  <TicketAttachmentList attachments={m.attachments} />
                </div>
              ) : null}
            </div>
          )
        })}
      </div>

      {ticket.status === 'RESOLVED' && isRaiser ? (
        <div
          style={{
            background: '#f0fdf4',
            border: '1px solid #86efac',
            borderRadius: 10,
            padding: '10px 14px',
            fontSize: '0.8rem',
            color: '#166534',
            marginBottom: 12,
          }}
        >
          <strong>Support marked this resolved.</strong> Accept to close, reply to reopen, or escalate.
        </div>
      ) : null}

      {ticket.status === 'RESOLVED' && staffWrite ? (
        <div
          style={{
            background: '#f0fdf4',
            border: '1px solid #86efac',
            borderRadius: 10,
            padding: '10px 14px',
            fontSize: '0.8rem',
            color: '#166534',
            marginBottom: 12,
          }}
        >
          <strong>Waiting for the requester.</strong> They can accept, reply to reopen, or escalate.
        </div>
      ) : null}

      {isTerminal ? (
        <div
          style={{
            background: '#f1f5f9',
            border: '1px solid #e2e8f0',
            borderRadius: 10,
            padding: '10px 14px',
            fontSize: '0.8rem',
            color: '#475569',
            marginBottom: 12,
          }}
        >
          This ticket is closed.
          {ticket.parent_satisfaction_rating ? ` Rated ${ticket.parent_satisfaction_rating}/5.` : ''}
        </div>
      ) : null}

      {isRaiser && !staffWrite && !ticket.has_staff_reply && ticket.status !== 'RESOLVED' ? (
        <p style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: 10 }}>
          Waiting for the first response from support.
        </p>
      ) : null}

      {canReply ? (
        <div className="ticket-compose">
          <textarea
            className="ticket-compose__input"
            placeholder={
              staffWrite
                ? 'Write a reply…'
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
          {staffWrite ? <TicketFileInput files={replyFiles} onChange={setReplyFiles} disabled={busy} /> : null}
          {ticketLevelAttachments.length > 0 ? (
            <div style={{ marginTop: 10 }}>
              <p style={{ fontSize: '0.72rem', fontWeight: 600, color: '#64748b', marginBottom: 6 }}>Ticket attachments</p>
              <TicketAttachmentList attachments={ticketLevelAttachments} />
            </div>
          ) : null}
          {staffWrite && !isTherapist ? (
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.78rem', color: '#64748b', marginTop: 8 }}>
              <input type="checkbox" checked={internalNote} onChange={(e) => setInternalNote(e.target.checked)} />
              Internal note (staff only)
            </label>
          ) : null}
          {error ? (
            <p style={{ color: '#b91c1c', fontSize: '0.78rem', marginTop: 8 }} role="alert">
              {error}
            </p>
          ) : null}

          <div className="ticket-compose__actions" style={{ flexWrap: 'wrap', marginTop: 12, gap: 8, alignItems: 'center' }}>
            {staffWrite ? (
              <>
                <ActionMenu
                  label={`Status: ${STATUS_META[ticket.status]?.label || ticket.status}`}
                  items={statusMenuItems}
                  disabled={busy}
                />
                <TicketEscalatePicker
                  apiBase={apiBase}
                  disabled={busy}
                  busy={busy}
                  canEscalate={ticket.can_escalate_staff || ticket.can_escalate}
                  onEscalate={handleEscalate}
                />
                <button type="button" className="ticket-compose__send" disabled={busy || !replyOk} onClick={sendReply}>
                  {busy ? 'Sending…' : 'Send reply'}
                </button>
              </>
            ) : (
              <>
                {isRaiser && ticket.can_accept ? (
                  <button
                    type="button"
                    disabled={busy}
                    className="ticket-compose__resolve"
                    onClick={() =>
                      setDialog({
                        action: 'close',
                        title: 'Accept resolution & close',
                        description: 'Confirm support addressed your issue.',
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
                        title: 'Escalate',
                        description: 'Escalate for senior review.',
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
                        confirmLabel: 'Close ticket',
                        requireNote: true,
                        noteLabel: 'Closing note',
                      })
                    }
                  >
                    Close…
                  </button>
                ) : null}
                <button type="button" className="ticket-compose__send" disabled={busy || !replyOk} onClick={sendReply}>
                  Send reply
                </button>
              </>
            )}
          </div>
          {canReply && !replyOk && reply.length > 0 ? (
            <p style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: 6 }}>
              Enter at least {MIN_MESSAGE_CHARS} characters to send.
            </p>
          ) : null}
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
          if (dialog?.action === 'resolve') runFlow('resolve', note)
          else if (dialog?.action === 'escalate') runFlow('escalate', note, dialog?.extra || {})
          else if (dialog?.action === 'close') runFlow('close', note, dialog?.extra || {})
        }}
      />
    </div>
  )
}
