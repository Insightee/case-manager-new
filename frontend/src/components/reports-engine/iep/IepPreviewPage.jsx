import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { formatDisplayDate } from '../../../lib/datetime.js'
import { IEP_DOMAIN_TABS } from '../../../lib/iepObservationAlign.js'
import { useIepReport } from '../hooks/useIepReport.js'
import { StitchWorkspaceSubhead } from '../observation/stitch/ObservationStitchBlocks.jsx'
import { labelForMeasurement } from '../../../lib/clinicalMeasurementCriteria.js'
import { IepApprovalPanel } from './IepApprovalPanel.jsx'

export function IepPreviewPage({ caseId, caseCode, childName, variant = 'therapist' }) {
  const navigate = useNavigate()
  const basePath = variant === 'admin' ? `/admin/cases/${caseId}` : `/therapist/cases/${caseId}`
  const [mode, setMode] = useState('clinical')
  const {
    workspace,
    preview,
    loading,
    loadPreview,
    loadWorkspace,
    approveReport,
    stakeholderApprove,
    stakeholderRequestReview,
    error,
  } = useIepReport(caseId)

  useEffect(() => {
    loadWorkspace()
  }, [loadWorkspace])

  useEffect(() => {
    if (workspace?.report_id) loadPreview(mode)
  }, [workspace?.report_id, mode, loadPreview])

  const data = preview || workspace
  const sections = data?.sections || []
  const goals = sections.find((s) => s.key === 'goals_plan')?.structured_data?.goals || []
  const domains = sections.find((s) => s.key === 'priority_domains')?.structured_data || {}
  const talent = sections.find((s) => s.key === 'talent_development')?.structured_data || {}
  const plan = sections.find((s) => s.key === 'review_parent_plan')?.structured_data || {}
  const isParent = mode === 'parent'

  function sectionNarrative(sec) {
    const text = sec?.narrative_text || ''
    if (!text.startsWith('{')) return text
    try {
      const parsed = JSON.parse(text)
      return Object.values(parsed)
        .filter((v) => typeof v === 'string')
        .join('\n\n')
    } catch {
      return text
    }
  }

  return (
    <>
      <StitchWorkspaceSubhead caseCode={caseCode} title={`IEP Preview — ${childName || 'Client'}`} />
      {error ? <p className="text-sm text-error mb-4">{error}</p> : null}

      <div className="flex flex-wrap gap-2 mb-6">
        <button
          type="button"
          className={`min-h-[44px] px-4 rounded-xl font-semibold text-sm${mode === 'clinical' ? ' bg-lush-forest text-white' : ' border'}`}
          onClick={() => setMode('clinical')}
        >
          Clinical
        </button>
        <button
          type="button"
          className={`min-h-[44px] px-4 rounded-xl font-semibold text-sm${mode === 'parent' ? ' bg-lush-forest text-white' : ' border'}`}
          onClick={() => setMode('parent')}
        >
          Parent preview
        </button>
        <Link to={`${basePath}?tab=reports&section=iep&view=builder`} className="min-h-[44px] px-4 rounded-xl border font-semibold text-sm inline-flex items-center no-underline text-inherit">
          Back to builder
        </Link>
      </div>

      {loading ? <p className="text-sm">Loading preview…</p> : null}

      <article className="max-w-3xl mx-auto bg-surface-container-lowest rounded-xl clinical-shadow border border-outline-variant/30 p-8">
        <p className="text-xs font-bold uppercase text-lush-forest font-mono m-0">Confirmed support plan</p>
        <h1 className="text-3xl font-bold text-lush-forest mt-2 mb-4">{childName}&apos;s growth journey</h1>

        {sections
          .filter((s) => {
            if (s.key === 'internal_cm_notes' || s.key === 'goals_plan') return false
            if (isParent && (s.key === 'clinical_insights' || s.visibility === 'internal_only')) return false
            return true
          })
          .map((s) => (
            <section key={s.key} className="mb-6">
              <h2 className="text-sm font-bold uppercase font-mono text-outline">{s.label}</h2>
              {sectionNarrative(s) ? <p className="text-sm whitespace-pre-wrap">{sectionNarrative(s)}</p> : null}
              {s.key === 'clinical_insights' && s.structured_data ? (
                <div className="grid md:grid-cols-2 gap-3 mt-2 text-sm">
                  {s.structured_data.promising_strategy ? (
                    <p className="m-0 p-3 rounded-lg bg-lush-mint/20">
                      <strong>Promising:</strong> {s.structured_data.promising_strategy}
                    </p>
                  ) : null}
                  {s.structured_data.emerging_barrier ? (
                    <p className="m-0 p-3 rounded-lg bg-error-container/30">
                      <strong>Barrier:</strong> {s.structured_data.emerging_barrier}
                    </p>
                  ) : null}
                </div>
              ) : null}
            </section>
          ))}

        {domains.present_levels ? (
          <section className="mb-6">
            <h2 className="text-sm font-bold uppercase font-mono text-outline mb-3">Domains</h2>
            {IEP_DOMAIN_TABS.map((tab) => {
              const row = domains.present_levels[tab.id]
              if (!row?.strengths && !row?.support_needs) return null
              return (
                <div key={tab.id} className="mb-4 p-4 rounded-xl border border-outline-variant/30">
                  <p className="font-semibold m-0 mb-2">{tab.label}</p>
                  {row.strengths ? <p className="text-sm m-0 mb-1"><strong>Strengths:</strong> {row.strengths}</p> : null}
                  {row.support_needs ? <p className="text-sm m-0"><strong>Supports:</strong> {row.support_needs}</p> : null}
                </div>
              )
            })}
          </section>
        ) : null}

        {(talent.imported_strengths?.length || talent.additional_strengths || talent.opportunities) ? (
          <section className="mb-6">
            <h2 className="text-sm font-bold uppercase font-mono text-outline mb-3">Strengths & growth</h2>
            {talent.imported_strengths?.length ? (
              <div className="flex flex-wrap gap-2 mb-3">
                {talent.imported_strengths.map((s) => (
                  <span key={s} className="px-2 py-1 rounded-lg bg-lush-mint/30 text-sm">{s}</span>
                ))}
              </div>
            ) : null}
            {talent.additional_strengths ? <p className="text-sm m-0 mb-2">{talent.additional_strengths}</p> : null}
            {talent.opportunities ? <p className="text-sm m-0 text-on-surface-variant">{talent.opportunities}</p> : null}
          </section>
        ) : null}

        {plan.review_date ? (
          <p className="text-sm mb-4">
            <strong>Review date:</strong> {formatDisplayDate(plan.review_date)}
          </p>
        ) : null}

        {!isParent && plan.therapist_input ? (
          <section className="mb-6">
            <h2 className="text-sm font-bold uppercase font-mono text-outline">Therapist input</h2>
            <p className="text-sm whitespace-pre-wrap m-0">{plan.therapist_input}</p>
          </section>
        ) : null}

        {(plan.parent_input_draft || plan.parent_inputs?.length) ? (
          <section className="mb-6">
            <h2 className="text-sm font-bold uppercase font-mono text-outline">Family input</h2>
            {plan.parent_input_draft ? <p className="text-sm m-0">{plan.parent_input_draft}</p> : null}
            {(plan.parent_inputs || []).map((p) => (
              <p key={p.id} className="text-sm m-0 mt-2">{p.text}</p>
            ))}
          </section>
        ) : null}

        <section>
          <h2 className="text-sm font-bold uppercase font-mono text-outline mb-3">Active learning goals</h2>
          {goals.map((g, i) => (
            <div key={g.iep_goal_id} className="mb-4 p-4 rounded-xl border border-outline-variant/30">
              <p className="text-xs font-mono m-0">Goal {i + 1}</p>
              <p className="font-bold m-0 mt-1">{g.parent_facing_wording || g.goal_statement || g.title}</p>
              <p className="text-xs text-on-surface-variant mt-2 m-0">
                {labelForMeasurement('participation', g.participation)} · {labelForMeasurement('goal_achievement', g.goal_achievement)}
              </p>
            </div>
          ))}
        </section>
      </article>

      <div className="max-w-3xl mx-auto mt-6">
        <IepApprovalPanel
          approval={workspace?.iep_approval}
          reviewThread={workspace?.review_thread}
          variant={variant === 'admin' ? 'admin' : isParent ? 'parent' : 'therapist'}
          onStakeholderApprove={stakeholderApprove}
          onStakeholderRequestReview={async (role, comment) => {
            await stakeholderRequestReview(role, comment)
            setReviewComment('')
          }}
        />
      </div>

      {variant === 'admin' && workspace?.status === 'submitted_for_review' && workspace?.iep_approval?.ready_for_final_approval ? (
        <div className="max-w-3xl mx-auto mt-6 flex gap-3">
          <button
            type="button"
            className="min-h-[44px] px-6 rounded-xl bg-lush-forest text-white font-bold"
            onClick={() => approveReport(false)}
          >
            Approve IEP
          </button>
        </div>
      ) : null}
    </>
  )
}
