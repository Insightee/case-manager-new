import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { clinicalReportSectionPath } from '../../../lib/clinicalReportPaths.js'
import { useIepReport } from '../hooks/useIepReport.js'
import { ClinicalReportNotice } from '../shared/ClinicalReportNotice.jsx'
import { StitchIcon, StitchWorkspaceSubhead } from '../observation/stitch/ObservationStitchBlocks.jsx'

const STATUS_LABELS = {
  draft: 'DRAFT',
  in_progress: 'DRAFT',
  submitted_for_review: 'UNDER REVIEW',
  returned_for_changes: 'REVISION',
  approved: 'ACTIVE PLAN',
  locked: 'APPROVED',
}

export function IepLandingPage({ caseId, caseCode, childName, variant = 'therapist' }) {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const portal = searchParams.get('portal')
  const sectionPath = (view) => clinicalReportSectionPath({ caseId, section: 'iep', view, variant, portal })

  const { summary, loading, error, saving, startReport, generateFromObservation, refresh } = useIepReport(caseId)

  async function handleStart() {
    try {
      const ws = await startReport()
      if (summary?.observation_approved) {
        await generateFromObservation()
      }
      navigate(sectionPath('builder'))
    } catch {
      /* hook surfaces error */
    }
  }

  async function handleImport() {
    try {
      if (!summary?.has_report) await startReport()
      await generateFromObservation()
      navigate(sectionPath('builder'))
    } catch {
      /* hook surfaces error */
    }
  }

  if (loading) return <p className="text-sm text-slate-600 m-0">Loading IEP plan…</p>

  const hasReport = summary?.has_report
  const statusLabel = STATUS_LABELS[summary?.status] || summary?.status_label || 'NOT STARTED'

  return (
    <>
      <StitchWorkspaceSubhead caseCode={caseCode} saving={saving} title="IEP Support Plan" />
      {error ? <ClinicalReportNotice className="mb-4">{error}</ClinicalReportNotice> : null}

      <article className="max-w-2xl mx-auto bg-surface-container-lowest p-8 rounded-xl clinical-shadow border border-outline-variant/30">
        <div className="flex items-start justify-between gap-4 mb-6 flex-wrap">
          <div className="flex gap-4 items-start">
            <div className="w-16 h-16 rounded-2xl bg-lush-mint/30 flex items-center justify-center shrink-0">
              <StitchIcon name="assignment" filled className="text-3xl text-lush-forest" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-lush-forest m-0">
                {hasReport ? 'IEP in progress' : 'No IEP Report active for this case'}
              </h2>
              <p className="text-sm text-on-surface-variant mt-1 m-0">
                {hasReport
                  ? `${childName || 'Client'} — ${summary.status_label}`
                  : `Ready to establish a structured plan for ${childName || 'this client'}?`}
              </p>
            </div>
          </div>
          {hasReport ? (
            <span className="bg-surface-container px-3 py-1 rounded-full border border-outline-variant/50 text-xs font-bold uppercase font-mono">
              {statusLabel}
            </span>
          ) : null}
        </div>

        {!hasReport ? (
          <p className="text-sm text-on-surface-variant mb-6 m-0">
            Start from an approved observation report to pre-fill strengths, domains, and goal candidates — or build manually.
          </p>
        ) : (
          <div className="grid grid-cols-2 gap-4 mb-6 text-sm">
            <div>
              <p className="text-xs font-bold uppercase text-outline font-mono m-0">Observation</p>
              <p className="m-0">{summary.observation_approved ? 'Approved' : summary.observation_status || 'Not ready'}</p>
            </div>
            <div>
              <p className="text-xs font-bold uppercase text-outline font-mono m-0">Goal candidates</p>
              <p className="m-0">{summary.available_goal_candidates ?? 0}</p>
            </div>
            {summary.pending_changes_count > 0 ? (
              <div className="col-span-2 text-amber-800 font-semibold">
                {summary.pending_changes_count} change(s) awaiting CM review
              </div>
            ) : null}
          </div>
        )}

        <div className="flex flex-wrap gap-3">
          {!hasReport ? (
            <button
              type="button"
              className="inline-flex items-center justify-center min-h-[44px] px-6 py-2 rounded-xl bg-lush-forest text-white font-bold text-sm"
              disabled={saving}
              onClick={handleStart}
            >
              Start Building IEP
            </button>
          ) : null}
          {summary?.observation_approved ? (
            <button
              type="button"
              className="inline-flex items-center justify-center min-h-[44px] px-6 py-2 rounded-xl border border-outline-variant/50 bg-surface-container font-semibold text-sm"
              disabled={saving}
              onClick={handleImport}
            >
              Import from Observation
            </button>
          ) : null}
          {hasReport && summary?.can_edit ? (
            <Link
              to={sectionPath('builder')}
              className="inline-flex items-center justify-center min-h-[44px] px-6 py-2 rounded-xl border border-outline-variant/50 bg-surface-container font-semibold text-sm no-underline text-inherit"
            >
              Continue Draft
            </Link>
          ) : null}
          {hasReport && summary?.has_active_approved_iep ? (
            <Link
              to={sectionPath('preview')}
              className="inline-flex items-center justify-center min-h-[44px] px-6 py-2 rounded-xl border border-outline-variant/50 font-semibold text-sm no-underline text-inherit"
            >
              Preview Approved IEP
            </Link>
          ) : null}
          <button type="button" className="text-sm text-on-surface-variant underline" onClick={() => refresh('summary')}>
            Refresh status
          </button>
        </div>
      </article>
    </>
  )
}
