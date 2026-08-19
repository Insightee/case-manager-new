import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { formatDisplayDate } from '../../../lib/datetime.js'
import { clinicalReportSectionPath } from '../../../lib/clinicalReportPaths.js'
import { apiFetch } from '../../../lib/apiClient.js'
import { useObservationReport } from '../hooks/useObservationReport.js'
import { StitchIcon, StitchWorkspaceSubhead } from './stitch/ObservationStitchBlocks.jsx'

export function ObservationPreviewPage({ caseId, caseCode, childName, variant = 'therapist' }) {
  const sectionPath = (view) => clinicalReportSectionPath({ caseId, section: 'observation', view, variant })
  const { preview, loading, error, loadPreview, summary, insights, workspace, loadWorkspace } = useObservationReport(caseId)
  const [reviewMsg, setReviewMsg] = useState('')
  const [reviewBusy, setReviewBusy] = useState(false)
  const isReviewer = variant === 'admin'

  useEffect(() => {
    loadPreview()
    loadWorkspace()
  }, [loadPreview, loadWorkspace])

  async function approveReport() {
    if (!workspace?.report_id) return
    setReviewBusy(true)
    setReviewMsg('')
    try {
      await apiFetch(`/api/v1/reports/${workspace.report_id}/approve`, {
        method: 'POST',
        body: JSON.stringify({ share_with_parent: false }),
      })
      setReviewMsg('Report approved.')
      await loadPreview()
      await loadWorkspace()
    } catch (err) {
      setReviewMsg(err.message || 'Could not approve report')
    } finally {
      setReviewBusy(false)
    }
  }

  if (loading && !preview) {
    return <p className="text-sm text-on-surface-variant m-0">Loading preview…</p>
  }

  const data = preview || {}
  const sections = data.sections || []
  const patterns = insights?.patterns || data.insights?.patterns || []

  function sectionText(key) {
    return sections.find((s) => s.key === key)?.narrative_text || ''
  }

  function sectionData(key) {
    return sections.find((s) => s.key === key)?.structured_data || {}
  }

  const strengths = sectionData('strengths_interests')
  const support = sectionData('support_needs')

  return (
    <>
      <div className="flex justify-end mb-4">
        <button type="button" className="bg-secondary-fixed text-on-secondary-fixed flex items-center gap-2 px-6 py-3 rounded-xl shadow-lg hover:bg-secondary transition-all font-semibold min-h-[44px]" onClick={() => window.print()}>
          <StitchIcon name="print" />
          Download PDF Report
        </button>
      </div>

      <StitchWorkspaceSubhead caseCode={caseCode} saving={false} title="Observation Report Preview" />

      {error ? <p className="mb-4 px-4 py-3 rounded-lg bg-error-container text-on-error-container text-sm" role="alert">{error}</p> : null}
      <p className="text-sm text-on-surface-variant mb-6 m-0">
        {data.preview_note || 'Parent-safe preview — internal notes excluded.'}
      </p>

      <article className="max-w-5xl mx-auto w-full bg-white shadow-2xl p-8 md:p-16 border border-outline-variant flex flex-col gap-12">
        <header className="flex flex-col md:flex-row justify-between items-start border-b border-outline pb-10 gap-8">
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 forest-gradient rounded-lg flex items-center justify-center">
                <StitchIcon name="analytics" filled className="text-white" />
              </div>
              <span className="text-xs font-mono uppercase text-outline tracking-widest">Clinical Documentation</span>
            </div>
            <h1 className="text-4xl font-bold text-on-surface m-0">Observation Report</h1>
            <div className="flex flex-col gap-1">
              <p className="text-base text-on-surface-variant m-0">Case ID: <span className="font-bold text-on-surface">{caseCode || data.case_code}</span></p>
              {data.approved_at ? (
                <p className="text-base text-on-surface-variant m-0">Date of Finalization: <span className="font-bold text-on-surface">{formatDisplayDate(data.approved_at.slice(0, 10))}</span></p>
              ) : null}
            </div>
          </div>
          <div className="text-right flex flex-col gap-4 md:items-end">
            <div className="bg-surface-container-high px-4 py-3 rounded-xl border border-outline-variant max-w-xs text-left md:text-right">
              <p className="text-xs text-on-surface-variant font-mono m-0">Client</p>
              <p className="text-2xl font-semibold text-on-secondary-fixed-variant m-0">{childName || data.child_name}</p>
            </div>
            <div className="flex items-center gap-2 md:justify-end text-on-surface-variant">
              <StitchIcon name="verified_user" className="text-sm" />
              <span className="text-xs font-mono">InsighteCase Verified Report</span>
            </div>
          </div>
        </header>

        <section className="grid grid-cols-1 md:grid-cols-3 gap-6 bg-surface-container-lowest p-6 rounded-2xl border border-outline-variant">
          <div className="flex flex-col gap-2">
            <span className="text-xs font-mono uppercase text-outline">Client name</span>
            <p className="text-2xl font-semibold text-on-surface m-0">{childName || data.child_name}</p>
          </div>
          <div className="flex flex-col gap-2">
            <span className="text-xs font-mono uppercase text-outline">Case</span>
            <p className="text-2xl font-semibold text-on-surface m-0">{caseCode || data.case_code}</p>
          </div>
          <div className="flex flex-col gap-2">
            <span className="text-xs font-mono uppercase text-outline">Status</span>
            <p className="text-2xl font-semibold text-on-surface m-0">{summary?.status_label || data.status || 'Draft'}</p>
          </div>
        </section>

        {sectionText('referral_background') || sectionText('clinical_summary') ? (
          <section className="flex flex-col gap-4">
            <h2 className="text-2xl font-semibold text-on-surface flex items-center gap-3 m-0">
              <StitchIcon name="history_edu" className="text-secondary" />
              Clinical Summary
            </h2>
            <div className="bg-white border-l-4 border-secondary p-6">
              <p className="text-lg text-on-surface leading-relaxed m-0">
                {sectionText('clinical_summary') || sectionText('referral_background')}
              </p>
            </div>
          </section>
        ) : null}

        {patterns.length ? (
          <section className="flex flex-col gap-4">
            <h2 className="text-2xl font-semibold text-on-surface flex items-center gap-3 m-0">
              <StitchIcon name="insights" className="text-secondary" />
              Behavioral Insights &amp; Trends
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {patterns.map((p, idx) => (
                <div key={p.key} className={`p-6 rounded-2xl border border-outline-variant flex flex-col gap-4${idx === 1 ? ' bg-secondary-fixed' : ' bg-surface-container-low'}`}>
                  <div className="flex justify-between items-start">
                    <StitchIcon name={idx === 0 ? 'warning' : idx === 1 ? 'verified' : 'psychology_alt'} />
                  </div>
                  <div>
                    <span className="font-bold text-on-surface">{p.label}</span>
                    <p className="text-xs text-on-surface-variant font-mono mt-1 m-0">{p.value}</p>
                  </div>
                  <div className="w-full bg-surface-container-high h-2 rounded-full overflow-hidden">
                    <div className={`h-full rounded-full${idx === 1 ? ' bg-on-tertiary-container' : idx === 0 ? ' bg-error' : ' bg-secondary'}`} style={{ width: `${60 + idx * 15}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        {(strengths.strengths?.length || support.support_needs?.length) ? (
          <section className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {strengths.strengths?.length ? (
              <div>
                <h2 className="text-xl font-semibold mb-3 m-0">Strengths</h2>
                <div className="flex flex-wrap gap-2">
                  {strengths.strengths.map((s) => (
                    <span key={s} className="px-3 py-1.5 rounded-lg bg-lush-mint/40 text-lush-forest text-sm font-bold">{s}</span>
                  ))}
                </div>
              </div>
            ) : null}
            {support.support_needs?.length ? (
              <div>
                <h2 className="text-xl font-semibold mb-3 m-0">Support Needs</h2>
                <div className="flex flex-wrap gap-2">
                  {support.support_needs.map((s) => (
                    <span key={s} className="px-3 py-1.5 rounded-lg bg-surface-container text-on-surface text-sm font-bold">{s}</span>
                  ))}
                </div>
              </div>
            ) : null}
          </section>
        ) : null}

        {sections.filter((s) => s.narrative_text && !['referral_background', 'clinical_summary', 'internal_notes'].includes(s.key)).map((sec) => (
          <section key={sec.key} className="flex flex-col gap-3">
            <h2 className="text-2xl font-semibold m-0">{sec.label || sec.key}</h2>
            <p className="text-base leading-relaxed m-0">{sec.narrative_text}</p>
          </section>
        ))}
      </article>

      <div className="flex flex-wrap gap-3 mt-8">
        {isReviewer && workspace?.status === 'submitted' ? (
          <button
            type="button"
            className="inline-flex items-center justify-center px-6 py-3 rounded-xl bg-lush-forest text-white font-bold min-h-[44px] disabled:opacity-50"
            disabled={reviewBusy}
            onClick={approveReport}
          >
            Approve observation report
          </button>
        ) : null}
        {reviewMsg ? <p className="text-sm text-on-surface-variant m-0 self-center">{reviewMsg}</p> : null}
        <Link className="inline-flex items-center justify-center px-6 py-3 rounded-xl border-2 border-lush-forest text-lush-forest font-bold hover:bg-lush-mint/10 transition-all min-h-[44px] no-underline" to={sectionPath('builder')}>
          {isReviewer ? 'Open full report workspace' : 'Back to builder'}
        </Link>
        <Link className="inline-flex items-center justify-center px-6 py-3 rounded-xl border border-outline-variant text-on-surface-variant font-semibold min-h-[44px] no-underline hover:border-lush-forest hover:text-lush-forest" to={sectionPath('landing')}>
          Back to status
        </Link>
      </div>
    </>
  )
}
