import { useState } from 'react'
import { apiFetch } from '../../../lib/apiClient.js'

/**
 * Forest Light overview summary — do not wrap in ClinicalCard.
 * Stitch: Modern Therapist Case Dashboard → Overview Summary section.
 */
export function CaseOverviewSummaryCard({
  caseId,
  clinicalProfile,
  onProfileUpdated,
  composedFallback = null,
  emptyMessage = 'Not enough case information has been added yet.',
}) {
  const savedHistory = clinicalProfile?.history?.trim() || ''
  const readOnlyFallback = !savedHistory && composedFallback?.trim() ? composedFallback.trim() : ''
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(savedHistory)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  const updatedLabel = clinicalProfile?.updated_at
    ? new Date(clinicalProfile.updated_at).toLocaleDateString('en-IN', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
      })
    : null

  function startEdit() {
    setDraft(savedHistory || readOnlyFallback)
    setMessage('')
    setEditing(true)
  }

  function cancelEdit() {
    setDraft(savedHistory)
    setMessage('')
    setEditing(false)
  }

  async function saveSummary() {
    const text = draft.trim()
    if (!text) {
      setMessage('Would you like to add a few lines before we save this.')
      return
    }
    if (text === savedHistory) {
      setEditing(false)
      return
    }

    setSaving(true)
    setMessage('')
    const previous = clinicalProfile
    const optimistic = {
      ...(clinicalProfile || { case_id: Number(caseId) }),
      history: text,
      updated_at: new Date().toISOString(),
    }
    onProfileUpdated?.(optimistic)

    try {
      const updated = await apiFetch(`/api/v1/cases/${caseId}/clinical-profile`, {
        method: 'PATCH',
        body: JSON.stringify({ history: text }),
      })
      onProfileUpdated?.(updated)
      setEditing(false)
    } catch (err) {
      onProfileUpdated?.(previous)
      setMessage(err.message || 'We could not save this summary right now. Would you like to try again?')
    } finally {
      setSaving(false)
    }
  }

  const displayText = savedHistory || readOnlyFallback

  return (
    <section className="cov-card cov-card--summary">
      <div className="cov-card__head">
        <span className="material-symbols-outlined cov-card__icon" aria-hidden="true">
          description
        </span>
        <h3 className="cov-card__title">Overview summary</h3>
        {!editing ? (
          <button type="button" className="cov-text-action" onClick={startEdit}>
            Edit
          </button>
        ) : null}
      </div>

      {editing ? (
        <div className="cov-summary-editor">
          <label className="cov-summary-editor__label" htmlFor={`case-summary-${caseId}`}>
            Summary for your care team
          </label>
          <textarea
            id={`case-summary-${caseId}`}
            className="cov-summary-editor__input"
            rows={5}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Participation patterns, supports in use, and what you are focusing on next…"
            disabled={saving}
          />
          {message ? (
            <p className="cov-summary-editor__msg" role="status">
              {message}
            </p>
          ) : null}
          <div className="cov-summary-editor__actions">
            <button type="button" className="cov-btn cov-btn--ghost" onClick={cancelEdit} disabled={saving}>
              Cancel
            </button>
            <button type="button" className="cov-btn cov-btn--primary" onClick={saveSummary} disabled={saving}>
              {saving ? 'Saving…' : 'Save summary'}
            </button>
          </div>
        </div>
      ) : (
        <>
          {displayText ? (
            <p className="cov-summary-text">{displayText}</p>
          ) : (
            <p className="cov-empty cov-empty--plain">{emptyMessage}</p>
          )}
          {message ? (
            <p className="cov-summary-editor__msg" role="status">
              {message}
            </p>
          ) : null}
        </>
      )}

      <p className="cov-summary-note">
        {updatedLabel
          ? `Last updated ${updatedLabel}. `
          : readOnlyFallback
            ? 'From intake, observation, or IEP. '
            : ''}
        Internal clinical note — not shared with parents unless included in a published family section.
      </p>
    </section>
  )
}
