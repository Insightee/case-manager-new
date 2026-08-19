import { ClinicalPrimaryButton } from '../../clinical-ui/ClinicalPrimaryButton.jsx'

export function ObservationBuilderFooter({ saving, canSubmit, readOnly, onPreview, onSubmit, onBack }) {
  return (
    <footer className="ob-footer">
      <button type="button" className="ob-btn-ghost" onClick={onBack}>← Back to status</button>
      <div className="ob-footer__actions">
        <button type="button" className="ob-btn-secondary" onClick={onPreview}>Preview report</button>
        {!readOnly ? (
          <ClinicalPrimaryButton disabled={!canSubmit || saving} onClick={onSubmit}>
            {saving ? 'Submitting…' : 'Finalize & submit'}
          </ClinicalPrimaryButton>
        ) : null}
      </div>
    </footer>
  )
}
