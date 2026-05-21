import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'

/**
 * Shared incident thread panel.
 *
 * Props:
 *   incident       — full incident object with .messages[]
 *   onUpdated(i)   — called with refreshed incident after any mutation
 *   apiBase        — "/api/v1/incidents" (admin/therapist) or "/api/v1/parent/incidents" (client)
 *   canManage      — whether this viewer can change status / resolve
 *   statusFlow     — ['OPEN','INVESTIGATING','RESOLVED','CLOSED']
 */

const STATUS_META = {
  OPEN: { label: 'Open', bg: '#fef3c7', color: '#b45309' },
  INVESTIGATING: { label: 'Investigating', bg: '#dbeafe', color: '#1d4ed8' },
  RESOLVED: { label: 'Resolved', bg: '#d1fae5', color: '#047857' },
  CLOSED: { label: 'Closed', bg: '#f1f5f9', color: '#64748b' },
}

function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const today = new Date()
  return d.toDateString() === today.toDateString()
    ? d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
    : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) +
        ' · ' +
        d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
}

function StatusPill({ status }) {
  const m = STATUS_META[status] || STATUS_META.OPEN
  return (
    <span
      style={{
        fontSize: '0.7rem',
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
        padding: '3px 9px',
        borderRadius: 6,
        background: m.bg,
        color: m.color,
      }}
    >
      {m.label}
    </span>
  )
}

const STAFF_ROLES = new Set(['SUPER_ADMIN', 'ADMIN', 'CASE_MANAGER', 'SUPERVISOR'])

export function IncidentDetailPanel({
  incident,
  onUpdated,
  apiBase = '/api/v1/incidents',
  canManage = false,
}) {
  const { user } = useAuth()
  const [reply, setReply] = useState('')
  const [pendingStatus, setPendingStatus] = useState(incident?.status || 'OPEN')
  const [staffUsers, setStaffUsers] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!canManage) return
    apiFetch('/api/v1/admin/users')
      .then((users) => {
        setStaffUsers(
          users.filter((u) => u.roles?.some((r) => STAFF_ROLES.has(r)) && u.is_active !== false),
        )
      })
      .catch(() => setStaffUsers([]))
  }, [canManage])

  if (!incident) return null

  const isClosed = incident.status === 'CLOSED'

  async function refresh() {
    const fresh = await apiFetch(`${apiBase}/${incident.id}`)
    onUpdated?.(fresh)
  }

  async function sendReply() {
    if (!reply.trim()) return
    setBusy(true)
    setError('')
    try {
      const updated = await apiFetch(`${apiBase}/${incident.id}/messages`, {
        method: 'POST',
        body: JSON.stringify({ body: reply.trim() }),
      })
      setReply('')
      onUpdated?.(updated)
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
      await apiFetch(`/api/v1/incidents/${incident.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ assigned_to_user_id: assigneeId }),
      })
      await refresh()
    } catch (err) {
      setError(err.message || 'Could not update assignee')
    } finally {
      setBusy(false)
    }
  }

  async function sendAndUpdateStatus() {
    setBusy(true)
    setError('')
    try {
      if (reply.trim()) {
        await apiFetch(`${apiBase}/${incident.id}/messages`, {
          method: 'POST',
          body: JSON.stringify({ body: reply.trim() }),
        })
        setReply('')
      }
      await apiFetch(`/api/v1/incidents/${incident.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: pendingStatus }),
      })
      await refresh()
    } catch (err) {
      setError(err.message || 'Could not update incident')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="ticket-detail-panel">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 8, marginBottom: 14 }}>
        <StatusPill status={incident.status} />
        {incident.reporter_name ? (
          <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>Filed by {incident.reporter_name}</span>
        ) : null}
        {canManage ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            <select
              value={incident.assigned_to_user_id ?? ''}
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
            {user?.id && incident.assigned_to_user_id !== user.id ? (
              <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" disabled={busy} onClick={() => patchAssign(user.id)}>
                Take
              </button>
            ) : null}
          </div>
        ) : incident.assigned_to_name ? (
          <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>· Assigned to {incident.assigned_to_name}</span>
        ) : null}
        {incident.case_code ? (
          <span
            style={{
              fontSize: '0.72rem',
              fontWeight: 700,
              background: '#eef2ff',
              color: '#3730a3',
              border: '1px solid #c7d2fe',
              borderRadius: 6,
              padding: '2px 8px',
              fontFamily: 'monospace',
            }}
          >
            {incident.case_code}
            {incident.child_name ? ` · ${incident.child_name}` : ''}
          </span>
        ) : null}
      </div>

      {/* Message thread */}
      <div className="ticket-thread">
        {(incident.messages || []).map((m) => (
          <div
            key={m.id}
            className={`ticket-bubble ${m.is_reporter ? 'ticket-bubble--raiser' : 'ticket-bubble--staff'}`}
          >
            <div className="ticket-bubble__meta">
              {m.author_name} · {fmtTime(m.created_at)}
            </div>
            <div className="ticket-bubble__body">{m.body}</div>
          </div>
        ))}
        {incident.messages?.length === 0 ? (
          <p style={{ fontSize: '0.8rem', color: '#94a3b8' }}>No messages yet.</p>
        ) : null}
      </div>

      {/* Resolved hint */}
      {incident.status === 'RESOLVED' && !canManage ? (
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
          <strong>Marked as resolved by the team.</strong> Reply below if you have further concerns.
        </div>
      ) : null}

      {/* Compose area */}
      {!isClosed ? (
        <div className="ticket-compose">
          <textarea
            className="ticket-compose__input"
            placeholder="Add a message or update…"
            value={reply}
            onChange={(e) => setReply(e.target.value)}
            rows={3}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) sendReply()
            }}
          />
          {error ? (
            <p style={{ color: '#b91c1c', fontSize: '0.78rem', margin: '6px 0 0' }}>{error}</p>
          ) : null}

          <div className="ticket-compose__actions">
            {/* Send reply button — always available for non-closed */}
            <button
              type="button"
              disabled={busy || !reply.trim()}
              onClick={sendReply}
              className="ticket-compose__send"
            >
              {busy ? 'Sending…' : 'Send reply'}
            </button>

            {/* Admin/supervisor: status selector + update button */}
            {canManage ? (
              <>
                <select
                  value={pendingStatus}
                  onChange={(e) => setPendingStatus(e.target.value)}
                  style={{
                    padding: '7px 10px',
                    borderRadius: 8,
                    border: '1px solid #d1d5db',
                    fontSize: '0.8rem',
                    background: '#fff',
                  }}
                >
                  {['OPEN', 'INVESTIGATING', 'RESOLVED', 'CLOSED'].map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  disabled={busy}
                  onClick={sendAndUpdateStatus}
                  className="ticket-compose__resolve"
                >
                  {reply.trim() ? 'Send & Update status' : 'Update status'}
                </button>
              </>
            ) : null}
          </div>
        </div>
      ) : (
        <div className="ticket-compose">
          <p style={{ fontSize: '0.78rem', color: '#94a3b8', padding: '4px 0' }}>
            This incident is closed.
          </p>
        </div>
      )}
    </div>
  )
}
