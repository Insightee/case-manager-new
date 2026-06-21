import { useCallback, useEffect, useState } from 'react'
import { CaseDocumentsPanel } from '../../documents/CaseDocumentsPanel.jsx'
import { EVIDENCE_DRIVE_V2 } from '../../../lib/reportsRevampFlags.js'
import { apiFetch } from '../../../lib/apiClient.js'
import { ClinicalDocumentCard } from '../../clinical-ui/ClinicalDocumentCard.jsx'
import { ClinicalEmptyState } from '../../clinical-ui/ClinicalEmptyState.jsx'

const FILTER_CHIPS = [
  { id: 'all',            label: 'All' },
  { id: 'parent_visible', label: 'Parent Visible' },
  { id: 'internal_only',  label: 'Internal Only' },
  { id: 'goal_linked',    label: 'Goal Linked' },
  { id: 'report_linked',  label: 'Report Linked' },
  { id: 'strategy_linked', label: 'Strategy Linked' },
]

function visibilityFor(item) {
  if (item.visibility === 'parent') return 'parent'
  if (item.visibility === 'internal' || item.group_key?.includes('internal')) return 'internal'
  return 'internal'
}

/** Evidence Drive — case documents grouped for clinical context. */
export function EvidenceDrivePanel({ caseId, variant = 'therapist' }) {
  const [groups, setGroups] = useState([])
  const [filter, setFilter] = useState('all')

  const load = useCallback(async () => {
    if (!EVIDENCE_DRIVE_V2) return
    try {
      const data = await apiFetch(`/api/v1/cases/${caseId}/evidence-drive`)
      setGroups(data.groups || [])
    } catch {
      setGroups([])
    }
  }, [caseId])

  useEffect(() => { load() }, [load])

  const filteredGroups = groups.filter((g) => {
    if (filter === 'all') return true
    if (filter === 'parent_visible') return g.items?.some((i) => i.visibility === 'parent')
    if (filter === 'internal_only') return g.items?.some((i) => i.visibility !== 'parent')
    return g.group_key === filter || g.group_key.startsWith(filter)
  })

  /* Flatten all items for the clinical card list */
  const allItems = filteredGroups.flatMap((g) =>
    (g.items || [{ id: g.group_key, title: g.group_key.replace(/_/g, ' '), count: g.items?.length }]).map((item) => ({
      ...item,
      groupKey: g.group_key,
      visibility: item.visibility || (g.group_key.includes('parent') ? 'parent' : 'internal'),
    }))
  )

  return (
    <div>
      <div style={{ marginBottom: '0.875rem' }}>
        <h2 className="clinical-section-heading">Evidence Drive</h2>
        <p className="clinical-section-subtitle">
          Reference files, observation exports, monthly PDFs, and uploads linked to this case.
        </p>
      </div>

      {/* Filter chips */}
      <div className="clinical-filter-chips" role="group" aria-label="Filter evidence">
        {FILTER_CHIPS.map((chip) => (
          <button
            key={chip.id}
            type="button"
            className={`clinical-filter-chip${filter === chip.id ? ' is-active' : ''}`}
            onClick={() => setFilter(chip.id)}
          >
            {chip.label}
          </button>
        ))}
      </div>

      {/* Clinical document cards grid from evidence-drive API */}
      {EVIDENCE_DRIVE_V2 && allItems.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1rem' }}>
          {allItems.map((item, idx) => (
            <ClinicalDocumentCard
              key={item.id || idx}
              doc={{
                title:        item.title || item.name || item.group_key?.replace(/_/g, ' ') || 'Document',
                fileType:     item.file_type || item.fileType || 'PDF',
                uploadedDate: item.uploaded_at?.slice(0, 10),
                uploadedBy:   item.uploaded_by,
                visibility:   visibilityFor(item),
                linkedEntity: item.linked_entity,
              }}
            />
          ))}
        </div>
      ) : EVIDENCE_DRIVE_V2 ? (
        <ClinicalEmptyState
          variant="upload"
          icon="📁"
          title="No documents yet"
          body="Upload a file or add a Google link."
        />
      ) : null}

      {/* Existing document upload panel stays intact */}
      <CaseDocumentsPanel
        caseId={caseId}
        variant={variant}
        monthlyReportsPath={
          variant === 'admin'
            ? `/admin/reports?case_id=${caseId}`
            : `/therapist/reports?case_id=${caseId}`
        }
      />
    </div>
  )
}
