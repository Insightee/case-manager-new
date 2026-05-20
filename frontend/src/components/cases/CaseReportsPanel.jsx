import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'

const STATUS_LABELS = {
  DRAFT: { label: 'Draft', tone: 'muted' },
  UNDER_REVIEW: { label: 'With admin', tone: 'warn' },
  APPROVED: { label: 'Approved', tone: 'ok' },
  REJECTED: { label: 'Needs revision', tone: 'danger' },
  PUBLISHED: { label: 'Shared with family', tone: 'ok' },
}

function defaultMonthLabel() {
  const d = new Date()
  return d.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
}

export function CaseReportsPanel({ caseId, caseCode, childName, onUpdated }) {
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [month, setMonth] = useState(() => defaultMonthLabel())
  const [summary, setSummary] = useState('')
  const [submitting, setSubmitting] = useState(false)
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

  async function handleCreate(e) {
    e.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      await apiFetch('/api/v1/reports/monthly', {
        method: 'POST',
        body: JSON.stringify({ case_id: caseId, month, summary }),
      })
      setShowForm(false)
      setSummary('')
      await load()
      onUpdated?.()
    } catch (err) {
      setError(err.message || 'Could not create report')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <p className="ic-case-panel__loading">Loading reports…</p>

  return (
    <div className="ic-reports-flow">
      <p className="ic-reports-flow__intro">
        Monthly progress for <strong>{childName}</strong> ({caseCode}). Save a draft, then submit for admin review before
        families can read it.
      </p>

      <div className="ic-reports-flow__status-row">
        {draft ? (
          <div className="ic-reports-flow__banner ic-reports-flow__banner--action">
            <p>
              <strong>{draft.month}</strong> — ready to finish ({draft.status})
            </p>
            <button type="button" className="ic-btn ic-btn--accent" onClick={() => handleSubmit(draft.id)}>
              Submit for review
            </button>
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
            <button type="button" className="ic-btn ic-btn--primary" onClick={() => setShowForm(true)}>
              New monthly report
            </button>
          </div>
        )}
      </div>

      {showForm ? (
        <form onSubmit={handleCreate} className="ic-reports-flow__form">
          <h3 className="ic-reports-flow__form-title">New monthly report</h3>
          <label className="ic-session-composer__field">
            <span>Month</span>
            <input
              required
              value={month}
              onChange={(e) => setMonth(e.target.value)}
              placeholder="e.g. May 2026"
              className="ic-session-composer__input"
            />
          </label>
          <label className="ic-session-composer__field">
            <span>Summary</span>
            <textarea
              required
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              rows={5}
              className="ic-session-composer__input"
              placeholder="Goals worked on, progress, recommendations for family…"
            />
          </label>
          {error ? <p className="ic-session-composer__error">{error}</p> : null}
          <div className="ic-reports-flow__form-actions">
            <button type="submit" disabled={submitting} className="ic-btn ic-btn--accent">
              {submitting ? 'Saving…' : 'Save draft'}
            </button>
            <button type="button" className="ic-btn ic-btn--ghost" onClick={() => setShowForm(false)}>
              Cancel
            </button>
          </div>
        </form>
      ) : null}

      {reports.length === 0 && !showForm ? (
        <p className="ic-case-panel__muted">No monthly reports yet for this client.</p>
      ) : (
        <ul className="ic-reports-flow__list">
          {reports.map((r) => {
            const meta = STATUS_LABELS[r.status] || { label: r.status, tone: 'muted' }
            return (
              <li key={r.id} className={`ic-reports-flow__card ic-reports-flow__card--${meta.tone}`}>
                <div className="ic-reports-flow__card-head">
                  <strong>{r.month}</strong>
                  <span className={`ic-reports-flow__pill ic-reports-flow__pill--${meta.tone}`}>{meta.label}</span>
                </div>
                <p className="ic-reports-flow__summary">{r.summary}</p>
                {r.reviewer_comment ? (
                  <p className="ic-reports-flow__reviewer">Admin: {r.reviewer_comment}</p>
                ) : null}
                {r.status === 'DRAFT' || r.status === 'REJECTED' ? (
                  <button type="button" className="ic-btn ic-btn--accent" onClick={() => handleSubmit(r.id)}>
                    Submit for review
                  </button>
                ) : null}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
