import { useEffect, useMemo, useState } from 'react'
import { apiFetch, apiUpload } from '../../lib/apiClient.js'
import { formatDisplayDateTime, formatDisplayDate } from '../../lib/datetime.js'
import { meetingDisplayTitle } from './meetingUtils.js'
import { MEETING_OUTCOME_OPTIONS } from './meetingConstants.js'
import './meeting-sheets.css'

function formatMeetingDocMeta(doc) {
  const parts = []
  if (doc.meeting_scheduled_date) {
    parts.push(formatDisplayDate(doc.meeting_scheduled_date))
  }
  if (doc.meeting_scheduled_time) {
    parts.push(doc.meeting_scheduled_time)
  }
  if (doc.title?.toLowerCase().startsWith('meeting notes —')) {
    parts.push('Shared minutes')
  } else if (doc.current_version?.source_type === 'UPLOAD') {
    parts.push('File')
  } else {
    parts.push('Text note')
  }
  return parts.join(' · ')
}

export function MeetingNotesSheet({
  open,
  meeting,
  onClose,
  onSaved,
  isTherapistView = false,
}) {
  const [form, setForm] = useState({
    notes_outcome: meeting?.notes_outcome || '',
    notes_summary: meeting?.notes_summary || '',
    notes_next_meeting_required: Boolean(meeting?.notes_next_meeting_required),
    notes_additional: meeting?.notes_additional || '',
    therapist_notes: meeting?.therapist_notes || '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [selectedFile, setSelectedFile] = useState(null)
  const [documents, setDocuments] = useState([])
  const [documentsLoading, setDocumentsLoading] = useState(false)

  useEffect(() => {
    if (!meeting) return
    setForm({
      notes_outcome: meeting.notes_outcome || '',
      notes_summary: meeting.notes_summary || '',
      notes_next_meeting_required: Boolean(meeting.notes_next_meeting_required),
      notes_additional: meeting.notes_additional || '',
      therapist_notes: meeting.therapist_notes || '',
    })
    setSelectedFile(null)
    setError('')
  }, [meeting?.id, meeting?.notes_outcome, meeting?.notes_summary, meeting?.notes_next_meeting_required, meeting?.notes_additional, meeting?.therapist_notes])

  useEffect(() => {
    if (!open || !meeting?.id) {
      setDocuments([])
      return undefined
    }
    let cancelled = false
    setDocumentsLoading(true)
    apiFetch(`/api/v1/meetings/${meeting.id}/documents`)
      .then((rows) => {
        if (!cancelled) setDocuments(Array.isArray(rows) ? rows : [])
      })
      .catch(() => {
        if (!cancelled) setDocuments([])
      })
      .finally(() => {
        if (!cancelled) setDocumentsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [open, meeting?.id])

  const canAttachFiles = Boolean(meeting?.case_id) && !isTherapistView
  const sharedMinutesLabel = isTherapistView ? 'My private notes' : 'Shared minutes'
  const meetingLabel = useMemo(() => meetingDisplayTitle(meeting) || 'Meeting notes', [meeting])

  async function submit(mode = 'save') {
    if (!meeting?.id) return
    if (
      !isTherapistView
      && mode === 'complete'
      && (!form.notes_summary.trim() || !form.notes_outcome.trim())
    ) {
      setError('Looks like we still need a shared minutes outcome and summary before we can complete this meeting.')
      return
    }
    setSaving(true)
    setError('')
    try {
      const body = new FormData()
      if (isTherapistView) {
        body.append('therapist_notes', form.therapist_notes || '')
      } else {
        body.append('notes_outcome', form.notes_outcome || '')
        body.append('notes_summary', form.notes_summary || '')
        body.append('notes_next_meeting_required', form.notes_next_meeting_required ? 'true' : 'false')
        body.append('notes_additional', form.notes_additional || '')
        if (mode === 'complete') {
          body.append('status', 'COMPLETED')
        }
      }
      if (selectedFile) {
        body.append('file', selectedFile)
      }
      const updated = await apiUpload(`/api/v1/meetings/${meeting.id}/notes`, body)
      onSaved?.(updated)
      setSelectedFile(null)
    } catch (err) {
      setError(err.message || 'Could not save meeting notes')
    } finally {
      setSaving(false)
    }
  }

  if (!open || !meeting) return null

  return (
    <div className="meeting-sheet-backdrop" role="dialog" aria-modal="true">
      <div className="meeting-sheet">
        <div className="meeting-sheet__inner">
          <div className="meeting-sheet__head">
            <div>
              <p className="meeting-sheet__eyebrow">
                {isTherapistView ? 'Private notes' : 'Shared minutes'}
              </p>
              <h2 className="meeting-sheet__title">{meetingLabel}</h2>
              <p className="meeting-sheet__meta">
                {formatDisplayDateTime(meeting.scheduled_date, meeting.scheduled_time)}
                {meeting.duration_minutes ? ` · ${meeting.duration_minutes} min` : ''}
              </p>
            </div>
            <button type="button" className="meeting-sheet__close" onClick={onClose} aria-label="Close">
              ✕
            </button>
          </div>

          {error ? (
            <p className="meeting-sheet__helper meeting-sheet__helper--warning" role="alert">
              {error}
            </p>
          ) : null}

          <div className="meeting-sheet__body">
            <section className="meeting-sheet__card">
              <h3 className="meeting-sheet__card-title">{sharedMinutesLabel}</h3>
              {isTherapistView ? (
                <label className="meeting-sheet__label">
                  My private notes
                  <textarea
                    className="meeting-sheet__textarea"
                    placeholder="Add your private reflection or discussion notes..."
                    value={form.therapist_notes}
                    onChange={(e) => setForm((draft) => ({ ...draft, therapist_notes: e.target.value }))}
                  />
                </label>
              ) : (
                <>
                  <label className="meeting-sheet__label">
                    Shared minutes outcome
                    <select
                      className="meeting-sheet__select"
                      value={form.notes_outcome}
                      onChange={(e) => setForm((draft) => ({ ...draft, notes_outcome: e.target.value }))}
                    >
                      {MEETING_OUTCOME_OPTIONS.map((opt) => (
                        <option key={opt.value || 'empty'} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="meeting-sheet__label">
                    Shared minutes
                    <textarea
                      className="meeting-sheet__textarea"
                      placeholder="What was shared, agreed, and decided in this meeting..."
                      value={form.notes_summary}
                      onChange={(e) => setForm((draft) => ({ ...draft, notes_summary: e.target.value }))}
                    />
                  </label>
                  <label className="meeting-sheet__label">
                    <span className="meeting-sheet__inline-row">
                      <input
                        type="checkbox"
                        checked={form.notes_next_meeting_required}
                        onChange={(e) => setForm((draft) => ({ ...draft, notes_next_meeting_required: e.target.checked }))}
                      />
                      Follow-up meeting required
                    </span>
                  </label>
                  <label className="meeting-sheet__label">
                    Additional notes
                    <textarea
                      className="meeting-sheet__textarea"
                      placeholder="Any other context for the shared record..."
                      value={form.notes_additional}
                      onChange={(e) => setForm((draft) => ({ ...draft, notes_additional: e.target.value }))}
                    />
                  </label>
                </>
              )}
            </section>

            {!isTherapistView ? (
              <section className="meeting-sheet__card">
                <h3 className="meeting-sheet__card-title">Meeting files</h3>
                {canAttachFiles ? (
                  <label className="meeting-sheet__label">
                    Upload a file
                    <input
                      type="file"
                      className="meeting-sheet__file"
                      onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                    />
                  </label>
                ) : (
                  <p className="meeting-sheet__helper">
                    This meeting is not linked to a case, so file uploads are unavailable. Add text notes only.
                  </p>
                )}
                {selectedFile ? (
                  <p className="meeting-sheet__helper">Selected: {selectedFile.name}</p>
                ) : null}
                {documentsLoading ? (
                  <p className="meeting-sheet__helper">Loading existing meeting documents…</p>
                ) : documents.length ? (
                  <ul className="meeting-sheet__doc-list">
                    {documents.map((doc) => (
                      <li key={doc.id} className="meeting-sheet__doc-item">
                        <p className="meeting-sheet__doc-title">{doc.title}</p>
                        <p className="meeting-sheet__doc-meta">
                          {formatMeetingDocMeta(doc)}
                        </p>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="meeting-sheet__helper">No meeting documents yet.</p>
                )}
              </section>
            ) : null}
          </div>
        </div>

        <div className="meeting-sheet__actions">
          {isTherapistView ? (
            <>
              <button
                type="button"
                className="meeting-sheet__btn meeting-sheet__btn--primary"
                disabled={saving}
                onClick={() => submit('save')}
              >
                {saving ? 'Saving…' : 'Save private notes'}
              </button>
              <button
                type="button"
                className="meeting-sheet__btn meeting-sheet__btn--ghost"
                onClick={onClose}
              >
                Close
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                className="meeting-sheet__btn meeting-sheet__btn--secondary"
                disabled={saving}
                onClick={() => submit('save')}
              >
                {saving ? 'Saving…' : 'Save shared minutes'}
              </button>
              <button
                type="button"
                className="meeting-sheet__btn meeting-sheet__btn--primary"
                disabled={saving}
                onClick={() => submit('complete')}
              >
                {saving ? 'Saving…' : 'Complete meeting'}
              </button>
              <button
                type="button"
                className="meeting-sheet__btn meeting-sheet__btn--ghost"
                onClick={onClose}
              >
                Close
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
