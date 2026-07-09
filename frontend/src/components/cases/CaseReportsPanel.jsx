import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  listMonthlyReports,
  submitMonthlyReport,
} from '../../lib/monthlyReportApi.js'
import { CreateDraftModal } from '../monthly-reports/CreateDraftModal.jsx'
import { ClinicalStatusBadge } from '../clinical-ui/ClinicalStatusBadge.jsx'
import { ClinicalCard } from '../clinical-ui/ClinicalCard.jsx'
import { ClinicalProgressBar } from '../clinical-ui/ClinicalProgressBar.jsx'
import { ClinicalPrimaryButton } from '../clinical-ui/ClinicalPrimaryButton.jsx'
import { ClinicalGhostButton } from '../clinical-ui/ClinicalGhostButton.jsx'

const STATUS_LABELS = {
  DRAFT:        { label: 'Draft',             tone: 'muted' },
  UNDER_REVIEW: { label: 'With admin',         tone: 'warn'  },
  APPROVED:     { label: 'Approved',           tone: 'ok'    },
  REJECTED:     { label: 'Needs revision',     tone: 'danger' },
  PUBLISHED:    { label: 'Shared with family', tone: 'ok'    },
}

const DEFAULT_EDIT_BASE = '/therapist/reports/edit'

function defaultMonthLabel() {
  return new Date().toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
}

export function CaseReportsPanel({ caseId, caseCode, childName, onUpdated, editBase = DEFAULT_EDIT_BASE }) {
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const rows = await listMonthlyReports({ caseId })
      setReports(rows)
    } catch {
      setReports([])
    } finally {
      setLoading(false)
    }
  }, [caseId])

  useEffect(() => { load() }, [load])

  const draft    = useMemo(() => reports.find((r) => r.status === 'DRAFT' || r.status === 'REJECTED'), [reports])
  const inReview = useMemo(() => reports.find((r) => r.status === 'UNDER_REVIEW'), [reports])
  const published = useMemo(() => reports.filter((r) => r.status === 'PUBLISHED' || r.status === 'APPROVED'), [reports])
  const history   = useMemo(() => reports.slice().reverse(), [reports])

  async function handleSubmit(reportId) {
    setError('')
    try {
      await submitMonthlyReport(reportId)
      await load()
      onUpdated?.()
    } catch (err) {
      setError(err.message || 'Could not submit report')
    }
  }

  if (loading) return <p className="ic-case-panel__loading">Loading reports…</p>

  /* Evidence readiness mock values (derived from report data) */
  const evidenceScore = reports.length > 0 ? Math.min(90, 20 + reports.length * 10) : 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
      <p className="clinical-section-subtitle" style={{ marginBottom: '0 ' }}>
        Monthly progress for <strong>{childName}</strong> ({caseCode}). Submit drafts for admin review before families can read them.
      </p>

      {/* Current month card */}
      <ClinicalCard>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.875rem' }}>
          <div>
            <h3 style={{ margin: '0 0 0.2rem', fontSize: '0.9375rem', fontWeight: 800 }}>
              {defaultMonthLabel()}
            </h3>
            <p className="cp-hint" style={{ margin: 0 }}>Current reporting cycle</p>
          </div>
          {draft ? (
            <ClinicalStatusBadge status={draft.status} />
          ) : inReview ? (
            <ClinicalStatusBadge status="UNDER_REVIEW" />
          ) : (
            <ClinicalStatusBadge status="DRAFT" customLabel="Not started" />
          )}
        </div>

        <ClinicalProgressBar label="Evidence quality" pct={evidenceScore} />

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.875rem' }}>
          {draft ? (
            <>
              <Link to={`${editBase}/${draft.id}`} className="clinical-btn-primary" style={{ fontSize: '0.8125rem', minHeight: '40px', padding: '0.4rem 0.875rem' }}>
                Open Monthly Builder →
              </Link>
              <button type="button" className="clinical-btn-secondary" style={{ fontSize: '0.8125rem', minHeight: '40px', padding: '0.4rem 0.875rem' }} onClick={() => handleSubmit(draft.id)}>
                Submit for Review
              </button>
            </>
          ) : inReview ? (
            <span className="cp-hint" style={{ alignSelf: 'center' }}>Report is with admin. Waiting for review.</span>
          ) : (
            <>
              <ClinicalPrimaryButton onClick={() => setShowModal(true)}>
                + Create Monthly Report
              </ClinicalPrimaryButton>
            </>
          )}
        </div>

        {error ? <p className="ic-case-panel__error" style={{ marginTop: '0.5rem' }}>{error}</p> : null}
      </ClinicalCard>

      <div className="clinical-two-col">
        {/* Left: history */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <h4 style={{ fontSize: '0.875rem', fontWeight: 700, margin: '0 0 0.25rem', color: 'var(--clinical-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Report History
          </h4>
          {history.length === 0 ? (
            <div className="clinical-empty-state" style={{ background: '#fff', border: '1px dashed var(--clinical-border)', borderRadius: 'var(--clinical-radius-card)', padding: '1.25rem' }}>
              <p className="clinical-empty-state__body">No monthly reports yet for this client.</p>
            </div>
          ) : (
            history.map((r) => {
              const meta    = STATUS_LABELS[r.status] || { label: r.status }
              const editable = r.status === 'DRAFT' || r.status === 'REJECTED'
              return (
                <ClinicalCard key={r.id} className={editable ? 'clinical-case-queue-card' : ''}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.375rem', marginBottom: '0.5rem' }}>
                    <strong style={{ fontSize: '0.9375rem', color: '#0f172a' }}>{r.month}</strong>
                    <ClinicalStatusBadge status={r.status} />
                  </div>
                  {r.summary ? <p style={{ fontSize: '0.8125rem', color: '#334155', margin: '0 0 0.5rem', lineHeight: 1.5 }}>{r.summary}</p> : null}
                  {r.reviewer_comment ? (
                    <p className="cp-hint cp-hint--warn" style={{ marginBottom: '0.5rem' }}>
                      Admin: {r.reviewer_comment}
                    </p>
                  ) : null}
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.375rem' }}>
                    {editable ? (
                      <>
                        <Link to={`${editBase}/${r.id}`} className="clinical-btn-ghost" style={{ fontSize: '0.8125rem', minHeight: '36px' }}>
                          {r.status === 'REJECTED' ? 'Revise' : 'Continue'}
                        </Link>
                        <button type="button" className="clinical-btn-secondary" style={{ fontSize: '0.8125rem', minHeight: '36px', padding: '0.375rem 0.75rem' }} onClick={() => handleSubmit(r.id)}>
                          Submit for review
                        </button>
                      </>
                    ) : (
                      <Link to={`${editBase}/${r.id}`} className="clinical-btn-ghost" style={{ fontSize: '0.8125rem', minHeight: '36px' }}>
                        View report →
                      </Link>
                    )}
                  </div>
                </ClinicalCard>
              )
            })
          )}
        </div>

        {/* Right: evidence readiness */}
        <div className="clinical-evidence-panel">
          <h4 className="clinical-evidence-panel__title">Evidence Readiness</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
            <ClinicalProgressBar label="Logs completed" pct={evidenceScore} />
            <ClinicalProgressBar label="Goals with evidence" pct={Math.max(0, evidenceScore - 15)} variant="green" />
            <ClinicalProgressBar label="Strategies documented" pct={Math.max(0, evidenceScore - 25)} variant="amber" />
          </div>
          {evidenceScore < 50 ? (
            <p className="clinical-evidence-panel__text" style={{ marginTop: '0.75rem', color: 'var(--clinical-amber)' }}>
              ⚠ Some evidence areas need attention before the monthly report can be finalised.
            </p>
          ) : (
            <p className="clinical-evidence-panel__text" style={{ marginTop: '0.75rem', color: 'var(--clinical-green)' }}>
              ✓ Evidence is looking good for this cycle.
            </p>
          )}
        </div>
      </div>

      <CreateDraftModal
        open={showModal}
        onClose={() => setShowModal(false)}
        defaultMonth={defaultMonthLabel()}
        defaultCaseId={caseId}
        onCreated={() => {
          setShowModal(false)
          load()
          onUpdated?.()
        }}
      />
    </div>
  )
}
