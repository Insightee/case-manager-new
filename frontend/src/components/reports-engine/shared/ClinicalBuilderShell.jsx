/** Shared builder chrome — IEP + observation. Matches Stitch header/footer. */
export function ClinicalBuilderShell({
  title,
  statusLabel = 'DRAFT',
  saving = false,
  readOnly = false,
  canSubmit = false,
  onSaveDraft,
  onPreview,
  onSubmit,
  onDownloadPdf,
  onAddGoal,
  addGoalLabel = 'Add goal / strategy',
  children,
}) {
  return (
    <div className="clinical-report-ui">
      <header className="cr-builder-header">
        <div>
          <h1 className="cr-builder-header__title">{title}</h1>
          <span className="cr-badge-draft">{statusLabel}</span>
        </div>
        <div className="cr-header-actions">
          <button type="button" className="cr-btn" onClick={onPreview}>
            Preview report
          </button>
          {onDownloadPdf ? (
            <button type="button" className="cr-btn" disabled={saving} onClick={onDownloadPdf}>
              {saving ? 'Preparing…' : 'Download PDF'}
            </button>
          ) : null}
          {!readOnly ? (
            <button type="button" className="cr-btn" disabled={saving} onClick={onSaveDraft}>
              {saving ? 'Saving…' : 'Save'}
            </button>
          ) : null}
          {!readOnly && onSubmit ? (
            <button
              type="button"
              className="cr-btn cr-btn--primary"
              style={{ backgroundColor: '#0b1c16', color: '#fff' }}
              disabled={saving}
              onClick={onSubmit}
            >
              Submit for review
            </button>
          ) : null}
          {!readOnly && onAddGoal ? (
            <button type="button" className="cr-btn cr-btn--forest" onClick={onAddGoal}>
              {addGoalLabel}
            </button>
          ) : null}
        </div>
      </header>
      {children}
      <footer className="sticky-footer flex flex-wrap gap-3 justify-end mt-8">
        {!readOnly ? (
          <button type="button" className="cr-btn" disabled={saving} onClick={onSaveDraft}>
            Save draft
          </button>
        ) : null}
        <button type="button" className="cr-btn" onClick={onPreview}>
          Preview
        </button>
        {onDownloadPdf ? (
          <button type="button" className="cr-btn" disabled={saving} onClick={onDownloadPdf}>
            Download PDF
          </button>
        ) : null}
        {!readOnly && onSubmit ? (
          <button
            type="button"
            className="cr-btn cr-btn--primary"
            style={{ backgroundColor: '#0b1c16', color: '#fff' }}
            disabled={saving}
            onClick={onSubmit}
          >
            Submit for review
          </button>
        ) : null}
      </footer>
    </div>
  )
}
