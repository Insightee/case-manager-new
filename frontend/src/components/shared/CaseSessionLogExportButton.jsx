import { useEffect, useId, useRef, useState } from 'react'
import { downloadCaseSessionLogExport } from '../../lib/sessionLogBulkExport.js'
import './CaseSessionLogExportButton.css'

function SpreadsheetIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" width="16" height="16">
      <path
        d="M7 4h10a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <path d="M9 4v16M15 4v16M5 9h14M5 15h14" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  )
}

export function CaseSessionLogExportButton({
  caseId,
  caseCode,
  parent = false,
  viewMode,
  selectedMonth,
  selectedDate,
  statusFilter,
  attendanceFilter,
  year,
  disabled = false,
  className = '',
  label = 'Download',
}) {
  const [open, setOpen] = useState(false)
  const [includeContent, setIncludeContent] = useState(false)
  const [busy, setBusy] = useState(false)
  const rootRef = useRef(null)
  const panelId = useId()
  const titleId = `${panelId}-title`

  useEffect(() => {
    if (!open) return undefined

    function handlePointerDown(event) {
      if (rootRef.current?.contains(event.target)) return
      setOpen(false)
    }

    function handleKeyDown(event) {
      if (event.key === 'Escape') setOpen(false)
    }

    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  async function handleExport() {
    if (busy || disabled || !caseId) return
    setBusy(true)
    try {
      await downloadCaseSessionLogExport({
        caseId,
        caseCode,
        parent,
        viewMode,
        selectedMonth,
        selectedDate,
        statusFilter,
        attendanceFilter,
        year,
        includeContent,
      })
      setOpen(false)
    } catch (err) {
      window.alert(err.message || "We couldn't download the export right now. Please try again.")
    } finally {
      setBusy(false)
    }
  }

  const rootClass = ['case-log-export', className].filter(Boolean).join(' ')

  return (
    <div className={rootClass} ref={rootRef}>
      <button
        type="button"
        className="case-log-export-btn"
        onClick={() => setOpen((prev) => !prev)}
        disabled={busy || disabled || !caseId}
        aria-label={busy ? 'Preparing session log export' : 'Download filtered session logs'}
        aria-busy={busy}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-controls={open ? panelId : undefined}
        title={busy ? 'Preparing export…' : 'Download filtered session logs'}
      >
        <SpreadsheetIcon />
        <span>{busy ? 'Preparing…' : label}</span>
      </button>

      {open ? (
        <div
          id={panelId}
          className="case-log-export__panel"
          role="dialog"
          aria-labelledby={titleId}
        >
          <p id={titleId} className="case-log-export__title">
            Download session logs
          </p>
          <p className="case-log-export__hint">
            Choose what to include for the filters currently on this page.
          </p>

          <fieldset className="case-log-export__fieldset">
            <legend className="case-log-export__legend">Include log content?</legend>
            <label className="case-log-export__option">
              <input
                type="radio"
                name={`${panelId}-content`}
                checked={!includeContent}
                onChange={() => setIncludeContent(false)}
              />
              <span className="case-log-export__option-copy">
                <strong>Summary only</strong>
                <span>Therapist, date, time, and status</span>
              </span>
            </label>
            <label className="case-log-export__option">
              <input
                type="radio"
                name={`${panelId}-content`}
                checked={includeContent}
                onChange={() => setIncludeContent(true)}
              />
              <span className="case-log-export__option-copy">
                <strong>Include log text</strong>
                <span>
                  {parent
                    ? 'Family-facing notes and activities'
                    : 'Full session log fields'}
                </span>
              </span>
            </label>
          </fieldset>

          <div className="case-log-export__actions">
            <button
              type="button"
              className="case-log-export__action case-log-export__action--ghost"
              onClick={() => setOpen(false)}
              disabled={busy}
            >
              Cancel
            </button>
            <button
              type="button"
              className="case-log-export__action case-log-export__action--primary"
              onClick={handleExport}
              disabled={busy}
            >
              {busy ? 'Preparing…' : 'Download spreadsheet'}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
