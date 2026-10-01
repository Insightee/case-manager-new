import { useEffect } from 'react'
import { apiDownload } from '../../lib/apiClient.js'

function isImageMime(mime) {
  return (mime || '').startsWith('image/')
}

function isPdfMime(mime, fileName) {
  const m = (mime || '').toLowerCase()
  if (m === 'application/pdf') return true
  return (fileName || '').toLowerCase().endsWith('.pdf')
}

function isTextMime(mime, fileName) {
  const m = (mime || '').toLowerCase()
  if (m === 'text/plain') return true
  return (fileName || '').toLowerCase().endsWith('.txt')
}

export function TicketAttachmentPreviewModal({
  open,
  attachment,
  downloadPrefix,
  loading,
  error,
  blobUrl,
  textContent,
  onClose,
}) {
  useEffect(() => {
    if (!open) return undefined
    function onKeyDown(e) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  if (!open || !attachment) return null

  const mime = attachment.mime_type || ''
  const fileName = attachment.file_name || 'attachment'
  const downloadPath = `${downloadPrefix}/attachments/${attachment.id}/download`
  const canPreview =
    !loading &&
    !error &&
    (isImageMime(mime) || isPdfMime(mime, fileName) || isTextMime(mime, fileName))

  return (
    <div
      className="ticket-attachment-preview"
      role="dialog"
      aria-modal="true"
      aria-labelledby="ticket-attachment-preview-title"
    >
      <button type="button" className="ticket-attachment-preview__backdrop" aria-label="Close preview" onClick={onClose} />
      <div className="ticket-attachment-preview__sheet">
        <header className="ticket-attachment-preview__header">
          <h2 id="ticket-attachment-preview-title" className="ticket-attachment-preview__title">
            {fileName}
          </h2>
          <div className="ticket-attachment-preview__actions">
            <button
              type="button"
              className="ticket-attachment-preview__download"
              onClick={() =>
                apiDownload(downloadPath, fileName).catch((err) =>
                  alert(err.message || 'Could not download'),
                )
              }
            >
              Download
            </button>
            <button type="button" className="ticket-attachment-preview__close" aria-label="Close" onClick={onClose}>
              ×
            </button>
          </div>
        </header>

        <div className="ticket-attachment-preview__body">
          {loading ? <p className="ticket-attachment-preview__status">Loading preview…</p> : null}
          {error ? <p className="ticket-attachment-preview__status ticket-attachment-preview__status--error">{error}</p> : null}

          {!loading && !error && canPreview && isImageMime(mime) && blobUrl ? (
            <img src={blobUrl} alt={fileName} className="ticket-attachment-preview__image" />
          ) : null}

          {!loading && !error && canPreview && isPdfMime(mime, fileName) && blobUrl ? (
            <iframe title={fileName} src={blobUrl} className="ticket-attachment-preview__iframe" />
          ) : null}

          {!loading && !error && canPreview && isTextMime(mime, fileName) && textContent != null ? (
            <pre className="ticket-attachment-preview__text">{textContent}</pre>
          ) : null}

          {!loading && !error && !canPreview ? (
            <p className="ticket-attachment-preview__status">
              Preview is not available for this file type. Use Download to save it to your device.
            </p>
          ) : null}
        </div>
      </div>
    </div>
  )
}
