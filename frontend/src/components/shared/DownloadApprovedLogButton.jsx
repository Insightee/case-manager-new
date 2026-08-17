import { useState } from 'react'
import { canDownloadApprovedSessionLog, downloadApprovedSessionLog } from '../../lib/sessionLogDownload.js'
import './DownloadApprovedLogButton.css'

function DownloadIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" width="14" height="14">
      <path
        d="M12 4v10m0 0 4-4m-4 4-4-4M5 18h14"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export function DownloadApprovedLogButton({ log, variant = 'staff', className = '' }) {
  const [busy, setBusy] = useState(false)
  if (!canDownloadApprovedSessionLog(log)) return null

  async function handleClick(event) {
    event.preventDefault()
    event.stopPropagation()
    if (busy) return
    setBusy(true)
    try {
      await downloadApprovedSessionLog(log, { parent: variant === 'parent' })
    } catch (err) {
      window.alert(err.message || "We couldn't download this log right now. Please try again.")
    } finally {
      setBusy(false)
    }
  }

  const rootClass = ['log-download-btn', `log-download-btn--${variant}`, className].filter(Boolean).join(' ')

  return (
    <button
      type="button"
      className={rootClass}
      onClick={handleClick}
      disabled={busy}
      aria-label="Download approved log"
    >
      <DownloadIcon />
      {busy ? 'Downloading…' : 'Download'}
    </button>
  )
}
