import { ClinicalVisibilityBadge } from './ClinicalVisibilityBadge.jsx'

const TYPE_ICONS = {
  PDF:        '📄',
  IMG:        '🖼',
  IMAGE:      '🖼',
  ASSESSMENT: '📊',
  VIDEO:      '🎥',
  AUDIO:      '🎙',
}

/**
 * Document drive card.
 * doc: { title, fileType, uploadedDate, uploadedBy, visibility, linkedEntity }
 * onView, onDownload: optional callbacks (only rendered if provided)
 */
export function ClinicalDocumentCard({ doc, onView, onDownload }) {
  const icon = TYPE_ICONS[(doc.fileType || '').toUpperCase()] || '📁'

  return (
    <div className="clinical-document-card">
      <div className="clinical-document-card__icon-wrap" aria-hidden="true">{icon}</div>
      <div className="clinical-document-card__body">
        <p className="clinical-document-card__title">
          {doc.title}
          {doc.fileType ? <span className="clinical-document-card__type-badge">{doc.fileType.toUpperCase()}</span> : null}
        </p>
        <p className="clinical-document-card__meta">
          {doc.uploadedDate ? `Uploaded: ${doc.uploadedDate}` : null}
          {doc.uploadedBy ? ` · By: ${doc.uploadedBy}` : null}
        </p>
        {doc.linkedEntity ? (
          <p className="clinical-document-card__meta" style={{ marginTop: '0.2rem' }}>
            Linked: {doc.linkedEntity}
          </p>
        ) : null}
        {doc.visibility ? (
          <div style={{ marginTop: '0.35rem' }}>
            <ClinicalVisibilityBadge visibility={doc.visibility} />
          </div>
        ) : null}
      </div>
      <div className="clinical-document-card__actions">
        {onView ? (
          <button type="button" className="clinical-btn-ghost" style={{ fontSize: '0.75rem', minHeight: '32px' }} onClick={() => onView(doc)}>
            View
          </button>
        ) : null}
        {onDownload ? (
          <button type="button" className="clinical-btn-ghost" style={{ fontSize: '0.75rem', minHeight: '32px' }} onClick={() => onDownload(doc)}>
            Download
          </button>
        ) : null}
      </div>
    </div>
  )
}
