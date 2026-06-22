import { ParentVoiceNote } from './ParentVoiceNote.jsx'
import { SessionLogParentPreview } from './SessionLogParentPreview.jsx'

export function SessionLogNotesDual({
  form,
  onChange,
  readOnly = false,
  caseId,
  sessionDate,
  sessionEvidence,
  voiceAttachment,
  onVoiceAttachmentChange,
}) {
  const internalValue = [form.session_notes, form.observations].filter(Boolean).join('\n\n')

  function updateInternal(text) {
    onChange({ session_notes: text, observations: '' })
  }

  return (
    <>
      <div className="sl-v2-notes-grid">
        <div className="sl-v2-note-card">
          <div className="sl-v2-note-card__head">
            <span aria-hidden="true">🔒</span>
            <h3 className="sl-v2-note-card__title">Clinical Internal Note</h3>
          </div>
          <textarea
            value={internalValue}
            disabled={readOnly}
            placeholder="Private notes for clinical staff only. Document complex behaviors, confidential observations, or clinical reasoning here."
            onChange={(e) => updateInternal(e.target.value)}
          />
        </div>
        <div className="sl-v2-note-card">
          <div className="sl-v2-note-card__head">
            <span aria-hidden="true">↗</span>
            <h3 className="sl-v2-note-card__title">Parent Shareable Summary</h3>
          </div>
          <textarea
            value={form.parent_notes || ''}
            disabled={readOnly}
            placeholder="Summarize the session in parent-friendly language. Focus on wins, participation, and one thing to try at home."
            onChange={(e) => onChange({ parent_notes: e.target.value })}
          />
          <ParentVoiceNote
            caseId={caseId}
            sessionDate={sessionDate}
            disabled={readOnly}
            attachment={voiceAttachment}
            onAttachmentChange={onVoiceAttachmentChange}
          />
        </div>
      </div>
      <SessionLogParentPreview sessionEvidence={sessionEvidence} parentNotes={form.parent_notes} />
    </>
  )
}
