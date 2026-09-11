import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { formatDateIN } from '../../lib/datetime.js'
import { useAuth } from '../../context/AuthContext.jsx'

function formatNoteMeta(note) {
  if (!note) return ''
  const when = note.created_at ? formatDateIN(note.created_at) : ''
  const who = note.author_name || 'Team member'
  return when ? `${who} · ${when}` : who
}

function NoteBody({ body }) {
  return (
    <div className="admin-case-ops-note__body">
      {(body || '').split('\n').map((line, idx) => (
        <p key={idx} className="admin-case-ops-note__paragraph">
          {line || '\u00a0'}
        </p>
      ))}
    </div>
  )
}

function AddNoteModal({ caseId, open, onClose, onSaved }) {
  const [heading, setHeading] = useState('')
  const [body, setBody] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    setHeading('')
    setBody('')
    setError('')
    setSaving(false)
  }, [open, caseId])

  if (!open) return null

  async function handleSubmit(event) {
    event.preventDefault()
    if (!heading.trim()) {
      setError('Please add a heading so your team can scan notes quickly.')
      return
    }
    if (!body.trim()) {
      setError('Looks like we still need a few details before we can save this.')
      return
    }
    setSaving(true)
    setError('')
    try {
      const created = await apiFetch(`/api/v1/cases/${caseId}/operational-notes`, {
        method: 'POST',
        body: JSON.stringify({ heading: heading.trim(), body: body.trim() }),
      })
      onSaved?.(created)
      onClose?.()
    } catch (err) {
      setError(err.message || 'Looks like we still need a moment before we can save this.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="cs-modal-overlay" onClick={onClose}>
      <div className="cs-modal admin-case-ops-note__modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <p className="cs-modal__title">Add operational note</p>
        <p className="admin-muted" style={{ marginTop: 0, fontSize: '0.85rem' }}>
          Visible to your team only — families never see these notes.
        </p>
        {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}
        <form onSubmit={handleSubmit} className="admin-case-ops-note__form">
          <label className="admin-label" htmlFor={`ops-note-heading-${caseId}`}>
            Heading
            <input
              id={`ops-note-heading-${caseId}`}
              className="admin-input"
              value={heading}
              onChange={(e) => setHeading(e.target.value)}
              placeholder="e.g. Therapist preference, billing flag"
              maxLength={200}
              autoFocus
            />
          </label>
          <label className="admin-label" htmlFor={`ops-note-body-${caseId}`}>
            Note
            <textarea
              id={`ops-note-body-${caseId}`}
              className="admin-input"
              rows={8}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Add operational context for the case team."
            />
          </label>
          <div className="cs-modal__actions">
            <button type="button" className="admin-btn admin-btn--ghost" onClick={onClose} disabled={saving}>
              Cancel
            </button>
            <button type="submit" className="admin-btn admin-btn--primary" disabled={saving}>
              {saving ? 'Saving…' : 'Save note'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function ViewAllModal({ caseId, open, notes, loading, canDelete, onClose, onDelete, deletingId }) {
  if (!open) return null

  return (
    <div className="cs-modal-overlay" onClick={onClose}>
      <div
        className="cs-modal admin-case-ops-note__modal admin-case-ops-note__modal--wide"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <p className="cs-modal__title">All case notes</p>
        <p className="admin-muted" style={{ marginTop: 0, fontSize: '0.85rem' }}>
          Newest entries appear first.
        </p>
        {loading ? (
          <p className="admin-muted">Loading notes…</p>
        ) : notes.length ? (
          <ul className="admin-case-ops-note__stack">
            {notes.map((note) => (
              <li key={note.id} className="admin-case-ops-note__stack-item">
                <div className="admin-case-ops-note__stack-head">
                  <strong>{note.heading}</strong>
                  <span className="admin-case-ops-note__meta">{formatNoteMeta(note)}</span>
                </div>
                <NoteBody body={note.body} />
                {canDelete ? (
                  <button
                    type="button"
                    className="admin-btn admin-btn--ghost admin-btn--sm admin-case-ops-note__delete"
                    disabled={deletingId === note.id}
                    onClick={() => onDelete(note.id)}
                  >
                    {deletingId === note.id ? 'Removing…' : 'Delete'}
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="admin-empty">No case notes yet.</p>
        )}
        <div className="cs-modal__actions">
          <button type="button" className="admin-btn admin-btn--ghost" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

export function CaseOperationalNotesPanel({ caseId, canAdd, onCaseNotesChanged }) {
  const { user } = useAuth()
  const [latest, setLatest] = useState(null)
  const [allNotes, setAllNotes] = useState([])
  const [loadingLatest, setLoadingLatest] = useState(true)
  const [loadingAll, setLoadingAll] = useState(false)
  const [showAdd, setShowAdd] = useState(false)
  const [showAll, setShowAll] = useState(false)
  const [successMsg, setSuccessMsg] = useState('')
  const [deletingId, setDeletingId] = useState(null)

  const canDelete = Boolean((user?.roles || []).includes('SUPER_ADMIN'))

  const loadLatest = useCallback(async () => {
    if (!caseId) return
    setLoadingLatest(true)
    try {
      const row = await apiFetch(`/api/v1/cases/${caseId}/operational-notes/latest`)
      setLatest(row || null)
    } catch {
      setLatest(null)
    } finally {
      setLoadingLatest(false)
    }
  }, [caseId])

  const loadAll = useCallback(async () => {
    if (!caseId) return
    setLoadingAll(true)
    try {
      const rows = await apiFetch(`/api/v1/cases/${caseId}/operational-notes`)
      setAllNotes(rows || [])
    } catch {
      setAllNotes([])
    } finally {
      setLoadingAll(false)
    }
  }, [caseId])

  useEffect(() => {
    loadLatest()
    setSuccessMsg('')
  }, [loadLatest])

  useEffect(() => {
    if (!successMsg) return undefined
    const timer = window.setTimeout(() => setSuccessMsg(''), 5000)
    return () => window.clearTimeout(timer)
  }, [successMsg])

  async function handleSaved(created) {
    setLatest(created)
    setSuccessMsg('Note saved — visible to your team only.')
    onCaseNotesChanged?.(created)
    if (showAll) {
      await loadAll()
    }
  }

  async function openViewAll() {
    setShowAll(true)
    await loadAll()
  }

  async function handleDelete(noteId) {
    if (!canDelete) return
    setDeletingId(noteId)
    try {
      await apiFetch(`/api/v1/cases/${caseId}/operational-notes/${noteId}`, { method: 'DELETE' })
      await loadAll()
      await loadLatest()
      onCaseNotesChanged?.()
      setSuccessMsg('Note removed.')
    } catch (err) {
      window.alert(err.message || 'Could not remove this note.')
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="admin-panel admin-case-overview__panel">
      <div className="admin-case-overview__panel-head">
        <div>
          <p className="admin-case-overview__eyebrow">Case notes</p>
          <h3 className="admin-case-overview__title">Internal note</h3>
        </div>
      </div>

      {successMsg ? (
        <p className="admin-alert admin-alert--success admin-case-ops-note__success" role="status">
          {successMsg}
        </p>
      ) : null}

      {loadingLatest ? (
        <p className="admin-muted">Loading latest note…</p>
      ) : latest ? (
        <article className="admin-case-ops-note__latest">
          <h4 className="admin-case-ops-note__latest-heading">{latest.heading}</h4>
          <p className="admin-case-ops-note__meta">{formatNoteMeta(latest)}</p>
          <NoteBody body={latest.body} />
        </article>
      ) : (
        <p className="admin-case-overview__readonly-text">No case notes yet.</p>
      )}

      <div className="admin-case-ops-note__actions">
        {canAdd ? (
          <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={() => setShowAdd(true)}>
            Add note
          </button>
        ) : null}
        <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={openViewAll}>
          View all
        </button>
      </div>

      <AddNoteModal
        caseId={caseId}
        open={showAdd}
        onClose={() => setShowAdd(false)}
        onSaved={handleSaved}
      />
      <ViewAllModal
        caseId={caseId}
        open={showAll}
        notes={allNotes}
        loading={loadingAll}
        canDelete={canDelete}
        deletingId={deletingId}
        onClose={() => setShowAll(false)}
        onDelete={handleDelete}
      />
    </div>
  )
}
