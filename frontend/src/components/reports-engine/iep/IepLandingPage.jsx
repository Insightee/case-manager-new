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

  const { summary, loading, error, saving, startReport, generateFromObservation, refresh, shareWithParent, submitReport, downloadPdf } = useIepReport(caseId)

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
  const isParent = variant === 'parent'
  const isAdmin = variant === 'admin'
  const canStart = !isParent && !hasReport
  const canImport = !isParent && summary?.observation_approved
  const canContinue = !isParent && hasReport && summary?.can_edit
  const canSubmit = !isParent && Boolean(summary?.can_submit)
  const canPreview = hasReport && (isParent ? summary?.can_preview : summary?.has_active_approved_iep || summary?.can_preview)
  const canShare = isAdmin && summary?.can_share_with_parent
  const canDownload = hasReport && (isParent ? summary?.can_preview : true)
  const currentPeriod = new Date().toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
  const iepVersions = summary?.iep_versions || []

  async function handleShare() {
    try {
      await shareWithParent()
    } catch {
      /* hook surfaces error */
    }
  }

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
                {hasReport
                  ? isParent
                    ? `IEP support plan${summary.period_label ? ` · ${summary.period_label}` : ''}`
                    : `IEP${summary.period_label ? ` · ${summary.period_label}` : ''}`
                  : isParent
                    ? 'No IEP has been shared yet'
                    : 'No IEP Report active for this case'}
              </h2>
              <p className="text-sm text-on-surface-variant mt-1 m-0">
                {hasReport
                  ? `${childName || 'Client'} — ${summary.status_label}`
                  : isParent
                    ? `When the care team shares a plan for ${childName || 'this client'}, it will appear here.`
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
            {isParent
              ? 'The family view opens after the team shares this plan.'
              : 'Start from an approved observation report to pre-fill strengths, domains, and goal candidates — or build manually.'}
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
            {!isParent && hasReport && !summary.shared_with_parent ? (
              <div className="col-span-2 text-sm text-on-surface-variant">
                The family cannot see this plan until a case manager shares it.
              </div>
            ) : null}
            {summary.shared_with_parent ? (
              <div className="col-span-2 text-sm font-semibold text-lush-forest">Shared with family</div>
            ) : null}
          </div>
        )}

        {iepVersions.length > 0 ? (
          <div className="mb-6">
            <p className="text-xs font-bold uppercase text-outline font-mono m-0 mb-2">IEP history</p>
            <ul className="space-y-2 m-0 p-0 list-none text-sm">
              {iepVersions.map((ver) => (
                <li key={ver.report_id} className="flex flex-wrap gap-2 items-center">
                  <span className="font-semibold">{ver.period_label}</span>
                  <span className="text-on-surface-variant">{ver.status?.replace(/_/g, ' ')}</span>
                  {ver.is_active ? <span className="text-xs uppercase text-lush-forest font-bold">Current</span> : null}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="flex flex-wrap gap-3">
          {canStart ? (
            <button
              type="button"
              className="cr-btn cr-btn--primary inline-flex items-center justify-center font-bold text-sm"
              style={{ backgroundColor: '#0b1c16', color: '#fff' }}
              disabled={saving}
              onClick={handleStart}
            >
              Start IEP — {currentPeriod}
            </button>
          ) : null}
          {summary?.can_start_new && !canStart ? (
            <button
              type="button"
              className="cr-btn cr-btn--primary inline-flex items-center justify-center font-bold text-sm"
              style={{ backgroundColor: '#0b1c16', color: '#fff' }}
              disabled={saving}
              onClick={handleStart}
            >
              Start next IEP — {currentPeriod}
            </button>
          ) : null}
          {canImport ? (
            <button
              type="button"
              className="inline-flex items-center justify-center min-h-[44px] px-6 py-2 rounded-xl border border-outline-variant/50 bg-surface-container font-semibold text-sm"
              disabled={saving}
              onClick={handleImport}
            >
              Import from Observation
            </button>
          ) : null}
          {canContinue ? (
            <Link
              to={sectionPath('builder')}
              className="inline-flex items-center justify-center min-h-[44px] px-6 py-2 rounded-xl border border-outline-variant/50 bg-surface-container font-semibold text-sm no-underline text-inherit"
            >
              Continue Draft
            </Link>
          ) : null}
          {canSubmit ? (
            <button
              type="button"
              className="cr-btn cr-btn--primary inline-flex items-center justify-center font-bold text-sm"
              style={{ backgroundColor: '#0b1c16', color: '#fff' }}
              disabled={saving}
              onClick={() => submitReport()}
            >
              Submit for review
            </button>
          ) : null}
          {canShare ? (
            <button
              type="button"
              className="cr-btn cr-btn--primary inline-flex items-center justify-center font-bold text-sm"
              style={{ backgroundColor: '#0b1c16', color: '#fff' }}
              disabled={saving}
              onClick={handleShare}
            >
              Share with family
            </button>
          ) : null}
          {canDownload ? (
            <button
              type="button"
              className="inline-flex items-center justify-center min-h-[44px] px-6 py-2 rounded-xl border border-outline-variant/50 font-semibold text-sm"
              disabled={saving}
              onClick={() => downloadPdf(`IEP_${caseCode || caseId}.pdf`)}
            >
              Download PDF
            </button>
          ) : null}
          {canPreview ? (
            <Link
              to={sectionPath('preview')}
              className="inline-flex items-center justify-center min-h-[44px] px-6 py-2 rounded-xl border border-outline-variant/50 font-semibold text-sm no-underline text-inherit"
            >
              {isParent ? 'View support plan' : 'Preview IEP'}
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
