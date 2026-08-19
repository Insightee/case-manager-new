import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { formatDisplayDate } from '../../../lib/datetime.js'
import { clinicalReportNavBase, clinicalReportSectionPath } from '../../../lib/clinicalReportPaths.js'
import { useObservationReport } from '../hooks/useObservationReport.js'
import { StitchIcon, StitchWorkspaceSubhead } from './stitch/ObservationStitchBlocks.jsx'

const STATUS_LABELS = {
  draft: 'DRAFT',
  in_progress: 'DRAFT',
  submitted_for_review: 'UNDER REVIEW',
  returned_for_changes: 'REVISION',
  approved: 'APPROVED',
  locked: 'APPROVED',
}

export function ObservationLandingPage({ caseId, caseCode, childName, variant = 'therapist' }) {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const portal = searchParams.get('portal')
  const caseNavBase = clinicalReportNavBase({ caseId, variant, portal })
  const sectionPath = (view) => clinicalReportSectionPath({ caseId, section: 'observation', view, variant, portal })

  const { summary, loading, error, saving, startReport, refresh } = useObservationReport(caseId)

  async function handleStart() {
    try {
      await startReport()
      navigate(sectionPath('builder'))
    } catch {
      /* hook surfaces error */
    }
  }

  if (loading) {
    return <p className="text-sm text-on-surface-variant m-0">Loading observation report…</p>
  }

  const hasReport = summary?.has_report
  const statusLabel = STATUS_LABELS[summary?.status] || summary?.status_label || 'NOT STARTED'
  const pct = summary?.completion_pct ?? 0

  return (
    <>
      <StitchWorkspaceSubhead caseCode={caseCode} saving={saving} title="Observation Report" />

      {error ? <p className="mb-4 px-4 py-3 rounded-lg bg-error-container text-on-error-container text-sm" role="alert">{error}</p> : null}
      {summary?.reviewer_comment ? (
        <p className="mb-4 px-4 py-3 rounded-lg bg-amber-50 border border-amber-200 text-sm"><strong>Case manager note:</strong> {summary.reviewer_comment}</p>
      ) : null}

      <article className="max-w-2xl mx-auto bg-surface-container-lowest p-8 rounded-xl clinical-shadow border border-outline-variant/30">
        <div className="flex items-start justify-between gap-4 mb-6 flex-wrap">
          <div className="flex gap-4 items-start">
            <div className="w-16 h-16 rounded-2xl bg-lush-mint/30 flex items-center justify-center shrink-0">
              <StitchIcon name="description" filled className="text-3xl text-lush-forest" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-lush-forest m-0">{childName || 'Client'}</h2>
              <p className="text-sm text-on-surface-variant mt-1 m-0">
                {hasReport
                  ? `Current observation cycle for ${childName || 'this client'}.`
                  : 'No observation report started yet.'}
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
            {summary.due_at ? (
              <p className={`text-sm m-0${summary.is_overdue ? ' text-amber-700 font-semibold' : ' text-on-surface-variant'}`}>
                Due {formatDisplayDate(summary.due_at.slice(0, 10))}
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
            The builder walks you through strengths, environments, emerging goals, strategies, and stakeholder inputs — matching the approved clinical workspace layout.
          </p>
        )}

        <div className="flex flex-wrap gap-3">
          {!hasReport || summary.can_edit ? (
            <button
              type="button"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-lush-forest text-white font-bold shadow-lg hover:opacity-90 transition-all min-h-[44px] disabled:opacity-50"
              disabled={saving}
              onClick={hasReport ? () => navigate(sectionPath('builder')) : handleStart}
            >
              <StitchIcon name={hasReport ? 'edit_note' : 'add'} />
              {saving ? 'Starting…' : hasReport ? 'Continue in builder' : 'Start new observation report'}
            </button>
          ) : null}
          {summary?.can_preview ? (
            <Link
              className="inline-flex items-center justify-center px-6 py-3 rounded-xl border-2 border-lush-forest text-lush-forest font-bold hover:bg-lush-mint/10 transition-all min-h-[44px] no-underline"
              to={sectionPath('preview')}
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
              Start new cycle
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
