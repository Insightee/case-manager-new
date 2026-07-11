export function VoiceFlowFooter({ onSaveDraft, onBack, onPreview, onSubmit, submitting, previewMode, submitLabel = 'Submit log' }) {
  return (
    <footer className="vsl-stitch__footer">
      {onSaveDraft && !previewMode ? (
        <button type="button" className="vsl-stitch__btn vsl-stitch__btn--ghost" onClick={onSaveDraft}>
          Save draft
        </button>
      ) : null}
      {previewMode && onBack ? (
        <button type="button" className="vsl-stitch__btn vsl-stitch__btn--ghost" onClick={onBack}>
          Back to draft
        </button>
      ) : null}
      {previewMode && onSubmit ? (
        <button type="button" className="vsl-stitch__btn vsl-stitch__btn--primary" disabled={submitting} onClick={onSubmit}>
          {submitting ? 'Submitting…' : submitLabel}
        </button>
      ) : onPreview ? (
        <button type="button" className="vsl-stitch__btn vsl-stitch__btn--primary" onClick={onPreview}>
          Review and submit
        </button>
      ) : null}
    </footer>
  )
}
