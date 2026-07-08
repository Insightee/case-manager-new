import { useState } from 'react'
import { apiFetch } from '../../../lib/apiClient.js'
import { ClinicalCard } from '../../clinical-ui/ClinicalCard.jsx'
import { ClinicalActionButton } from '../../clinical-ui/ClinicalActionButton.jsx'

export function CaseSummaryEditor({
  caseId,
  clinicalProfile,
  onProfileUpdated,
  title = 'Case summary',
  composedFallback = null,
  emptyMessage = 'Add a brief summary of participation, supports in use, and recent focus for this case.',
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
    setDraft(savedHistory)
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

  return (
    <ClinicalCard
      title={title}
      subtitle={updatedLabel ? `Last updated ${updatedLabel}` : readOnlyFallback ? 'From intake, observation, or IEP' : 'Clinical overview'}
      className="clinical-overview-summary-card"
      headerActions={
        editing ? null : (
          <ClinicalActionButton variant="ghost" className="clinical-summary-edit-btn" onClick={startEdit}>
            Edit
          </ClinicalActionButton>
        )
      }
    >
      {editing ? (
        <div className="clinical-summary-editor">
          <label className="clinical-summary-editor__label" htmlFor={`case-summary-${caseId}`}>
            Summary for your care team
          </label>
          <textarea
            id={`case-summary-${caseId}`}
            className="clinical-summary-editor__input"
            rows={5}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Participation patterns, supports in use, and what you are focusing on next…"
            disabled={saving}
          />
          {message ? <p className="clinical-summary-editor__msg" role="status">{message}</p> : null}
          <div className="clinical-summary-editor__actions">
            <ClinicalActionButton variant="ghost" onClick={cancelEdit} disabled={saving}>
              Cancel
            </ClinicalActionButton>
            <ClinicalActionButton variant="primary" onClick={saveSummary} disabled={saving}>
              {saving ? 'Saving…' : 'Save summary'}
            </ClinicalActionButton>
          </div>
        </div>
      ) : (
        <>
          {savedHistory ? (
            <p className="clinical-overview-summary">{savedHistory}</p>
          ) : readOnlyFallback ? (
            <p className="clinical-overview-summary">{readOnlyFallback}</p>
          ) : (
            <p className="clinical-overview-summary clinical-overview-summary--empty">
              {emptyMessage}
            </p>
          )}
          {message ? <p className="clinical-summary-editor__msg" role="status">{message}</p> : null}
        </>
      )}
      <p className="clinical-overview-summary__note">
        Internal clinical note — not shared with parents unless included in a published family section.
      </p>
    </ClinicalCard>
  )
}
