import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { formatDisplayDate } from '../../../lib/datetime.js'
import { useProgressReport } from '../hooks/useProgressReport.js'

const STATUS_LABELS = {
  draft: 'DRAFT',
  in_progress: 'DRAFT',
  submitted_for_review: 'UNDER REVIEW',
  returned_for_changes: 'REVISION',
  approved: 'APPROVED',
  locked: 'APPROVED',
}

export function ProgressLandingPage({ caseId, caseCode, childName }) {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const basePath = searchParams.get('portal') === 'admin' ? `/admin/cases/${caseId}` : `/therapist/cases/${caseId}`

  const { summary, loading, error, saving, startReport, refresh } = useProgressReport(caseId)

  async function handleStart() {
    try {
      await startReport()
      navigate(`${basePath}?tab=reports&section=progress&view=builder`)
    } catch {
      /* hook surfaces error */
    }
  }

  if (loading) {
    return <p className="text-sm text-on-surface-variant m-0">Loading progress report…</p>
  }

  const hasReport = summary?.has_report
  const statusLabel = STATUS_LABELS[summary?.status] || summary?.status_label || 'NOT STARTED'
  const pct = summary?.completion_pct ?? 0

  return (
    <>
      <header className="flex flex-wrap justify-between items-center gap-3 mb-6 pb-4 border-b border-outline-variant/30">
        <h2 className="text-lg font-semibold text-on-surface-variant m-0">Progress Report</h2>
        <span className="text-sm text-on-surface-variant">{caseCode}</span>
      </header>

      {error ? <p className="mb-4 px-4 py-3 rounded-lg bg-error-container text-on-error-container text-sm" role="alert">{error}</p> : null}

      <article className="max-w-2xl mx-auto bg-surface-container-lowest p-8 rounded-xl clinical-shadow border border-outline-variant/30">
        <div className="flex items-start justify-between gap-4 mb-6 flex-wrap">
          <div className="flex gap-4 items-start">
            <div className="w-16 h-16 rounded-2xl bg-lush-mint/30 flex items-center justify-center shrink-0">
              <span className="material-symbols-outlined text-3xl text-lush-forest" aria-hidden="true">insights</span>
            </div>
            <div>
              <h2 className="text-2xl font-bold text-lush-forest m-0">{childName || 'Client'}</h2>
              <p className="text-sm text-on-surface-variant mt-1 m-0">
                {hasReport
                  ? `Current review period for ${childName || 'this client'}.`
                  : 'No progress report started for this review period yet.'}
              </p>
            </div>
          </div>
          {hasReport ? (
            <span className="bg-surface-container px-3 py-1 rounded-full border border-outline-variant/50 text-xs font-bold uppercase font-mono">{statusLabel}</span>
          ) : null}
        </div>

        {hasReport ? (
          <div className="space-y-4 mb-6">
            <div>
              <p className="text-xs font-bold uppercase text-outline font-mono m-0 mb-1">Status</p>
              <p className="text-lg font-bold m-0">{summary.status_label}</p>
            </div>
            <div>
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs font-bold uppercase text-outline font-mono">Completion</span>
                <span className="font-bold text-lush-forest">{pct}%</span>
              </div>
              <div className="w-full h-2 bg-surface-container rounded-full overflow-hidden">
                <div className="h-full bg-lush-forest rounded-full" style={{ width: `${pct}%` }} />
              </div>
            </div>
            {summary.period_start && summary.period_end ? (
              <p className="text-sm text-on-surface-variant m-0">
                Review period {formatDisplayDate(summary.period_start)} – {formatDisplayDate(summary.period_end)}
              </p>
            ) : null}
            {summary.submitted_at ? (
              <p className="text-sm text-on-surface-variant m-0">Submitted {formatDisplayDate(summary.submitted_at.slice(0, 10))}</p>
            ) : null}
            {summary.approved_at ? (
              <p className="text-sm text-on-surface-variant m-0">Approved {formatDisplayDate(summary.approved_at.slice(0, 10))}</p>
            ) : null}
          </div>
        ) : (
          <p className="text-sm text-on-surface-variant mb-6 m-0">
            Progress reports roll up monthly reports and goal/strategy evidence since the last cycle — status labels only, no invented percentages.
            {summary?.period_start ? ` Suggested period: ${formatDisplayDate(summary.period_start)} – ${formatDisplayDate(summary.period_end)}.` : ''}
          </p>
        )}

        <div className="flex flex-wrap gap-3">
          {!hasReport || summary.can_edit ? (
            <button
              type="button"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-lush-forest text-white font-bold shadow-lg hover:opacity-90 transition-all min-h-[44px] disabled:opacity-50"
              disabled={saving}
              onClick={hasReport ? () => navigate(`${basePath}?tab=reports&section=progress&view=builder`) : handleStart}
            >
              <span className="material-symbols-outlined" aria-hidden="true">{hasReport ? 'edit_note' : 'add'}</span>
              {saving ? 'Starting…' : hasReport ? 'Continue in builder' : 'Start progress report'}
            </button>
          ) : null}
          {summary?.can_preview ? (
            <Link
              className="inline-flex items-center justify-center px-6 py-3 rounded-xl border-2 border-lush-forest text-lush-forest font-bold hover:bg-lush-mint/10 transition-all min-h-[44px] no-underline"
              to={`${basePath}?tab=reports&section=progress&view=preview`}
            >
              Preview report
            </Link>
          ) : null}
          {summary?.can_start_new ? (
            <button
              type="button"
              className="inline-flex items-center justify-center px-6 py-3 rounded-xl border-2 border-outline-variant text-outline font-bold hover:border-lush-forest hover:text-lush-forest transition-all min-h-[44px]"
              disabled={saving}
              onClick={handleStart}
            >
              Start next cycle
            </button>
          ) : null}
        </div>
      </article>

      <button
        type="button"
        className="mt-4 inline-flex items-center justify-center px-6 py-2 rounded-xl border border-outline-variant text-on-surface-variant text-sm font-semibold min-h-[44px] hover:border-lush-forest hover:text-lush-forest transition-colors"
        onClick={() => refresh('summary')}
      >
        Refresh status
      </button>
    </>
  )
}
