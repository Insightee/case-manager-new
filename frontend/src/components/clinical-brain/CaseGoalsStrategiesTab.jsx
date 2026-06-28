import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { GOALS_STRATEGIES_ENGINE_V2 } from '../../lib/reportsRevampFlags.js'
import { currentReportMonth, fetchCaseClinicalEvidenceEvents } from '../../lib/clinicalEvidenceApi.js'
import { countEvidenceByGoalCard } from '../../lib/goalEngineHelpers.js'
import { enrichStrategyPoolFromApi } from '../../lib/clinicalBrainMockData.js'
import { CaseGoalsPanel } from '../case-profile/sections/CaseGoalsPanel.jsx'
import { CaseStrategiesPanel } from '../case-profile/sections/CaseStrategiesPanel.jsx'
import { CreateGoalModal } from '../clinical/goals-strategy/CreateGoalModal.jsx'
import { CreateStrategyModal } from '../clinical/goals-strategy/CreateStrategyModal.jsx'
import { SubmitCustomStrategyForm } from './SubmitCustomStrategyForm.jsx'
import {
  ActiveIepGoalCard,
  GoalCandidateCard,
  LibraryShortcuts,
  StrategyInsightsPlaceholder,
  StrategySuggestionCard,
  StrategyTrialCard,
} from './CaseGoalCards.jsx'
import '../../styles/goals-strategies-engine.css'
import '../../styles/clinical-brain.css'

export function CaseGoalsStrategiesTab({
  caseId,
  canModerate = false,
  variant = 'therapist',
  onEditGoal,
}) {
  const [payload, setPayload] = useState(null)
  const [poolSuggestions, setPoolSuggestions] = useState([])
  const [evidenceCounts, setEvidenceCounts] = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [showGoalModal, setShowGoalModal] = useState(false)
  const [showStrategyModal, setShowStrategyModal] = useState(false)
  const [showCustomStrategy, setShowCustomStrategy] = useState(false)

  const load = useCallback(async () => {
    if (!caseId || !GOALS_STRATEGIES_ENGINE_V2) return
    setLoading(true)
    setError('')
    try {
      const [data, evidence, search] = await Promise.all([
        apiFetch(`/api/v1/cases/${caseId}/goals-engine`),
        fetchCaseClinicalEvidenceEvents(caseId, currentReportMonth()).catch(() => ({ events: [] })),
        apiFetch(`/api/v1/cases/${caseId}/clinical/repository-search?kind=strategies`).catch(() => ({ items: [] })),
      ])
      setPayload(data)
      setEvidenceCounts(countEvidenceByGoalCard(evidence.events || []))
      setPoolSuggestions(enrichStrategyPoolFromApi(search.items || []))
    } catch (err) {
      setError(err.message || 'Could not load goals & strategies')
    } finally {
      setLoading(false)
    }
  }, [caseId])

  useEffect(() => {
    load()
  }, [load])

  const iepGoals = useMemo(
    () =>
      (payload?.iep_goals || []).map((g) => ({
        ...g,
        evidence_count: evidenceCounts[g.goal_card_id] || 0,
      })),
    [payload, evidenceCounts],
  )

  const goalsToReview = useMemo(
    () =>
      (payload?.goals || []).filter((g) => g.is_pending || g.status === 'local' || g.status === 'candidate'),
    [payload],
  )

  const strategyTrials = useMemo(() => payload?.strategies || [], [payload])

  async function sendGoalToReview(goal) {
    if (!caseId) return
    try {
      if (goal.id) {
        await apiFetch(`/api/v1/cases/${caseId}/goal-candidates/${goal.id}`, {
          method: 'PATCH',
          body: JSON.stringify({ action: 'submit_for_cm_review' }),
        })
      } else {
        await apiFetch(`/api/v1/cases/${caseId}/goal-candidates`, {
          method: 'POST',
          body: JSON.stringify({
            label: goal.label,
            goal_statement: goal.goal_statement || goal.label,
            domain_key: goal.domain_key || (goal.core_domains || [])[0],
            rationale: goal.rationale,
            goal_use: 'cm_iep_review',
            source: 'therapist',
          }),
        })
      }
      setMsg('Sent to case manager for review.')
      load()
    } catch (err) {
      setMsg(err.message || 'Could not send for review')
    }
  }

  if (!GOALS_STRATEGIES_ENGINE_V2) {
    return (
      <>
        <CaseGoalsPanel caseId={caseId} variant={variant} canModerate={canModerate} />
        <CaseStrategiesPanel caseId={caseId} variant={variant} />
      </>
    )
  }

  if (loading) return <p className="gs-muted">Loading goals &amp; strategies…</p>
  if (error) return <p className="gs-error">{error}</p>

  return (
    <div className="gs-engine gs-engine-page cb-case-goals">
      <header className="gs-engine-page__head">
        <div>
          <h2 className="gs-engine-page__title">Goals &amp; Strategies</h2>
          <p className="gs-engine-page__sub">
            Case-specific goals, trials, and evidence — organisation library is separate.
          </p>
        </div>
        <div className="gs-engine-actions">
          <button type="button" className="gs-btn gs-btn--primary" onClick={() => setShowGoalModal(true)}>
            + Propose goal
          </button>
          <button type="button" className="gs-btn" onClick={() => setShowCustomStrategy(true)}>
            + Propose strategy
          </button>
        </div>
      </header>

      {payload?.pending_count ? (
        <p className="gs-engine-pending-banner">
          {payload.pending_count} item{payload.pending_count === 1 ? '' : 's'} awaiting case manager review
        </p>
      ) : null}
      {msg ? <p className="gs-hint">{msg}</p> : null}

      <section className="cb-section">
        <h3 className="cb-section__label">Active IEP goals</h3>
        <div className="cb-grid cb-grid--2">
          {iepGoals.map((g) => (
            <ActiveIepGoalCard key={`iep-${g.goal_card_id}`} goal={g} caseId={caseId} variant={variant} />
          ))}
          {!iepGoals.length ? <p className="gs-muted">No active IEP goals — complete an IEP plan first.</p> : null}
        </div>
      </section>

      <section className="cb-section">
        <h3 className="cb-section__label">Goals to review</h3>
        <div className="cb-grid cb-grid--2">
          {goalsToReview.map((g) => (
            <GoalCandidateCard
              key={`goal-${g.id}`}
              goal={g}
              caseId={caseId}
              variant={variant}
              onEdit={onEditGoal || (() => setShowGoalModal(true))}
              onSendReview={sendGoalToReview}
            />
          ))}
          {!goalsToReview.length ? (
            <p className="gs-muted">No case goal candidates — propose one from session log or observation.</p>
          ) : null}
        </div>
      </section>

      <section className="cb-section">
        <h3 className="cb-section__label">Strategy suggestions</h3>
        <div className="cb-grid cb-grid--2">
          {poolSuggestions.slice(0, 6).map((s) => (
            <StrategySuggestionCard
              key={`sug-${s.id}`}
              strategy={s}
              caseId={caseId}
              variant={variant}
              onUseLog={() => setShowCustomStrategy(true)}
              onAddTrial={() => setShowStrategyModal(true)}
            />
          ))}
          {!poolSuggestions.length ? (
            <p className="gs-muted">No pool suggestions yet — capture session evidence to surface helpful supports.</p>
          ) : null}
        </div>
      </section>

      <section className="cb-section">
        <h3 className="cb-section__label">Strategy trials</h3>
        <div className="cb-grid cb-grid--2">
          {strategyTrials.map((s) => (
            <StrategyTrialCard key={`trial-${s.id}`} strategy={s} caseId={caseId} variant={variant} />
          ))}
          {!strategyTrials.length ? (
            <p className="gs-muted">No strategy trials on this case — add one from session log or here.</p>
          ) : null}
        </div>
      </section>

      <section className="cb-section">
        <h3 className="cb-section__label">Goal &amp; strategy library</h3>
        <LibraryShortcuts variant={variant} />
      </section>

      <section className="cb-section">
        <h3 className="cb-section__label">Strategy insights</h3>
        <StrategyInsightsPlaceholder />
      </section>

      {showGoalModal ? (
        <CreateGoalModal
          caseId={caseId}
          captureGoalUse
          onClose={() => setShowGoalModal(false)}
          onCreated={() => {
            setShowGoalModal(false)
            setMsg('Goal saved.')
            load()
          }}
        />
      ) : null}

      {showStrategyModal ? (
        <CreateStrategyModal
          caseId={caseId}
          captureStrategyType
          onClose={() => setShowStrategyModal(false)}
          onCreated={() => {
            setShowStrategyModal(false)
            load()
          }}
        />
      ) : null}

      {showCustomStrategy ? (
        <SubmitCustomStrategyForm
          caseId={caseId}
          mode="therapist"
          onClose={() => setShowCustomStrategy(false)}
          onSaved={() => {
            setShowCustomStrategy(false)
            setMsg('Strategy candidate saved.')
            load()
          }}
        />
      ) : null}
    </div>
  )
}
