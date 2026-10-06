import { useEffect } from 'react'
import { apiDownload } from '../../lib/apiClient.js'
import '../support/ticket-attachment-preview.css'

export function VaultDocumentPreviewModal({ open, fileName, fileUrl, downloadPath, loading, error, onClose }) {
  useEffect(() => {
    if (!open) return undefined
    function onKeyDown(e) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="ticket-attachment-preview" role="dialog" aria-modal="true">
      <button type="button" className="ticket-attachment-preview__backdrop" aria-label="Close preview" onClick={onClose} />
      <div className="ticket-attachment-preview__sheet">
        <header className="ticket-attachment-preview__header">
          <h2 className="ticket-attachment-preview__title">{fileName || 'Document'}</h2>
          <div className="ticket-attachment-preview__actions">
            {downloadPath ? (
              <button
                type="button"
                className="ticket-attachment-preview__download"
                onClick={() =>
                  apiDownload(downloadPath, fileName || 'document.pdf').catch((err) =>
                    alert(err.message || 'Could not download'),
                  )
                }
              >
                Download
              </button>
            ) : null}
            <button type="button" className="ticket-attachment-preview__close" aria-label="Close" onClick={onClose}>
              ×
            </button>
          </div>
        </header>
        <div className="ticket-attachment-preview__body">
          {loading ? <p className="ticket-attachment-preview__status">Loading preview…</p> : null}
          {error ? <p className="ticket-attachment-preview__status ticket-attachment-preview__status--error">{error}</p> : null}
          {!loading && !error && fileUrl ? (
            <iframe title={fileName} className="ticket-attachment-preview__pdf" src={fileUrl} />
          ) : null}
        </div>
      </div>
    </div>
  )
}
