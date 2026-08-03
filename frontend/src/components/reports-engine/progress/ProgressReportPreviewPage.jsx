import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { formatDisplayDate } from '../../../lib/datetime.js'
import { apiFetch } from '../../../lib/apiClient.js'
import { useProgressReport } from '../hooks/useProgressReport.js'
import { ProgressReviewPanel } from './ProgressReviewPanel.jsx'

export function ProgressReportPreviewPage({ caseId, caseCode, childName, variant = 'therapist' }) {
  const basePath = variant === 'admin' ? `/admin/cases/${caseId}` : `/therapist/cases/${caseId}`
  const { preview, loading, error, loadPreview, workspace, loadWorkspace } = useProgressReport(caseId)
  const [reviewMsg, setReviewMsg] = useState('')
  const [reviewBusy, setReviewBusy] = useState(false)
  const [previewMode, setPreviewMode] = useState('clinical')
  const isReviewer = variant === 'admin'

  useEffect(() => {
    loadWorkspace()
  }, [loadWorkspace])

  useEffect(() => {
    if (workspace?.report_id) loadPreview(previewMode)
  }, [workspace?.report_id, loadPreview, previewMode])

  async function approveReport(shareWithParent) {
    if (!workspace?.report_id) return
    setReviewBusy(true)
    setReviewMsg('')
    try {
      await apiFetch(`/api/v1/reports/${workspace.report_id}/approve`, {
        method: 'POST',
        body: JSON.stringify({ share_with_parent: shareWithParent }),
      })
      setReviewMsg(shareWithParent ? 'Approved and shared with parent.' : 'Report approved.')
      await loadWorkspace()
      await loadPreview('clinical')
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
  const goalsSection = sections.find((s) => s.key === 'goals_progress')
  const goals = goalsSection?.structured_data?.goals || []

  function sectionText(key) {
    return sections.find((s) => s.key === key)?.narrative_text?.replace(/<\/?p>|<\/?em>|<\/?ul>|<\/?li>/g, ' ').trim() || ''
  }

  return (
    <>
      <header className="flex flex-wrap justify-between items-center gap-3 mb-6 pb-4 border-b border-outline-variant/30">
        <h2 className="text-lg font-semibold text-on-surface-variant m-0">Progress Report Preview</h2>
        <div className="flex flex-wrap gap-2 items-center">
          <div className="inline-flex rounded-xl border border-outline-variant overflow-hidden">
            <button
              type="button"
              className={`px-4 py-2 text-sm font-semibold min-h-[44px] ${previewMode === 'clinical' ? 'bg-lush-mint/30 text-lush-forest' : ''}`}
              onClick={() => setPreviewMode('clinical')}
            >
              Clinical
            </button>
            <button
              type="button"
              className={`px-4 py-2 text-sm font-semibold min-h-[44px] ${previewMode === 'parent' ? 'bg-lush-mint/30 text-lush-forest' : ''}`}
              onClick={() => setPreviewMode('parent')}
            >
              Parent-safe
            </button>
          </div>
          <button
            type="button"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-outline-variant text-on-surface-variant text-sm font-semibold min-h-[44px]"
            onClick={() => window.print()}
          >
            <span className="material-symbols-outlined" aria-hidden="true">print</span>
            Download PDF
          </button>
        </div>
      </header>

      {error ? <p className="mb-4 px-4 py-3 rounded-lg bg-error-container text-on-error-container text-sm" role="alert">{error}</p> : null}
      <p className="text-sm text-on-surface-variant mb-6 m-0">
        {data.preview_note || 'Clinical preview — parent-safe view excludes therapist reflection and internal notes.'}
      </p>

      <article className="max-w-3xl mx-auto w-full bg-white shadow-lg p-6 md:p-10 border border-outline-variant rounded-xl flex flex-col gap-8">
        <header className="flex flex-col md:flex-row justify-between items-start border-b border-outline pb-6 gap-4">
          <div>
            <h1 className="text-2xl font-bold text-on-surface m-0">Progress Report</h1>
            <p className="text-sm text-on-surface-variant m-0 mt-1">
              {childName || data.child_name} · {caseCode || data.case_code}
            </p>
            {data.period?.start ? (
              <p className="text-sm text-on-surface-variant m-0 mt-1">
                Review period {formatDisplayDate(data.period.start)} – {formatDisplayDate(data.period.end)}
              </p>
            ) : null}
          </div>
          <span className="bg-surface-container px-3 py-1 rounded-full border border-outline-variant/50 text-xs font-bold uppercase font-mono">
            {data.status || workspace?.status || 'DRAFT'}
          </span>
        </header>

        {sectionText('period_overview') ? (
          <section className="flex flex-col gap-2">
            <h2 className="text-lg font-semibold m-0">Period Overview</h2>
            <p className="text-base leading-relaxed m-0">{sectionText('period_overview')}</p>
          </section>
        ) : null}

        {goals.length ? (
          <section className="flex flex-col gap-3">
            <h2 className="text-lg font-semibold m-0">Goal Review</h2>
            <div className="grid sm:grid-cols-2 gap-3">
              {goals.map((g) => (
                <div key={g.goal_id || g.label} className="border border-outline-variant/40 rounded-xl p-4">
                  <p className="text-sm font-bold m-0">{g.label}</p>
                  <p className="text-xs text-on-surface-variant m-0 mt-1">{g.status}</p>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        {sections
          .filter((s) => s.narrative_text && !['period_overview', 'goals_progress'].includes(s.key))
          .map((sec) => (
            <section key={sec.key} className="flex flex-col gap-2">
              <h2 className="text-lg font-semibold m-0">{sec.label || sec.key}</h2>
              <p className="text-base leading-relaxed m-0" dangerouslySetInnerHTML={{ __html: sec.narrative_text }} />
            </section>
          ))}
      </article>

      <div className="flex flex-wrap gap-3 mt-8 flex-col sm:flex-row">
        {isReviewer ? (
          <ProgressReviewPanel
            reportId={workspace?.report_id}
            canReview={workspace?.status === 'submitted_for_review'}
            onReturned={() => {
              loadWorkspace()
              loadPreview(previewMode)
            }}
          />
        ) : null}
        {isReviewer && workspace?.status === 'submitted_for_review' ? (
          <>
            <button
              type="button"
              className="inline-flex items-center justify-center px-6 py-3 rounded-xl bg-lush-forest text-white font-bold min-h-[44px] disabled:opacity-50"
              disabled={reviewBusy}
              onClick={() => approveReport(false)}
            >
              Approve (internal only)
            </button>
            <button
              type="button"
              className="inline-flex items-center justify-center px-6 py-3 rounded-xl border-2 border-lush-forest text-lush-forest font-bold min-h-[44px] disabled:opacity-50"
              disabled={reviewBusy}
              onClick={() => approveReport(true)}
            >
              Approve &amp; share with parent
            </button>
          </>
        ) : null}
        {reviewMsg ? <p className="text-sm text-on-surface-variant m-0 self-center">{reviewMsg}</p> : null}
        <Link
          className="inline-flex items-center justify-center px-6 py-3 rounded-xl border-2 border-lush-forest text-lush-forest font-bold hover:bg-lush-mint/10 transition-all min-h-[44px] no-underline"
          to={`${basePath}?tab=reports&section=progress&view=builder`}
        >
          Back to builder
        </Link>
        <Link
          className="inline-flex items-center justify-center px-6 py-3 rounded-xl border border-outline-variant text-on-surface-variant font-semibold min-h-[44px] no-underline hover:border-lush-forest hover:text-lush-forest"
          to={`${basePath}?tab=reports&section=progress`}
        >
          Back to status
        </Link>
      </div>
    </>
  )
}
