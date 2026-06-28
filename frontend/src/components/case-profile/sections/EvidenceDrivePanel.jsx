import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../../context/AuthContext.jsx'
import { formatDisplayDate } from '../../../lib/datetime.js'
import { isReportsRevampActive } from '../../../lib/reportsRevampFlags.js'
import { useCaseDocumentsList } from '../../../hooks/useCaseDocuments.js'
import { CaseDocumentsPanel } from '../../documents/CaseDocumentsPanel.jsx'
import { ClinicalDocumentCard } from '../../clinical-ui/ClinicalDocumentCard.jsx'
import { ClinicalEmptyState } from '../../clinical-ui/ClinicalEmptyState.jsx'
import { ClinicalPrimaryButton } from '../../clinical-ui/ClinicalPrimaryButton.jsx'

const TYPE_FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'pdf', label: 'PDFs' },
  { id: 'image', label: 'Images' },
  { id: 'assessment', label: 'Assessments' },
]

function fileTypeForDoc(doc) {
  const mime = doc.current_version?.mime_type || ''
  const name = (doc.current_version?.file_name || doc.title || '').toLowerCase()
  const category = (doc.category || '').toUpperCase()

  if (mime.includes('pdf') || name.endsWith('.pdf')) return 'PDF'
  if (mime.startsWith('image/') || /\.(png|jpe?g|gif|webp|heic)$/i.test(name)) return 'IMG'
  if (category.includes('OBSERVATION') || category.includes('ASSESSMENT')) return 'ASSESSMENT'
  if (doc.current_version?.source_type === 'EXTERNAL_LINK') return 'LINK'
  return 'FILE'
}

function matchesTypeFilter(doc, filterId) {
  if (filterId === 'all') return true
  const type = fileTypeForDoc(doc)
  if (filterId === 'pdf') return type === 'PDF'
  if (filterId === 'image') return type === 'IMG'
  if (filterId === 'assessment') return type === 'ASSESSMENT'
  return true
}

function DocumentDriveView({ caseId, variant, monthlyReportsPath }) {
  const { can } = useAuth()
  const canCreate = can('case_document.create')
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [selectedId, setSelectedId] = useState(null)

  const { data: list = [], isLoading } = useCaseDocumentsList(caseId, {})

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return list.filter((doc) => {
      if (!matchesTypeFilter(doc, typeFilter)) return false
      if (!q) return true
      const hay = [
        doc.title,
        doc.current_version?.file_name,
        doc.category,
        doc.uploaded_by_name,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
      return hay.includes(q)
    })
  }, [list, search, typeFilter])

  return (
    <div className="cp-document-drive">
      <header className="cp-document-drive__header">
        <div>
          <h2 className="clinical-section-heading">Document Drive</h2>
          <p className="clinical-section-subtitle">
            Reference files, assessments, session photos, and uploads linked to this case.
          </p>
        </div>
      </header>

      <div className="cp-document-drive__toolbar">
        <label className="cp-document-drive__search">
          <span className="cp-document-drive__search-icon" aria-hidden="true">
            🔍
          </span>
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search documents…"
            aria-label="Search documents"
          />
        </label>

        <div className="clinical-filter-chips cp-document-drive__filters" role="group" aria-label="Filter by type">
          {TYPE_FILTERS.map((chip) => (
            <button
              key={chip.id}
              type="button"
              className={`clinical-filter-chip${typeFilter === chip.id ? ' is-active' : ''}`}
              onClick={() => setTypeFilter(chip.id)}
            >
              {chip.label}
            </button>
          ))}
        </div>

        {canCreate ? (
          <ClinicalPrimaryButton
            type="button"
            className="cp-document-drive__upload"
            onClick={() => setSelectedId('__create__')}
          >
            Upload
          </ClinicalPrimaryButton>
        ) : null}
      </div>

      {monthlyReportsPath ? (
        <p className="cp-document-drive__hint">
          In-app monthly report (rich text):{' '}
          <Link to={monthlyReportsPath}>Open Monthly Reports →</Link>
        </p>
      ) : null}

      {isLoading ? (
        <p className="ic-case-detail__loading">Loading documents…</p>
      ) : filtered.length === 0 ? (
        <ClinicalEmptyState
          variant="upload"
          icon="📁"
          title="No documents yet"
          body="Upload a file or add a Google link to build this case’s evidence drive."
        />
      ) : (
        <div className="cp-document-drive__grid">
          {filtered.map((doc) => (
            <button
              key={doc.id}
              type="button"
              className="cp-document-drive__card-btn"
              onClick={() => setSelectedId(doc.id)}
            >
              <ClinicalDocumentCard
                doc={{
                  title: doc.title,
                  fileType: fileTypeForDoc(doc),
                  uploadedDate: doc.created_at ? formatDisplayDate(doc.created_at) : '',
                  uploadedBy: doc.uploaded_by_name || doc.created_by_name || '',
                  visibility: doc.visibility === 'parent' ? 'parent' : 'internal',
                }}
              />
            </button>
          ))}
        </div>
      )}

      <CaseDocumentsPanel
        caseId={caseId}
        variant={variant}
        monthlyReportsPath={monthlyReportsPath}
        presentation="embedded"
        externalSelectedId={selectedId === '__create__' ? null : selectedId}
        externalCreateOpen={selectedId === '__create__'}
        onExternalClose={() => setSelectedId(null)}
      />
    </div>
  )
}

/** Evidence Drive — case documents grouped for clinical context. */
export function EvidenceDrivePanel({ caseId, variant = 'therapist' }) {
  const monthlyReportsPath =
    variant === 'admin'
      ? `/admin/reports?case_id=${caseId}`
      : `/therapist/reports?case_id=${caseId}`

  if (isReportsRevampActive(variant === 'admin' ? 'admin' : 'therapist')) {
    return (
      <DocumentDriveView
        caseId={caseId}
        variant={variant}
        monthlyReportsPath={monthlyReportsPath}
      />
    )
  }

  return (
    <CaseDocumentsPanel
      caseId={caseId}
      variant={variant}
      monthlyReportsPath={monthlyReportsPath}
    />
  )
}
