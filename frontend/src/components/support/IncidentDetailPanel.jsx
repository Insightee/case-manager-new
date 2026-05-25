import { useEffect, useState } from 'react'
import { apiFetch, apiDownload, apiUpload } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { INCIDENT_STATUS_META, PRIORITY_META } from '../../lib/incidentCatalog.js'
import { TicketFlowDialog } from './TicketFlowDialog.jsx'

const FLOW_API = '/api/v1/incidents'

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
  const m = INCIDENT_STATUS_META[status] || INCIDENT_STATUS_META.REPORTED
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

function PriorityPill({ priority }) {
  const m = PRIORITY_META[priority] || PRIORITY_META.NORMAL
  return (
    <span style={{ fontSize: '0.7rem', fontWeight: 700, padding: '3px 8px', borderRadius: 6, background: m.bg, color: m.color }}>
      {m.label}
    </span>
  )
}

const STAFF_ROLES = new Set(['SUPER_ADMIN', 'ADMIN', 'CASE_MANAGER', 'SUPERVISOR', 'HR'])
const STATUS_OPTIONS = ['REPORTED', 'IN_REVIEW', 'ACTION_TAKEN', 'ESCALATED', 'CLOSED']
const TAG_ROLES = ['CASE_MANAGER', 'HR', 'ADMIN']

export function IncidentDetailPanel({
  incident,
  onUpdated,
  apiBase = '/api/v1/incidents',
  canManage = false,
}) {
  const { user } = useAuth()
  const [reply, setReply] = useState('')
  const [pendingStatus, setPendingStatus] = useState(incident?.status || 'REPORTED')
  const [pendingPriority, setPendingPriority] = useState(incident?.priority || 'NORMAL')
  const [actionNote, setActionNote] = useState(incident?.action_taken_note || '')
  const [taggedRoles, setTaggedRoles] = useState(incident?.tagged_roles || [])
  const [staffUsers, setStaffUsers] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [uploadFiles, setUploadFiles] = useState([])
  const [dialog, setDialog] = useState(null)

  useEffect(() => {
    setPendingStatus(incident?.status || 'REPORTED')
    setPendingPriority(incident?.priority || 'NORMAL')
    setActionNote(incident?.action_taken_note || '')
    setTaggedRoles(incident?.tagged_roles || [])
  }, [incident?.id, incident?.status])

  useEffect(() => {
    if (!canManage) return
    apiFetch('/api/v1/admin/users?page_size=100')
      .then((users) => {
        const list = unwrapList(users)
        setStaffUsers(
          list.filter((u) => u.roles?.some((r) => STAFF_ROLES.has(r)) && u.is_active !== false),
        )
      })
      .catch(() => setStaffUsers([]))
  }, [canManage])

  if (!incident) return null

  const isClosed = incident.status === 'CLOSED'
  const patchBase = canManage ? '/api/v1/incidents' : apiBase

  async function refresh() {
    const fresh = await apiFetch(`${apiBase}/${incident.id}`)
    onUpdated?.(fresh)
  }

  async function flowAction(action, note) {
    setBusy(true)
    setError('')
    setDialog(null)
    try {
      const body = action === 'escalate' ? { reason: note } : { note: note || '' }
      const flowBase = canManage ? FLOW_API : apiBase
      const updated = await apiFetch(`${flowBase}/${incident.id}/${action}`, {
        method: 'POST',
        body: JSON.stringify(body),
      })
      onUpdated?.(updated)
    } catch (err) {
      setError(err.message || `Could not ${action} incident`)
    } finally {
      setBusy(false)
    }
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

  async function patchIncident(body) {
    setBusy(true)
    setError('')
    try {
      await apiFetch(`${patchBase}/${incident.id}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      })
      await refresh()
    } catch (err) {
      setError(err.message || 'Could not update incident')
    } finally {
      setBusy(false)
    }
  }

  async function uploadAttachments() {
    if (!uploadFiles.length) return
    setBusy(true)
    setError('')
    try {
      const fd = new FormData()
      uploadFiles.forEach((f) => fd.append('files', f))
      await apiUpload(`${apiBase}/${incident.id}/attachments`, fd)
      setUploadFiles([])
      await refresh()
    } catch (err) {
      setError(err.message || 'Could not upload files')
    } finally {
      setBusy(false)
    }
  }

  function toggleTag(role) {
    const next = taggedRoles.includes(role)
      ? taggedRoles.filter((r) => r !== role)
      : [...taggedRoles, role]
    setTaggedRoles(next)
    patchIncident({ tagged_roles: next })
  }

  return (
    <div className="ticket-detail-panel">
      <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
        {incident.ticket_code ? (
          <span style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: '0.85rem', color: '#0f172a' }}>
            {incident.ticket_code}
          </span>
        ) : null}
        <StatusPill status={incident.status} />
        {incident.priority ? <PriorityPill priority={incident.priority} /> : null}
      </div>

      <p style={{ margin: '0 0 10px', fontWeight: 600, color: '#0f172a' }}>{incident.title}</p>

      <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: 12, display: 'grid', gap: 4 }}>
        {incident.child_name ? <span>Client: {incident.child_name}</span> : null}
        {incident.primary_category ? (
          <span>
            Category: {incident.primary_category}
            {incident.subcategory ? ` · ${incident.subcategory}` : ''}
          </span>
        ) : null}
        {incident.incident_at ? <span>When: {new Date(incident.incident_at).toLocaleString()}</span> : null}
        {incident.location ? <span>Location: {incident.location}</span> : null}
        {incident.child_safe ? <span>Child safe: {incident.child_safe}</span> : null}
        {incident.parent_informed ? <span>Parent informed: {incident.parent_informed}</span> : null}
        {incident.immediate_action ? <span>Immediate action: {incident.immediate_action}</span> : null}
        {incident.primary_owner_role ? <span>Owner role: {incident.primary_owner_role}</span> : null}
        {incident.assigned_to_name ? <span>Assigned: {incident.assigned_to_name}</span> : null}
      </div>

      {canManage ? (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12, alignItems: 'center' }}>
          <select
            value={incident.assigned_to_user_id ?? ''}
            onChange={(e) => patchIncident({ assigned_to_user_id: e.target.value ? Number(e.target.value) : null })}
            disabled={busy}
            style={{ fontSize: '0.78rem', padding: '4px 8px', borderRadius: 8, border: '1px solid #d1d5db' }}
          >
            <option value="">Unassigned</option>
            {staffUsers.map((u) => (
              <option key={u.id} value={u.id}>{u.full_name}</option>
            ))}
          </select>
          <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Tag:</span>
          {TAG_ROLES.map((r) => (
            <button
              key={r}
              type="button"
              className="admin-btn admin-btn--ghost admin-btn--sm"
              style={{
                background: taggedRoles.includes(r) ? '#eef2ff' : undefined,
                borderColor: taggedRoles.includes(r) ? '#6366f1' : undefined,
              }}
              disabled={busy}
              onClick={() => toggleTag(r)}
            >
              {r.replace('_', ' ')}
            </button>
          ))}
        </div>
      ) : null}

      {(incident.attachments || []).length > 0 ? (
        <div style={{ marginBottom: 12 }}>
          <p style={{ fontSize: '0.75rem', fontWeight: 600, margin: '0 0 6px' }}>Attachments</p>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: '0.8rem' }}>
            {incident.attachments.map((a) => (
              <li key={a.id}>
                <button
                  type="button"
                  className="ic-case-sessions__link-btn"
                  onClick={() => apiDownload(`${apiBase}/attachments/${a.id}/download`, a.file_name)}
                >
                  {a.file_name}
                </button>
                {a.note ? <span style={{ color: '#94a3b8' }}> — {a.note}</span> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {!isClosed && !canManage ? (
        <div style={{ marginBottom: 12 }}>
          <input type="file" multiple onChange={(e) => setUploadFiles(Array.from(e.target.files || []))} />
          {uploadFiles.length > 0 ? (
            <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" disabled={busy} onClick={uploadAttachments} style={{ marginTop: 6 }}>
              Upload {uploadFiles.length} file(s)
            </button>
          ) : null}
        </div>
      ) : null}

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
      </div>

      {incident.status === 'ACTION_TAKEN' && !canManage ? (
        <p style={{ fontSize: '0.8rem', color: '#166534', marginBottom: 10 }}>
          Action has been taken. Close when satisfied, reply for follow-up, or escalate if the response was not adequate.
        </p>
      ) : null}

      {incident.status === 'ESCALATED' ? (
        <p style={{ fontSize: '0.8rem', color: '#9a3412', marginBottom: 10 }}>
          Escalated to {incident.escalation_next_role ? String(incident.escalation_next_role).replace(/_/g, ' ') : 'senior review'}.
        </p>
      ) : null}

      {!canManage && !incident.has_staff_reply && !isClosed ? (
        <p style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: 10 }}>
          Waiting for the first response from the team. You can escalate after they reply.
        </p>
      ) : null}

      {!isClosed ? (
        <div className="ticket-compose">
          <textarea
            className="ticket-compose__input"
            placeholder="Add a message…"
            value={reply}
            onChange={(e) => setReply(e.target.value)}
            rows={3}
          />
          {canManage ? (
            <label style={{ display: 'block', marginTop: 8, fontSize: '0.78rem' }}>
              Action taken note {pendingStatus === 'CLOSED' ? '(required to close)' : ''}
              <textarea
                rows={2}
                value={actionNote}
                onChange={(e) => setActionNote(e.target.value)}
                style={{ width: '100%', marginTop: 4 }}
              />
            </label>
          ) : null}
          {error ? <p style={{ color: '#b91c1c', fontSize: '0.78rem' }}>{error}</p> : null}
          <div className="ticket-compose__actions" style={{ flexWrap: 'wrap' }}>
            <button type="button" disabled={busy || !reply.trim()} onClick={sendReply} className="ticket-compose__send">
              Send reply
            </button>
            {canManage ? (
              <>
                <select value={pendingPriority} onChange={(e) => setPendingPriority(e.target.value)} style={{ fontSize: '0.8rem' }}>
                  <option value="NORMAL">Normal</option>
                  <option value="URGENT">Urgent</option>
                  <option value="CRITICAL">Critical</option>
                </select>
                <select value={pendingStatus} onChange={(e) => setPendingStatus(e.target.value)} style={{ fontSize: '0.8rem' }}>
                  {STATUS_OPTIONS.map((s) => (
                    <option key={s} value={s}>{INCIDENT_STATUS_META[s]?.label || s}</option>
                  ))}
                </select>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    patchIncident({
                      status: pendingStatus === 'CLOSED' ? 'ACTION_TAKEN' : pendingStatus,
                      priority: pendingPriority,
                      action_taken_note: actionNote || undefined,
                    })
                  }
                  className="ticket-compose__resolve"
                >
                  Update status
                </button>
                {incident.can_close_staff ? (
                  <button
                    type="button"
                    disabled={busy}
                    className="admin-btn admin-btn--ghost admin-btn--sm"
                    onClick={() =>
                      setDialog({
                        action: 'close',
                        title: 'Close incident',
                        description: 'Record what action was taken and close this report. The reporter will see this in the thread.',
                        confirmLabel: 'Close incident',
                        requireNote: true,
                        noteLabel: 'Action taken note',
                      })
                    }
                  >
                    Close…
                  </button>
                ) : null}
                {incident.can_escalate && canManage ? (
                  <button
                    type="button"
                    disabled={busy}
                    className="admin-btn admin-btn--secondary admin-btn--sm"
                    onClick={() =>
                      setDialog({
                        action: 'escalate',
                        title: 'Escalate incident',
                        description: `Route to ${incident.escalation_next_role ? String(incident.escalation_next_role).replace(/_/g, ' ') : 'the next level'}.`,
                        confirmLabel: 'Escalate',
                        requireNote: false,
                        noteLabel: 'Reason (optional)',
                      })
                    }
                  >
                    Escalate…
                  </button>
                ) : null}
                {!isClosed ? (
                  <>
                    <input type="file" multiple onChange={(e) => setUploadFiles(Array.from(e.target.files || []))} />
                    {uploadFiles.length > 0 ? (
                      <button type="button" disabled={busy} onClick={uploadAttachments}>Upload files</button>
                    ) : null}
                  </>
                ) : null}
              </>
            ) : (
              <>
                {incident.can_close_reporter ? (
                  <button
                    type="button"
                    disabled={busy}
                    className="ticket-compose__resolve"
                    onClick={() =>
                      setDialog({
                        action: 'close',
                        title: 'Close incident report',
                        description: 'Confirm you are satisfied and no further follow-up is needed.',
                        confirmLabel: 'Close report',
                        requireNote: true,
                        noteLabel: 'Closing note',
                        notePlaceholder: 'Brief summary (e.g. issue resolved)…',
                      })
                    }
                  >
                    Close report…
                  </button>
                ) : null}
                {incident.can_escalate ? (
                  <button
                    type="button"
                    disabled={busy}
                    className="admin-btn admin-btn--secondary admin-btn--sm"
                    onClick={() =>
                      setDialog({
                        action: 'escalate',
                        title: 'Escalate incident',
                        description: 'Not satisfied with the team response? Escalate for senior review.',
                        confirmLabel: 'Escalate',
                        requireNote: false,
                        noteLabel: 'What was missing? (optional)',
                      })
                    }
                  >
                    Escalate…
                  </button>
                ) : null}
              </>
            )}
          </div>
        </div>
      ) : (
        <p style={{ fontSize: '0.78rem', color: '#94a3b8' }}>This incident is closed.</p>
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
          if (dialog?.action === 'close') flowAction('close', note)
          else if (dialog?.action === 'escalate') flowAction('escalate', note)
        }}
      />
    </div>
  )
}
