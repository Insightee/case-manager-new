import { useEffect, useRef, useState } from 'react'

/**
 * Unified save toolbar: primary Save dropdown + PDF + optional generate + workflow CTA.
 */
export function ReportSaveMenu({
  saving = false,
  editable = false,
  onSaveCloud,
  onSaveLocal,
  onDownloadPdf,
  onGenerateFromLogs,
  generatingFromLogs = false,
  workflowLabel,
  onWorkflow,
  variant = 'desktop',
}) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    function onDocClick(e) {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [open])

  if (!editable && !onDownloadPdf) return null

  const btnClass =
    variant === 'mobile'
      ? 'report-edit-mobile-bar__btn report-edit-mobile-bar__btn--secondary'
      : 'rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700'

  const primaryClass =
    variant === 'mobile'
      ? 'report-edit-mobile-bar__btn report-edit-mobile-bar__btn--secondary'
      : 'rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white'

  const workflowClass =
    variant === 'mobile'
      ? 'report-edit-mobile-bar__btn report-edit-mobile-bar__btn--primary'
      : 'rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white'

  return (
    <div
      ref={rootRef}
      className={variant === 'desktop' ? 'report-save-menu flex flex-wrap items-center gap-2' : 'report-save-menu report-save-menu--mobile'}
    >
      {editable ? (
        <div className="report-save-menu__split">
          <button
            type="button"
            className={primaryClass}
            disabled={saving}
            onClick={() => {
              setOpen(false)
              onSaveCloud?.()
            }}
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
          <button
            type="button"
            className={`${primaryClass} report-save-menu__caret`}
            aria-expanded={open}
            aria-haspopup="menu"
            aria-label="More save options"
            disabled={saving}
            onClick={() => setOpen((v) => !v)}
          >
            ▾
          </button>
          {open ? (
            <div className="report-save-menu__dropdown" role="menu">
              <button
                type="button"
                role="menuitem"
                className="report-save-menu__item"
                onClick={() => {
                  setOpen(false)
                  onSaveCloud?.()
                }}
              >
                Save to cloud
              </button>
              <button
                type="button"
                role="menuitem"
                className="report-save-menu__item"
                onClick={() => {
                  setOpen(false)
                  onSaveLocal?.()
                }}
              >
                Save on this device
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
      {onDownloadPdf ? (
        <button type="button" className={btnClass} onClick={onDownloadPdf}>
          Download PDF
        </button>
      ) : null}
      {editable && onGenerateFromLogs ? (
        <button
          type="button"
          className={
            variant === 'mobile'
              ? btnClass
              : 'rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2 text-sm font-semibold text-indigo-800'
          }
          disabled={generatingFromLogs || saving}
          onClick={onGenerateFromLogs}
        >
          {generatingFromLogs ? 'Generating…' : 'Generate from session logs'}
        </button>
      ) : null}
      {editable && workflowLabel && onWorkflow ? (
        <button
          type="button"
          className={`${workflowClass}${variant === 'mobile' ? ' report-save-menu__workflow' : ''}`}
          disabled={saving}
          onClick={onWorkflow}
        >
          {workflowLabel}
        </button>
      ) : null}
    </div>
  )
}
