import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { GOALS_STRATEGIES_ENGINE_V2 } from '../../lib/reportsRevampFlags.js'
import { splitAssignedGoals, splitAssignedStrategies } from '../../lib/goalEngineHelpers.js'
import { CaseGoalsPanel } from '../case-profile/sections/CaseGoalsPanel.jsx'
import { CaseStrategiesPanel } from '../case-profile/sections/CaseStrategiesPanel.jsx'
import { CreateGoalModal } from '../clinical/goals-strategy/CreateGoalModal.jsx'
import { CreateStrategyModal } from '../clinical/goals-strategy/CreateStrategyModal.jsx'
import { SubmitCustomStrategyForm } from './SubmitCustomStrategyForm.jsx'
import { ActiveIepGoalCard, StrategyTrialCard } from './CaseGoalCards.jsx'
import '../../styles/goals-strategies-engine.css'
import '../../styles/clinical-brain.css'

function AssignedSection({ title, empty, children }) {
  return (
    <section className="cb-section">
      <h3 className="cb-section__label">{title}</h3>
      <div className="cb-grid cb-grid--2">{children}</div>
      {empty ? <p className="gs-muted">{empty}</p> : null}
    </section>
  )
}

export function CaseGoalsStrategiesTab({
  caseId,
  canModerate = false,
  variant = 'therapist',
}) {
  const [payload, setPayload] = useState(null)
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
      const data = await apiFetch(`/api/v1/cases/${caseId}/goals-engine`)
      setPayload(data)
    } catch (err) {
      setError(err.message || 'Could not load goals & strategies')
    } finally {
      setLoading(false)
    }
  }, [caseId])

  useEffect(() => {
    load()
  }, [load])

  const assignedGoals = useMemo(
    () => payload?.assigned_goals || payload?.iep_goals || [],
    [payload],
  )
  const assignedStrategies = useMemo(
    () => payload?.assigned_strategies || payload?.strategies || [],
    [payload],
  )

  const { active: activeGoals, paused: pausedGoals } = useMemo(
    () => splitAssignedGoals(assignedGoals),
    [assignedGoals],
  )
  const { active: activeStrategies, paused: pausedStrategies } = useMemo(
    () => splitAssignedStrategies(assignedStrategies),
    [assignedStrategies],
  )

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

  const goalKey = (g) => `goal-${g.goal_card_id || g.id}`
  const strategyKey = (s) => `strategy-${s.id}-${s.label}`

  return (
    <div className="gs-engine gs-engine-page cb-case-goals">
      <header className="gs-engine-page__head">
        <div>
          <h2 className="gs-engine-page__title">Goals &amp; Strategies</h2>
          <p className="gs-engine-page__sub">
            Active and paused goals and strategies assigned to this child, with session evidence.
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

      {msg ? <p className="gs-hint">{msg}</p> : null}

      <AssignedSection
        title="Active goals"
        empty={!activeGoals.length ? 'No active goals assigned to this child yet.' : null}
      >
        {activeGoals.map((g) => (
          <ActiveIepGoalCard key={goalKey(g)} goal={g} caseId={caseId} variant={variant} />
        ))}
      </AssignedSection>

      {pausedGoals.length ? (
        <AssignedSection title="Paused goals">
          {pausedGoals.map((g) => (
            <ActiveIepGoalCard key={goalKey(g)} goal={g} caseId={caseId} variant={variant} />
          ))}
        </AssignedSection>
      ) : null}

      <AssignedSection
        title="Active strategies"
        empty={!activeStrategies.length ? 'No active strategies assigned to this child yet.' : null}
      >
        {activeStrategies.map((s) => (
          <StrategyTrialCard key={strategyKey(s)} strategy={s} caseId={caseId} variant={variant} />
        ))}
      </AssignedSection>

      {pausedStrategies.length ? (
        <AssignedSection title="Paused strategies">
          {pausedStrategies.map((s) => (
            <StrategyTrialCard key={strategyKey(s)} strategy={s} caseId={caseId} variant={variant} />
          ))}
        </AssignedSection>
      ) : null}

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
