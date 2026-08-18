import { useState } from 'react'
import {
  confirmIncludeLogContent,
  downloadCaseSessionLogExport,
} from '../../lib/sessionLogBulkExport.js'
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
  const [busy, setBusy] = useState(false)

  async function handleClick() {
    if (busy || disabled || !caseId) return
    const includeContent = confirmIncludeLogContent()
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
    } catch (err) {
      window.alert(err.message || "We couldn't download the export right now. Please try again.")
    } finally {
      setBusy(false)
    }
  }

  const rootClass = ['case-log-export-btn', className].filter(Boolean).join(' ')

  return (
    <button
      type="button"
      className={rootClass}
      onClick={handleClick}
      disabled={busy || disabled || !caseId}
      aria-label={busy ? 'Preparing session log export' : 'Download filtered session logs'}
      aria-busy={busy}
      title={busy ? 'Preparing export…' : 'Download filtered session logs'}
    >
      <SpreadsheetIcon />
      <span>{busy ? 'Preparing…' : label}</span>
    </button>
  )
}
