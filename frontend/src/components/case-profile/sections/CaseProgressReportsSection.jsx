import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../../lib/apiClient.js'
import { unwrapList } from '../../../lib/listApi.js'
import { ClinicalStatusBadge } from '../../clinical-ui/ClinicalStatusBadge.jsx'
import { ClinicalCard } from '../../clinical-ui/ClinicalCard.jsx'
import { ClinicalProgressBar } from '../../clinical-ui/ClinicalProgressBar.jsx'
import { ClinicalDocumentCard } from '../../clinical-ui/ClinicalDocumentCard.jsx'

const PROGRESS_TYPES = [
  { id: 'SIX_MONTH',   label: '6-month Review' },
  { id: 'ANNUAL',      label: 'Annual Progress' },
  { id: 'MILESTONE',   label: 'Milestone' },
  { id: 'HANDOVER',    label: 'Handover' },
  { id: 'TERMINATION', label: 'Transition / Termination' },
]

const EDIT_BASE = {
  therapist: '/therapist/reports/edit',
  admin:     '/admin/reports/edit',
}

export function CaseProgressReportsSection({ caseId, caseCode, childName, variant = 'therapist' }) {
  const [reports, setReports] = useState([])
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedType, setSelectedType] = useState('SIX_MONTH')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [monthly, docs] = await Promise.all([
        apiFetch('/api/v1/reports/monthly?page_size=100').catch(() => []),
        apiFetch(`/api/v1/cases/${caseId}/documents`).catch(() => []),
      ])
      const all = unwrapList(monthly)
      setReports(all.filter((r) => r.case_id === Number(caseId) && r.category === 'PROGRESS'))
      const docList = unwrapList(docs)
      setDocuments(
        docList.filter((d) =>
          ['MONTHLY_PROGRESS_REPORT', 'ANNUAL_PROGRESS_REPORT', 'TERMINATION_PROGRESS_REPORT'].includes(d.category),
        ),
      )
    } catch {
      setReports([])
      setDocuments([])
    } finally {
      setLoading(false)
    }
  }, [caseId])

  useEffect(() => { load() }, [load])

  if (loading) return <p className="ic-case-panel__loading">Loading progress reports…</p>

  const editBase = EDIT_BASE[variant] || EDIT_BASE.therapist

  /* Filter by selected type */
  const filteredReports = reports.filter((r) => r.sub_category === selectedType || reports.length === 0)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
      <div className="clinical-page-header">
        <h2 className="clinical-section-heading">Progress Reports</h2>
        <p className="clinical-section-subtitle">
          Aggregate goal and domain evidence over longer periods for <strong>{childName}</strong> ({caseCode}).
        </p>
      </div>

      {/* Report type selector */}
      <div className="clinical-report-type-selector">
        {PROGRESS_TYPES.map((pt) => (
          <button
            key={pt.id}
            type="button"
            className={`clinical-report-type-btn${selectedType === pt.id ? ' is-active' : ''}`}
            onClick={() => setSelectedType(pt.id)}
          >
            {pt.label}
          </button>
        ))}
      </div>

      {/* Latest progress report card */}
      {filteredReports.length > 0 ? (
        filteredReports.map((r) => {
          const typeLabel = PROGRESS_TYPES.find((t) => t.id === r.sub_category)?.label || r.sub_category || 'Progress'
          const editable = r.status === 'DRAFT' || r.status === 'REJECTED'
          return (
            <ClinicalCard key={r.id}>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
                <div>
                  <h3 style={{ fontSize: '1.0625rem', fontWeight: 700, margin: '0 0 0.2rem' }}>{typeLabel}</h3>
                  <p className="cp-hint" style={{ margin: 0 }}>{r.month || '—'}</p>
                </div>
                <ClinicalStatusBadge status={r.status} />
              </div>

              {r.summary ? (
                <p style={{ fontSize: '0.875rem', color: '#334155', margin: '0 0 0.75rem', lineHeight: 1.5 }}>{r.summary}</p>
              ) : null}

              {/* Goal journey progress bars (placeholder from report data) */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '0.875rem' }}>
                <ClinicalProgressBar label="Overall goal progress" pct={r.progress_pct || 65} variant="green" />
                <ClinicalProgressBar label="Evidence documentation" pct={r.evidence_pct || 50} />
              </div>

              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.375rem' }}>
                {editable ? (
                  <Link to={`${editBase}/${r.id}`} className="clinical-btn-primary" style={{ fontSize: '0.8125rem', minHeight: '40px', padding: '0.4rem 0.875rem' }}>
                    Continue Editing →
                  </Link>
                ) : (
                  <Link to={`${editBase}/${r.id}`} className="clinical-btn-ghost" style={{ fontSize: '0.8125rem', minHeight: '36px' }}>
                    View Report →
                  </Link>
                )}
              </div>
            </ClinicalCard>
          )
        })
      ) : (
        <div className="clinical-empty-state cp-card">
          <span style={{ fontSize: '1.5rem' }} aria-hidden="true">📊</span>
          <p className="clinical-empty-state__title">No {PROGRESS_TYPES.find((t) => t.id === selectedType)?.label} report yet</p>
          <p className="clinical-empty-state__body">
            Your case manager may request this report when due. Progress reports are compiled from monthly report data and goal evidence.
          </p>
        </div>
      )}

      {/* Uploaded progress documents */}
      {documents.length > 0 ? (
        <div>
          <h4 style={{ fontSize: '0.875rem', fontWeight: 700, margin: '0 0 0.5rem', color: 'var(--clinical-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Uploaded Documents
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {documents.map((d) => (
              <ClinicalDocumentCard
                key={d.id}
                doc={{
                  title:      d.title,
                  fileType:   d.file_type || 'PDF',
                  visibility: 'internal',
                  linkedEntity: d.category?.replace(/_/g, ' '),
                }}
              />
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}
