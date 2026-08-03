import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { formatDisplayDate } from '../../../lib/datetime.js'
import { useProgressReport } from '../hooks/useProgressReport.js'
import { ProgressEvidenceDrawer } from './ProgressEvidenceDrawer.jsx'

function sectionByKey(sections, key) {
  return sections?.find((s) => s.key === key) || {}
}

const STATUS_TONE = {
  Consistent: 'bg-lush-mint/40 text-lush-forest',
  Building: 'bg-secondary-fixed text-on-secondary-fixed-variant',
  Emerging: 'bg-surface-container text-on-surface-variant',
  'Needs adapting': 'bg-amber-50 text-amber-700 border border-amber-200',
  'Not enough evidence': 'bg-surface-container text-outline',
}

const STATUS_OPTIONS = ['Emerging', 'Building', 'Consistent', 'Needs adapting', 'Not enough evidence']

function GoalStatusPill({ status }) {
  const tone = STATUS_TONE[status] || 'bg-surface-container text-on-surface-variant'
  return <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold ${tone}`}>{status}</span>
}

function effectiveStatus(goal) {
  return goal.final_status || (goal.status_confirmed ? goal.suggested_status : null) || goal.suggested_status || goal.status
}

function GoalReviewCard({ goal, readOnly, onConfirm, onOverride, onShowEvidence }) {
  const displayStatus = effectiveStatus(goal)
  return (
    <div className="border border-outline-variant/40 rounded-xl p-4 bg-white flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <h4 className="text-sm font-bold m-0">{goal.label || 'Goal'}</h4>
        <GoalStatusPill status={displayStatus} />
      </div>
      <p className="text-xs text-on-surface-variant m-0">
        Suggested: {goal.suggested_status || '—'} · {goal.sessions_addressed || 0} session(s) in period
      </p>
      {goal.strategies_used?.length ? (
        <div className="flex flex-wrap gap-1.5">
          {goal.strategies_used.map((s) => (
            <span key={s} className="px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant text-xs">{s}</span>
          ))}
        </div>
      ) : null}
      {!readOnly ? (
        <div className="flex flex-col gap-2 pt-1 border-t border-outline-variant/30">
          <label className="text-xs font-bold uppercase text-outline">Final status</label>
          <select
            className="border border-outline-variant rounded-lg px-3 py-2 text-sm min-h-[44px]"
            value={goal.final_status || ''}
            onChange={(e) => onOverride(goal.goal_id, { final_status: e.target.value || null, status_confirmed: false })}
          >
            <option value="">Use suggested ({goal.suggested_status})</option>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <button
            type="button"
            className="text-sm font-semibold text-lush-forest min-h-[44px] text-left"
            onClick={() => onConfirm(goal.goal_id)}
          >
            {goal.status_confirmed && !goal.final_status ? '✓ Suggested status confirmed' : 'Confirm suggested status'}
          </button>
        </div>
      ) : null}
      <button
        type="button"
        className="text-xs font-bold text-lush-forest min-h-[44px] text-left"
        onClick={() => onShowEvidence(goal)}
      >
        View evidence
      </button>
    </div>
  )
}

function SectionTextarea({ sectionKey, sections, readOnly, minHeight = 96, onBlur }) {
  const sec = sectionByKey(sections, sectionKey)
  return (
    <div>
      <label className="text-xs font-bold uppercase text-outline mb-2 block font-mono" htmlFor={`progress-${sectionKey}`}>
        {sec.label || sectionKey}
      </label>
      {sec.prompt ? <p className="text-xs text-on-surface-variant mt-0 mb-2">{sec.prompt}</p> : null}
      <textarea
        id={`progress-${sectionKey}`}
        className="w-full border border-outline-variant rounded-xl p-4 text-sm focus:ring-lush-mint resize-y"
        style={{ minHeight }}
        disabled={readOnly}
        defaultValue={(sec.narrative_text || '').replace(/<\/?p>|<\/?em>/g, '').trim()}
        onBlur={(e) => onBlur(sectionKey, e.target.value)}
      />
    </div>
  )
}

export function ProgressReportBuilderPage({ caseId, caseCode, childName, variant = 'therapist' }) {
  const navigate = useNavigate()
  const basePath = variant === 'admin' ? `/admin/cases/${caseId}` : `/therapist/cases/${caseId}`

  const {
    workspace,
    loading,
    error,
    saving,
    refreshPreview,
    loadWorkspace,
    populateFromEvidence,
    refreshEvidence,
    patchGoal,
    fetchGoalEvidence,
    patchSection,
    submitReport,
  } = useProgressReport(caseId)

  const [evidenceOpen, setEvidenceOpen] = useState(false)
  const [evidenceGoal, setEvidenceGoal] = useState(null)
  const [evidenceData, setEvidenceData] = useState(null)
  const [evidenceLoading, setEvidenceLoading] = useState(false)

  useEffect(() => {
    loadWorkspace()
  }, [loadWorkspace])

  const sections = workspace?.sections || []
  const readOnly = !workspace?.can_edit
  const goalsSection = sectionByKey(sections, 'goals_progress')
  const goals = goalsSection.structured_data?.goals || []
  const hasPopulated = goals.length > 0

  function saveNarrative(key, value) {
    const html = value.trim() ? `<p>${value.trim()}</p>` : ''
    patchSection(key, { narrative_text: html })
  }

  async function showEvidence(goal) {
    setEvidenceGoal(goal)
    setEvidenceOpen(true)
    setEvidenceLoading(true)
    try {
      const data = await fetchGoalEvidence(goal.goal_id)
      setEvidenceData(data)
    } catch {
      setEvidenceData(goal.evidence_summary ? { evidence_summary: goal.evidence_summary } : null)
    } finally {
      setEvidenceLoading(false)
    }
  }

  if (loading && !workspace) {
    return <p className="text-sm text-on-surface-variant m-0">Loading builder…</p>
  }

  return (
    <>
      <header className="flex flex-wrap justify-between items-center gap-3 mb-6 pb-4 border-b border-outline-variant/30">
        <h2 className="text-lg font-semibold text-on-surface-variant m-0">Progress Report — {childName || caseCode}</h2>
        <span className="inline-flex items-center gap-2 bg-surface-container px-4 py-1.5 rounded-full border border-outline-variant/50 text-xs font-semibold font-mono">
          <span className="live-sync-dot" aria-hidden="true" />
          {saving ? 'Saving…' : `${workspace?.completion_pct ?? 0}% complete`}
        </span>
      </header>

      {error ? <p className="mb-4 px-4 py-3 rounded-lg bg-error-container text-on-error-container text-sm" role="alert">{error}</p> : null}
      {workspace?.period ? (
        <p className="text-sm text-on-surface-variant mb-6 m-0">
          Review period {formatDisplayDate(workspace.period.start)} – {formatDisplayDate(workspace.period.end)}
        </p>
      ) : null}

      <div className="flex flex-col gap-6 pb-24 sm:pb-8">
        {!readOnly ? (
          <div className="bg-lush-mint/10 border border-lush-mint/40 rounded-xl p-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm m-0">
              {hasPopulated
                ? 'Refresh pulls new approved evidence — therapist-edited sections are preserved.'
                : 'Compile approved monthly reports and goal evidence for this period into a draft.'}
            </p>
            <button
              type="button"
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-lush-forest text-white font-bold min-h-[44px] disabled:opacity-50 shrink-0"
              disabled={saving}
              onClick={hasPopulated ? refreshEvidence : populateFromEvidence}
            >
              <span className="material-symbols-outlined" aria-hidden="true">auto_awesome</span>
              {saving ? 'Working…' : hasPopulated ? 'Refresh evidence' : 'Compile from evidence'}
            </button>
          </div>
        ) : null}

        {refreshPreview?.length ? (
          <p className="text-xs text-on-surface-variant m-0">
            Refresh complete — {refreshPreview.filter((r) => r.skipped_reason).length} section(s) skipped (therapist edits preserved).
          </p>
        ) : null}

        <SectionTextarea sectionKey="period_overview" sections={sections} readOnly={readOnly} onBlur={saveNarrative} />

        <section className="bg-surface-container-lowest p-5 sm:p-6 rounded-xl clinical-shadow border border-outline-variant/30">
          <h3 className="text-lg font-bold text-lush-forest mb-1 m-0">Goal Review</h3>
          <p className="text-xs text-on-surface-variant mt-1 mb-4">
            Confirm or override each suggested status before submit — never a fabricated percentage.
          </p>
          {goals.length ? (
            <div className="grid sm:grid-cols-2 gap-3 mb-4">
              {goals.map((g) => (
                <GoalReviewCard
                  key={g.goal_id || g.label}
                  goal={g}
                  readOnly={readOnly}
                  onConfirm={(id) => patchGoal(id, { status_confirmed: true })}
                  onOverride={(id, patch) => patchGoal(id, patch)}
                  onShowEvidence={showEvidence}
                />
              ))}
            </div>
          ) : (
            <p className="text-sm text-on-surface-variant mb-4">
              No goal review yet — compile from evidence to pull in IEP goals and session signals.
            </p>
          )}
          <SectionTextarea sectionKey="goals_progress" sections={sections} readOnly={readOnly} minHeight={80} onBlur={saveNarrative} />
        </section>

        <SectionTextarea sectionKey="strengths_and_development" sections={sections} readOnly={readOnly} onBlur={saveNarrative} />
        <SectionTextarea sectionKey="strategies_and_supports" sections={sections} readOnly={readOnly} onBlur={saveNarrative} />
        <SectionTextarea sectionKey="challenges_and_support_needs" sections={sections} readOnly={readOnly} onBlur={saveNarrative} />
        <SectionTextarea sectionKey="family_school_input" sections={sections} readOnly={readOnly} onBlur={saveNarrative} />
        <SectionTextarea sectionKey="next_period_plan" sections={sections} readOnly={readOnly} onBlur={saveNarrative} />
        <SectionTextarea sectionKey="therapist_reflection" sections={sections} readOnly={readOnly} minHeight={72} onBlur={saveNarrative} />
        <SectionTextarea sectionKey="parent_summary" sections={sections} readOnly={readOnly} onBlur={saveNarrative} />
      </div>

      <ProgressEvidenceDrawer
        open={evidenceOpen}
        onClose={() => setEvidenceOpen(false)}
        goalLabel={evidenceGoal?.label}
        evidence={evidenceData}
        loading={evidenceLoading}
      />

      <footer className="flex flex-wrap gap-3 justify-end mt-8 sticky-footer">
        <button
          type="button"
          className="inline-flex items-center justify-center px-5 py-3 rounded-xl border border-outline-variant text-on-surface-variant font-semibold min-h-[44px]"
          onClick={() => navigate(`${basePath}?tab=reports&section=progress`)}
        >
          ← Back to status
        </button>
        <button
          type="button"
          className="inline-flex items-center justify-center px-5 py-3 rounded-xl border-2 border-lush-forest text-lush-forest font-bold min-h-[44px]"
          onClick={() => navigate(`${basePath}?tab=reports&section=progress&view=preview`)}
        >
          Preview report
        </button>
        {!readOnly && workspace?.can_submit ? (
          <button
            type="button"
            className="inline-flex items-center justify-center px-5 py-3 rounded-xl bg-lush-forest text-white font-bold min-h-[44px] disabled:opacity-50"
            disabled={saving}
            onClick={async () => {
              await submitReport()
              navigate(`${basePath}?tab=reports&section=progress`)
            }}
          >
            {saving ? 'Submitting…' : 'Submit for CM review'}
          </button>
        ) : null}
      </footer>
    </>
  )
}
