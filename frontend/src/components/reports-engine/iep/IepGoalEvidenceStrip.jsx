import { useEffect, useState } from 'react'
import { ClinicalChipGroup } from '../../clinical-ui/ClinicalChipGroup.jsx'
import {
  IEP_GOAL_REVIEW_OPTIONS,
  IEP_STRATEGY_STATUS_OPTIONS,
  NEXT_STEP_OPTIONS,
} from '../../../lib/clinicalEvidenceFields.js'
import {
  aggregateGoalEvidence,
  currentReportMonth,
  fetchCaseClinicalEvidenceEvents,
  filterEventsForGoal,
} from '../../../lib/clinicalEvidenceApi.js'

function labelForOption(options, id) {
  return options.find((o) => o.id === id)?.label || id
}

export function IepGoalEvidenceStrip({
  caseId,
  goal,
  readOnly = false,
  onReviewDecision,
  onStrategyStatusChange,
}) {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [strategyStatus, setStrategyStatus] = useState(goal.strategy_status || 'planned')
  const [reviewDecision, setReviewDecision] = useState(goal.review_decision || null)
  const [dismissedAdaptations, setDismissedAdaptations] = useState({})

  useEffect(() => {
    if (!caseId || !goal) return undefined
    let cancelled = false
    async function load() {
      setLoading(true)
      try {
        const data = await fetchCaseClinicalEvidenceEvents(caseId, currentReportMonth())
        if (cancelled) return
        const events = filterEventsForGoal(data.events || [], goal)
        setStats(aggregateGoalEvidence(events))
      } catch {
        if (!cancelled) setStats(null)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [caseId, goal])

  const repeated = stats?.repeatedAdaptations || {}
  const repeatedKeys = Object.keys(repeated).filter((k) => !dismissedAdaptations[k])

  return (
    <div className="iep-evidence-strip rounded-xl border border-lush-forest/20 bg-lush-mint/10 p-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-bold uppercase text-lush-forest m-0">Live session evidence</p>
        {stats?.sessionCount ? (
          <span className="text-xs bg-white/70 px-2 py-0.5 rounded-full text-on-surface-variant internal-only-badge">
            Internal evidence strength
          </span>
        ) : null}
      </div>

      {loading ? (
        <p className="text-sm text-on-surface-variant m-0">Loading evidence…</p>
      ) : stats?.sessionCount ? (
        <div className="grid sm:grid-cols-2 gap-2 text-sm">
          <span>{stats.sessionCount} sessions addressed</span>
          <span>{stats.activeParticipationCount} active participation</span>
          <span>{stats.adaptationCount} with adaptation</span>
          {stats.nextStep ? (
            <span>Next step: {labelForOption(NEXT_STEP_OPTIONS, stats.nextStep)}</span>
          ) : null}
          {stats.commonBarriers.length ? (
            <span className="sm:col-span-2">Common barriers: {stats.commonBarriers.join(', ')}</span>
          ) : null}
        </div>
      ) : (
        <p className="text-sm text-on-surface-variant m-0">No session evidence this month yet — logs will appear here automatically.</p>
      )}

      {repeatedKeys.length ? (
        <div className="rounded-lg bg-amber-50 border border-amber-200 p-3">
          <p className="text-sm font-semibold m-0 mb-2">Repeated adaptation noticed</p>
          <p className="text-xs m-0 mb-2">
            {repeatedKeys.map((k) => `${k} (${repeated[k]}×)`).join(', ')}
          </p>
          {!readOnly ? (
            <div className="flex flex-wrap gap-2">
              <button type="button" className="min-h-[44px] px-3 rounded-lg border text-xs font-semibold" onClick={() => onStrategyStatusChange?.(goal, 'needs_adaptation')}>
                Add to IEP strategy plan
              </button>
              <button type="button" className="min-h-[44px] px-3 rounded-lg border text-xs font-semibold" onClick={() => onReviewDecision?.(goal, 'cm_review')}>
                Needs CM review
              </button>
              <button type="button" className="min-h-[44px] px-3 rounded-lg border text-xs font-semibold" onClick={() => setDismissedAdaptations(Object.fromEntries(repeatedKeys.map((k) => [k, true])))}>
                Ignore for now
              </button>
            </div>
          ) : null}
        </div>
      ) : null}

      {!readOnly ? (
        <>
          <ClinicalChipGroup
            label="Strategy status"
            options={IEP_STRATEGY_STATUS_OPTIONS}
            value={strategyStatus}
            onChange={(v) => {
              setStrategyStatus(v)
              onStrategyStatusChange?.(goal, v)
            }}
          />
          <ClinicalChipGroup
            label="Review decision"
            options={IEP_GOAL_REVIEW_OPTIONS}
            value={reviewDecision}
            onChange={(v) => {
              setReviewDecision(v)
              onReviewDecision?.(goal, v)
            }}
          />
        </>
      ) : null}
    </div>
  )
}
