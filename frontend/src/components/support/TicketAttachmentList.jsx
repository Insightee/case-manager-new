import { useCallback, useEffect, useState } from 'react'
import { fetchAuthenticatedBlob } from '../../lib/apiClient.js'
import { TicketAttachmentPreviewModal } from './TicketAttachmentPreviewModal.jsx'

function formatSize(sizeBytes) {
  if (!sizeBytes) return null
  if (sizeBytes < 1024 * 1024) return `${Math.round(sizeBytes / 1024)} KB`
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`
}

export function TicketAttachmentList({ attachments = [], downloadPrefix = '/api/v1/tickets' }) {
  const [preview, setPreview] = useState(null)

  const closePreview = useCallback(() => {
    setPreview((current) => {
      if (current?.blobUrl) URL.revokeObjectURL(current.blobUrl)
      return null
    })
  }, [])

  useEffect(() => () => {
    if (preview?.blobUrl) URL.revokeObjectURL(preview.blobUrl)
  }, [preview?.blobUrl])

  async function openPreview(att) {
    closePreview()
    setPreview({
      attachment: att,
      loading: true,
      error: null,
      blobUrl: null,
      textContent: null,
    })

    try {
      const path = `${downloadPrefix}/attachments/${att.id}/download`
      const { blob, url } = await fetchAuthenticatedBlob(path)
      const mime = (att.mime_type || blob.type || '').toLowerCase()
      const isText = mime === 'text/plain' || (att.file_name || '').toLowerCase().endsWith('.txt')

      if (isText) {
        const text = await blob.text()
        URL.revokeObjectURL(url)
        setPreview({
          attachment: att,
          loading: false,
          error: null,
          blobUrl: null,
          textContent: text,
        })
        return
      }

      setPreview({
        attachment: att,
        loading: false,
        error: null,
        blobUrl: url,
        textContent: null,
      })
    } catch (err) {
      setPreview({
        attachment: att,
        loading: false,
        error: err.message || 'Could not load preview',
        blobUrl: null,
        textContent: null,
      })
    }
  }

  if (!attachments?.length) return null

  return (
    <>
      <ul className="ticket-attachments">
        {attachments.map((att) => (
          <li key={att.id}>
            <button
              type="button"
              className="ticket-attachments__link"
              onClick={() => openPreview(att)}
            >
              {att.file_name}
              {att.size_bytes ? (
                <span className="ticket-attachments__size"> ({formatSize(att.size_bytes)})</span>
              ) : null}
            </button>
            {att.note ? <span className="ticket-attachments__note"> — {att.note}</span> : null}
          </li>
        ))}
      </ul>

      <TicketAttachmentPreviewModal
        open={Boolean(preview)}
        attachment={preview?.attachment}
        downloadPrefix={downloadPrefix}
        loading={preview?.loading}
        error={preview?.error}
        blobUrl={preview?.blobUrl}
        textContent={preview?.textContent}
        onClose={closePreview}
      />
    </>
  )
}
