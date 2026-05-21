import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { CreateDraftModal } from '../monthly-reports/CreateDraftModal.jsx'

const STATUS_LABELS = {
  DRAFT: { label: 'Draft', tone: 'muted' },
  UNDER_REVIEW: { label: 'With admin', tone: 'warn' },
  APPROVED: { label: 'Approved', tone: 'ok' },
  REJECTED: { label: 'Needs revision', tone: 'danger' },
  PUBLISHED: { label: 'Shared with family', tone: 'ok' },
}

const REPORTS_EDIT_BASE = '/therapist/reports/edit'

function defaultMonthLabel() {
  const d = new Date()
  return d.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
}

export function CaseReportsPanel({ caseId, caseCode, childName, onUpdated }) {
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const rows = await apiFetch('/api/v1/reports/monthly?page_size=100')
      setReports(unwrapList(rows).filter((r) => r.case_id === caseId))
    } catch {
      setReports([])
    } finally {
      setLoading(false)
    }
  }, [caseId])

  useEffect(() => {
    load()
  }, [load])

  const draft = useMemo(() => reports.find((r) => r.status === 'DRAFT' || r.status === 'REJECTED'), [reports])
  const inReview = useMemo(() => reports.find((r) => r.status === 'UNDER_REVIEW'), [reports])

  async function handleSubmit(reportId) {
    setError('')
    try {
      await apiFetch(`/api/v1/reports/monthly/${reportId}/submit`, { method: 'POST' })
      await load()
      onUpdated?.()
    } catch (err) {
      setError(err.message || 'Could not submit report')
    }
  }

  if (loading) return <p className="ic-case-panel__loading">Loading reports…</p>

  return (
    <div className="ic-reports-flow">
      <p className="ic-reports-flow__intro">
        Monthly progress for <strong>{childName}</strong> ({caseCode}). Write in the rich-text editor, then submit for
        admin review before families can read it.
      </p>

      <div className="ic-reports-flow__status-row">
        {draft ? (
          <div className="ic-reports-flow__banner ic-reports-flow__banner--action">
            <p>
              <strong>{draft.month}</strong> — ready to finish ({draft.status})
            </p>
            <div className="ic-reports-flow__form-actions">
              <Link to={`${REPORTS_EDIT_BASE}/${draft.id}`} className="ic-btn ic-btn--primary">
                Continue writing
              </Link>
              <button type="button" className="ic-btn ic-btn--accent" onClick={() => handleSubmit(draft.id)}>
                Submit for review
              </button>
            </div>
          </div>
        ) : inReview ? (
          <div className="ic-reports-flow__banner ic-reports-flow__banner--wait">
            <p>
              <strong>{inReview.month}</strong> is with admin for review.
            </p>
          </div>
        ) : (
          <div className="ic-reports-flow__banner">
            <p>No draft this cycle. Create a monthly report when you are ready.</p>
            <button type="button" className="ic-btn ic-btn--primary" onClick={() => setShowModal(true)}>
              New monthly report
            </button>
          </div>
        )}
      </div>

      {error ? <p className="ic-session-composer__error">{error}</p> : null}

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

      {reports.length === 0 && !showModal ? (
        <p className="ic-case-panel__muted">No monthly reports yet for this client.</p>
      ) : (
        <ul className="ic-reports-flow__list">
          {reports.map((r) => {
            const meta = STATUS_LABELS[r.status] || { label: r.status, tone: 'muted' }
            const editable = r.status === 'DRAFT' || r.status === 'REJECTED'
            return (
              <li key={r.id} className={`ic-reports-flow__card ic-reports-flow__card--${meta.tone}`}>
                <div className="ic-reports-flow__card-head">
                  <strong>{r.month}</strong>
                  <span className={`ic-reports-flow__pill ic-reports-flow__pill--${meta.tone}`}>{meta.label}</span>
                </div>
                <p className="ic-reports-flow__summary">{r.summary || '—'}</p>
                {r.reviewer_comment ? (
                  <p className="ic-reports-flow__reviewer">Admin: {r.reviewer_comment}</p>
                ) : null}
                <div className="ic-reports-flow__form-actions">
                  {editable ? (
                    <>
                      <Link to={`${REPORTS_EDIT_BASE}/${r.id}`} className="ic-btn ic-btn--ghost">
                        {r.status === 'REJECTED' ? 'Revise' : 'Continue'}
                      </Link>
                      <button type="button" className="ic-btn ic-btn--accent" onClick={() => handleSubmit(r.id)}>
                        Submit for review
                      </button>
                    </>
                  ) : null}
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
