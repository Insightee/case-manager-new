import { useState } from 'react'
import { InternalVsFamilyBanner } from './InternalVsFamilyBanner.jsx'
import { AiPreviewButton } from './AiPreviewButton.jsx'
import { MONTHLY_EVIDENCE_V2 } from '../../lib/reportsRevampFlags.js'
import { apiFetch } from '../../lib/apiClient.js'
import { ParentMonthlyPreview } from './parent/ParentMonthlyPreview.jsx'
import { ParentSafeContentBadge } from './parent/ParentSafeContentBadge.jsx'
import { ClinicalSectionRail } from '../clinical-ui/ClinicalSectionRail.jsx'
import { ClinicalActionButton } from '../clinical-ui/ClinicalActionButton.jsx'

const DEFAULT_SECTIONS = [
  { key: 'month_summary', label: 'Month at a Glance', visibility: 'parent' },
  { key: 'goal_progress', label: 'Goal Progress', visibility: 'parent' },
  { key: 'what_helped', label: 'What Helped', visibility: 'parent' },
  { key: 'support_barriers', label: 'Support Barriers', visibility: 'internal' },
  { key: 'parent_summary', label: 'Parent-Safe Summary', visibility: 'parent' },
  { key: 'next_month_focus', label: 'Next Month Focus', visibility: 'parent' },
  { key: 'cm_internal_notes', label: 'Internal CM Notes', visibility: 'cm' },
  { key: 'evidence_annexure', label: 'Evidence Annexure', visibility: 'internal' },
]

const CONFIDENCE_LEVELS = [
  { id: 'low', label: 'Low', cls: 'is-active--low' },
  { id: 'emerging', label: 'Emerging', cls: 'is-active--emerging' },
  { id: 'consistent', label: 'Consistent', cls: 'is-active--consistent' },
  { id: 'review', label: 'Needs Review', cls: 'is-active--review' },
]

export function MonthlyReportBuilderSections({ caseId, childName, reportId, onInsertDraft }) {
  const [compileMsg, setCompileMsg] = useState('')
  const [preview, setPreview] = useState(null)
  const [confidence, setConfidence] = useState({})

  async function compileFromEvidence() {
    if (!reportId || !MONTHLY_EVIDENCE_V2) return
    setCompileMsg('')
    try {
      await apiFetch(`/api/v1/reports/monthly/${reportId}/compile-evidence-v2`, { method: 'POST' })
      setCompileMsg('Sections compiled from session evidence (draft only).')
    } catch (err) {
      setCompileMsg(err.message || 'Compile failed')
    }
  }

  async function loadParentPreview() {
    if (!reportId) return
    try {
      const data = await apiFetch(`/api/v1/reports/monthly/${reportId}/parent-preview`)
      setPreview(data)
    } catch {
      setPreview(null)
    }
  }

  function setConfidenceFor(key, level) {
    setConfidence((prev) => ({ ...prev, [key]: prev[key] === level ? null : level }))
  }

  return (
    <ClinicalSectionRail
      title="Report Sections"
      note="Internal clinical notes are not shared with parents unless included in a published family section."
      aiNote="Draft suggestion only — never auto-published."
      sections={DEFAULT_SECTIONS}
      footer={(
        <>
          <AiPreviewButton
            action="monthly_summary"
            caseId={caseId}
            context={{ child_name: childName }}
            onDraft={(text) => onInsertDraft?.(text)}
            label="Preview summary (mock AI)"
          />
          {MONTHLY_EVIDENCE_V2 && reportId ? (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.375rem', marginTop: '0.75rem' }}>
              <ClinicalActionButton variant="secondary" onClick={compileFromEvidence}>
                Generate from Logs
              </ClinicalActionButton>
              <ClinicalActionButton variant="ghost" onClick={loadParentPreview}>
                Preview Parent Version
              </ClinicalActionButton>
              {compileMsg ? <p className="clinical-quality-card__stat-label" style={{ width: '100%' }}>{compileMsg}</p> : null}
            </div>
          ) : null}
          {DEFAULT_SECTIONS.find((s) => s.key === 'goal_progress') ? (
            <div className="clinical-confidence-selector" style={{ marginTop: '0.75rem' }}>
              <p className="clinical-quality-card__stat-label" style={{ marginBottom: '0.375rem' }}>Goal progress confidence</p>
              {CONFIDENCE_LEVELS.map((lv) => (
                <button
                  key={lv.id}
                  type="button"
                  className={`clinical-confidence-btn${confidence.goal_progress === lv.id ? ` ${lv.cls}` : ''}`}
                  onClick={() => setConfidenceFor('goal_progress', lv.id)}
                >
                  {lv.label}
                </button>
              ))}
            </div>
          ) : null}
          {preview ? (
            <div style={{ marginTop: '1rem', borderTop: '1px solid var(--clinical-border)', paddingTop: '0.875rem' }}>
              <ParentSafeContentBadge />
              <ParentMonthlyPreview preview={preview} reportId={reportId} />
            </div>
          ) : null}
        </>
      )}
    />
  )
}
