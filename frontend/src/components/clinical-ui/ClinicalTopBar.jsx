import { Link } from 'react-router-dom'

/**
 * Sticky top bar for report builder pages.
 * backTo: route string or null/undefined to hide back button
 * title: page title
 * saveAction: { label, onClick, saving } — only shown if provided
 * previewAction: { label, onClick } — only shown if provided
 * submitAction: { label, onClick, disabled } — only shown if provided
 */
export function ClinicalTopBar({ backTo, onBack, title, saveAction, previewAction, submitAction }) {
  return (
    <div className="clinical-topbar">
      {(backTo || onBack) ? (
        backTo ? (
          <Link to={backTo} className="clinical-topbar__back" aria-label="Go back">
            ←
          </Link>
        ) : (
          <button type="button" className="clinical-topbar__back" onClick={onBack} aria-label="Go back">
            ←
          </button>
        )
      ) : null}

      <h1 className="clinical-topbar__title">{title}</h1>

      <div className="clinical-topbar__actions">
        {saveAction ? (
          <button
            type="button"
            className="clinical-btn-ghost"
            onClick={saveAction.onClick}
            disabled={saveAction.saving}
            aria-label={saveAction.label || 'Save'}
            title={saveAction.label || 'Save'}
          >
            {saveAction.saving ? '…' : '💾'}
          </button>
        ) : null}

        {previewAction ? (
          <button
            type="button"
            className="clinical-btn-secondary"
            onClick={previewAction.onClick}
            style={{ fontSize: '0.8125rem', minHeight: '36px', padding: '0.4rem 0.875rem' }}
          >
            {previewAction.label || 'Preview'}
          </button>
        ) : null}

        {submitAction ? (
          <button
            type="button"
            className="clinical-btn-primary"
            onClick={submitAction.onClick}
            disabled={submitAction.disabled}
            style={{ fontSize: '0.8125rem', minHeight: '36px', padding: '0.4rem 0.875rem' }}
          >
            {submitAction.label || 'Submit'}
          </button>
        ) : null}
      </div>
    </div>
  )
}
