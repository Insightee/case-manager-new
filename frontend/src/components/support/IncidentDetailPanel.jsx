import { useEffect, useMemo, useRef, useState } from 'react'
import { apiFetch, apiDownload, apiUpload } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { INCIDENT_STATUS_META, PRIORITY_META } from '../../lib/incidentCatalog.js'
import { TicketFlowDialog } from './TicketFlowDialog.jsx'

const FLOW_API = '/api/v1/incidents'

const TAG_GROUPS = [
  { role: 'CASE_MANAGER', label: 'Case manager', matchRoles: ['CASE_MANAGER', 'SUPERVISOR'] },
  { role: 'HR', label: 'HR', matchRoles: ['HR'] },
  { role: 'ADMIN', label: 'Admin', matchRoles: ['MODULE_ADMIN', 'SUPER_ADMIN', 'ADMIN'] },
]

const STAFF_ROLES = new Set(['SUPER_ADMIN', 'ADMIN', 'MODULE_ADMIN', 'CASE_MANAGER', 'SUPERVISOR', 'HR'])
const STATUS_MENU = ['REPORTED', 'IN_REVIEW', 'ACTION_TAKEN', 'ESCALATED', 'CLOSED']
const PRIORITIES = ['NORMAL', 'URGENT', 'CRITICAL']
const MIN_MESSAGE_CHARS = 3

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
            minWidth: 160,
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
              style={{ width: '100%', justifyContent: 'flex-start', marginBottom: 2 }}
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

function userInTagGroup(user, group) {
  return user.roles?.some((r) => group.matchRoles.includes(r))
}

export function IncidentDetailPanel({
  incident,
  onUpdated,
  apiBase = '/api/v1/incidents',
  canManage = false,
}) {
  const [reply, setReply] = useState('')
  const [actionNote, setActionNote] = useState(incident?.action_taken_note || '')
  const [taggedUserIds, setTaggedUserIds] = useState(incident?.tagged_user_ids || [])
  const [staffUsers, setStaffUsers] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [uploadFiles, setUploadFiles] = useState([])
  const [dialog, setDialog] = useState(null)
  const [tagRole, setTagRole] = useState(null)
  const [tagBanner, setTagBanner] = useState(null)
  const [assignBanner, setAssignBanner] = useState(null)
  const [pendingOwnerId, setPendingOwnerId] = useState(null)

  useEffect(() => {
    setActionNote(incident?.action_taken_note || '')
    setTaggedUserIds(incident?.tagged_user_ids || [])
  }, [incident?.id, incident?.status, incident?.tagged_user_ids])

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

  const taggedUsersDisplay = useMemo(() => {
    const fromApi = incident?.tagged_users || []
    if (fromApi.length) return fromApi
    return staffUsers.filter((u) => taggedUserIds.includes(u.id))
  }, [incident?.tagged_users, staffUsers, taggedUserIds])

  if (!incident) return null

  const isClosed = incident.status === 'CLOSED'
  const patchBase = canManage ? '/api/v1/incidents' : apiBase
  const replyOk = reply.trim().length >= MIN_MESSAGE_CHARS
  const tagGroup = tagRole ? TAG_GROUPS.find((g) => g.role === tagRole) : null
  const tagRoleUsers = tagGroup ? staffUsers.filter((u) => userInTagGroup(u, tagGroup)) : []

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
    if (!replyOk) {
      setError(`Please enter at least ${MIN_MESSAGE_CHARS} characters before sending.`)
      return
    }
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

  function rolesFromUserIds(ids) {
    return TAG_GROUPS.filter((g) =>
      staffUsers.some((u) => ids.includes(u.id) && userInTagGroup(u, g)),
    ).map((g) => g.role)
  }

  async function applyTaggedUserIds(nextIds, taggedName) {
    const unique = [...new Set(nextIds)]
    setTaggedUserIds(unique)
    setBusy(true)
    setError('')
    try {
      await apiFetch(`${patchBase}/${incident.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          tagged_user_ids: unique,
          tagged_roles: rolesFromUserIds(unique),
        }),
      })
      await refresh()
      if (taggedName) setTagBanner(`Tagged ${taggedName}`)
      setTagRole(null)
    } catch (err) {
      setError(err.message || 'Could not update tags')
    } finally {
      setBusy(false)
    }
  }

  function tagPerson(user, group) {
    if (taggedUserIds.includes(user.id)) {
      setTagBanner(`${user.full_name} is already tagged`)
      setTagRole(null)
      return
    }
    applyTaggedUserIds([...taggedUserIds, user.id], user.full_name)
  }

  async function assignOwner(userId) {
    setBusy(true)
    setError('')
    try {
      await apiFetch(`${patchBase}/${incident.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ assigned_to_user_id: userId }),
      })
      await refresh()
      const name = staffUsers.find((u) => u.id === userId)?.full_name || 'team member'
      setAssignBanner(userId ? `Assigned to ${name}` : 'Incident unassigned')
      setPendingOwnerId(null)
    } catch (err) {
      setError(err.message || 'Could not assign owner')
    } finally {
      setBusy(false)
    }
  }

  function handleStatusPick(statusKey) {
    if (statusKey === 'CLOSED') {
      setDialog({
        action: 'close',
        title: 'Close incident',
        description: 'Record what action was taken and close this report.',
        confirmLabel: 'Close incident',
        requireNote: true,
        noteLabel: 'Closing note',
        notePlaceholder: 'Describe the action taken…',
      })
      return
    }
    if (statusKey === 'ESCALATED') {
      setDialog({
        action: 'escalate',
        title: 'Escalate incident',
        description: `Route to ${incident.escalation_next_role ? String(incident.escalation_next_role).replace(/_/g, ' ') : 'the next level'}.`,
        confirmLabel: 'Escalate',
        requireNote: false,
        noteLabel: 'Reason (optional)',
      })
      return
    }
    if (statusKey === 'ACTION_TAKEN') {
      const note = actionNote.trim()
      if (note.length < MIN_MESSAGE_CHARS) {
        setError(`Add an action taken note (at least ${MIN_MESSAGE_CHARS} characters) before updating status.`)
        return
      }
      patchIncident({ status: statusKey, action_taken_note: note })
      return
    }
    patchIncident({ status: statusKey })
  }

  const priorityMenuItems = PRIORITIES.map((p) => ({
    key: p,
    label: PRIORITY_META[p]?.label || p,
    onClick: () => patchIncident({ priority: p }),
  }))

  const statusMenuItems = STATUS_MENU.map((s) => ({
    key: s,
    label: INCIDENT_STATUS_META[s]?.label || s,
    disabled: s === 'ESCALATED' && !incident.can_escalate && canManage,
    onClick: () => handleStatusPick(s),
  }))

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
        {incident.assigned_to_name ? <span>Assigned owner: {incident.assigned_to_name}</span> : null}
      </div>

      {taggedUsersDisplay.length > 0 ? (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
          <span style={{ fontSize: '0.72rem', color: '#64748b', alignSelf: 'center' }}>Tagged:</span>
          {taggedUsersDisplay.map((u) => (
            <span
              key={u.id}
              className="admin-chip"
              style={{ fontSize: '0.72rem', display: 'inline-flex', alignItems: 'center', gap: 4 }}
            >
              {u.full_name}
              {canManage ? (
                <button
                  type="button"
                  aria-label={`Remove ${u.full_name}`}
                  style={{ border: 'none', background: 'none', cursor: 'pointer', padding: 0, lineHeight: 1 }}
                  disabled={busy}
                  onClick={() => applyTaggedUserIds(taggedUserIds.filter((id) => id !== u.id))}
                >
                  ×
                </button>
              ) : null}
            </span>
          ))}
        </div>
      ) : null}

      {tagBanner ? (
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
            gap: 8,
          }}
        >
          <span>{tagBanner}</span>
          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setTagBanner(null)}>
            Dismiss
          </button>
        </div>
      ) : null}

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
            gap: 8,
          }}
        >
          <span>{assignBanner}</span>
          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setAssignBanner(null)}>
            Dismiss
          </button>
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
              Action taken note (required when setting status to Action taken)
              <textarea
                rows={2}
                value={actionNote}
                onChange={(e) => setActionNote(e.target.value)}
                style={{ width: '100%', marginTop: 4 }}
                placeholder="Describe what action was taken…"
              />
            </label>
          ) : null}
          {canManage && !isClosed ? (
            <div style={{ marginTop: 8 }}>
              <input type="file" multiple onChange={(e) => setUploadFiles(Array.from(e.target.files || []))} />
              {uploadFiles.length > 0 ? (
                <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" disabled={busy} onClick={uploadAttachments} style={{ marginTop: 6 }}>
                  Upload {uploadFiles.length} file(s)
                </button>
              ) : null}
            </div>
          ) : null}
          {error ? <p style={{ color: '#b91c1c', fontSize: '0.78rem', marginTop: 8 }} role="alert">{error}</p> : null}

          {canManage && tagRole ? (
            <div
              style={{
                marginTop: 12,
                padding: 12,
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
                borderRadius: 10,
              }}
            >
              <p style={{ fontSize: '0.75rem', fontWeight: 600, margin: '0 0 8px', color: '#475569' }}>
                Tag / notify — {tagGroup?.label || tagRole}
              </p>
              {tagRoleUsers.length === 0 ? (
                <p style={{ fontSize: '0.75rem', color: '#94a3b8', margin: '0 0 8px' }}>No active users for this role.</p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 8 }}>
                  {tagRoleUsers.map((u) => (
                    <button
                      key={u.id}
                      type="button"
                      className="admin-btn admin-btn--ghost admin-btn--sm"
                      style={{ justifyContent: 'flex-start' }}
                      disabled={busy}
                      onClick={() => tagPerson(u, tagGroup)}
                    >
                      {u.full_name}
                      <span style={{ color: '#94a3b8', marginLeft: 6 }}>{u.email}</span>
                    </button>
                  ))}
                </div>
              )}
              <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setTagRole(null)}>
                Cancel
              </button>
            </div>
          ) : null}

          {canManage && pendingOwnerId != null && !tagRole ? (
            <div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
              <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" disabled={busy} onClick={() => assignOwner(pendingOwnerId)}>
                Confirm assign owner
              </button>
              <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setPendingOwnerId(null)}>
                Cancel
              </button>
            </div>
          ) : null}

          <div className="ticket-compose__actions" style={{ flexWrap: 'wrap', marginTop: 12, gap: 8, alignItems: 'center' }}>
            {canManage ? (
              <>
                <ActionMenu label={`Priority: ${PRIORITY_META[incident.priority]?.label || 'Normal'}`} items={priorityMenuItems} disabled={busy} />
                <ActionMenu
                  label={`Status: ${INCIDENT_STATUS_META[incident.status]?.label || incident.status}`}
                  items={statusMenuItems}
                  disabled={busy}
                />
                <ActionMenu
                  label="Tag / notify"
                  items={TAG_GROUPS.map((g) => ({
                    key: g.role,
                    label: g.label,
                    disabled: !staffUsers.some((u) => userInTagGroup(u, g)),
                    onClick: () => {
                      setPendingOwnerId(null)
                      setTagRole(g.role)
                    },
                  }))}
                  disabled={busy}
                />
                <ActionMenu
                  label="Assign owner"
                  items={[
                    {
                      key: 'unassigned',
                      label: 'Unassigned',
                      onClick: () => assignOwner(null),
                    },
                    ...staffUsers.map((u) => ({
                      key: String(u.id),
                      label: `${u.full_name} (${u.email})`,
                      onClick: () => {
                        setTagRole(null)
                        setPendingOwnerId(u.id)
                      },
                    })),
                  ]}
                  disabled={busy}
                />
                <button type="button" className="ticket-compose__send" disabled={busy || !replyOk} onClick={sendReply}>
                  Send reply
                </button>
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
                <button type="button" className="ticket-compose__send" disabled={busy || !replyOk} onClick={sendReply}>
                  Send reply
                </button>
              </>
            )}
          </div>
          {!isClosed && !replyOk && reply.length > 0 ? (
            <p style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: 6 }}>
              Enter at least {MIN_MESSAGE_CHARS} characters to send.
            </p>
          ) : null}
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
