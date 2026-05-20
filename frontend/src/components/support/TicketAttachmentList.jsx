import { apiDownload } from '../../lib/apiClient.js'

export function TicketAttachmentList({ attachments = [], downloadPrefix = '/api/v1/tickets' }) {
  if (!attachments?.length) return null

  return (
    <ul className="ticket-attachments">
      {attachments.map((att) => (
        <li key={att.id}>
          <button
            type="button"
            className="ticket-attachments__link"
            onClick={() =>
              apiDownload(`${downloadPrefix}/attachments/${att.id}/download`, att.file_name).catch((err) =>
                alert(err.message || 'Could not download'),
              )
            }
          >
            {att.file_name}
            {att.size_bytes ? (
              <span className="ticket-attachments__size">
                {' '}
                ({att.size_bytes < 1024 * 1024
                  ? `${Math.round(att.size_bytes / 1024)} KB`
                  : `${(att.size_bytes / (1024 * 1024)).toFixed(1)} MB`})
              </span>
            ) : null}
          </button>
        </li>
      ))}
    </ul>
  )
}
