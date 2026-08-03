export function VoiceFlowFooter({
  onBack,
  onSaveDraft,
  onPreview,
  onSubmit,
  submitting,
  savingDraft,
  previewMode,
  submitLabel = 'Submit log',
}) {
  if (previewMode) {
    return (
      <footer className="vsl-stitch__footer vsl-stitch__footer--compact">
        <div className="vsl-stitch__footer-inner">
          {onBack ? (
            <button type="button" className="vsl-stitch__footer-link" onClick={onBack}>
              ← Back to draft
            </button>
          ) : (
            <span className="vsl-stitch__footer-spacer" />
          )}
          {onSubmit ? (
            <button
              type="button"
              className="vsl-stitch__btn vsl-stitch__btn--primary vsl-stitch__btn--sm"
              disabled={submitting}
              onClick={onSubmit}
            >
              {submitting ? 'Submitting…' : submitLabel}
            </button>
          ) : null}
        </div>
      </footer>
    )
  }

  return (
    <footer className="vsl-stitch__footer vsl-stitch__footer--compact">
      <div className="vsl-stitch__footer-inner vsl-stitch__footer-inner--actions">
        {onSaveDraft ? (
          <button
            type="button"
            className="vsl-stitch__footer-link"
            disabled={savingDraft}
            onClick={onSaveDraft}
          >
            {savingDraft ? 'Saving…' : 'Save draft'}
          </button>
        ) : null}
        {onPreview ? (
          <button type="button" className="vsl-stitch__btn vsl-stitch__btn--ghost vsl-stitch__btn--sm" onClick={onPreview}>
            Preview
          </button>
        ) : null}
        {onSubmit ? (
          <button
            type="button"
            className="vsl-stitch__btn vsl-stitch__btn--primary vsl-stitch__btn--sm"
            disabled={submitting}
            onClick={onSubmit}
          >
            {submitting ? 'Submitting…' : submitLabel}
          </button>
        ) : null}
      </div>
    </footer>
  )
}
