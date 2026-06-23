import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { apiFetch } from '../../../lib/apiClient.js'
import {
  emptyGoalEntry,
  emptyStrategyRow,
  goalHasSessionWork,
  normalizeGoalEntry,
  prepareGoalForSubmit,
  parseActivityPhases,
} from '../../../lib/clinicalScoring.js'
import { loadSessionLogRepository } from '../../../lib/sessionLogRepository.js'
import {
  buildCaseGoalsForSessionLog,
  goalLocalId,
  repoGoalToSessionEntry,
  strategyRowFromRepoItem,
} from '../../../lib/sessionLogGoals.js'
import { AddStrategyOverlay } from './AddStrategyOverlay.jsx'
import { CreateGoalOverlay } from './CreateGoalOverlay.jsx'
import { GoalSessionCard } from './GoalSessionCard.jsx'
import { SessionLogGoalSearch } from './SessionLogGoalSearch.jsx'

export function SessionLogEvidencePanel({
  caseId,
  logId,
  sessionId,
  environment,
  value,
  onChange,
  readOnly = false,
}) {
  const [repo, setRepo] = useState(null)
  const [loading, setLoading] = useState(true)
  const [expandedIdx, setExpandedIdx] = useState(-1)
  const [showGoalOverlay, setShowGoalOverlay] = useState(false)
  const [strategyPanelIdx, setStrategyPanelIdx] = useState(null)
  const [strategyOverlayIdx, setStrategyOverlayIdx] = useState(null)
  const hydratedRef = useRef(null)
  const cardRefs = useRef({})

  const reloadRepo = useCallback(async () => {
    if (!caseId) return null
    const data = await loadSessionLogRepository(caseId)
    setRepo(data)
    return data
  }, [caseId])

  useEffect(() => {
    let cancelled = false
    const hydrateKey = `${caseId}:${logId || 'new'}`

    async function hydrate() {
      if (!caseId) {
        setLoading(false)
        return
      }
      if (hydratedRef.current === hydrateKey && value?.goals?.length) {
        setLoading(false)
        return
      }
      setLoading(true)
      try {
        const data = await loadSessionLogRepository(caseId)
        if (cancelled) return
        setRepo(data)

        if (logId) {
          const evidence = await apiFetch(`/api/v1/daily-logs/${logId}/session-evidence`).catch(() => null)
          if (cancelled) return
          if (evidence?.schema_version === 1) return
          if (evidence?.goals?.length) {
            onChange?.({
              schema_version: 2,
              goals: evidence.goals.map((g, i) =>
                normalizeGoalEntry({ ...g, _localId: g._localId || goalLocalId(g, i) }),
              ),
              strategies: evidence.strategies || [],
            })
            hydratedRef.current = hydrateKey
            if (expandedIdx < 0) setExpandedIdx(0)
            return
          }
        }

        if (!value?.goals?.length) {
          const caseGoals = buildCaseGoalsForSessionLog(data)
          onChange?.({
            schema_version: 2,
            goals: caseGoals,
            strategies: [],
          })
          hydratedRef.current = hydrateKey
          if (caseGoals.length) setExpandedIdx(0)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    hydrate()
    return () => {
      cancelled = true
    }
  }, [caseId, logId])

  const goals = value?.goals || []

  const otherGoalsByIndex = useMemo(() => {
    const pool = repo?.goals || []
    return goals.map((g, idx) => {
      const currentLabel = (g.goal_label || '').toLowerCase()
      return pool.filter((item) => {
        const label = (item.label || '').toLowerCase()
        if (!label || label === currentLabel) return false
        return !goals.some((og, oi) => oi !== idx && (og.goal_label || '').toLowerCase() === label)
      })
    })
  }, [goals, repo?.goals])

  function patchGoals(nextGoals) {
    onChange?.({ schema_version: 2, goals: nextGoals, strategies: value?.strategies || [] })
  }

  function updateGoal(i, patch) {
    patchGoals(goals.map((g, idx) => (idx === i ? normalizeGoalEntry({ ...g, ...patch }) : g)))
  }

  function focusGoalIndex(idx) {
    setExpandedIdx(idx)
    setStrategyPanelIdx(null)
    requestAnimationFrame(() => {
      const el = cardRefs.current[goalLocalId(goals[idx], idx)]
      el?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    })
  }

  function addOrFocusCaseGoal(caseGoal) {
    const label = (caseGoal.label || '').trim().toLowerCase()
    const existingIdx = goals.findIndex((g) => (g.goal_label || '').trim().toLowerCase() === label)
    if (existingIdx >= 0) {
      focusGoalIndex(existingIdx)
      return
    }
    const entry = repoGoalToSessionEntry(caseGoal, goals.length)
    patchGoals([...goals, entry])
    focusGoalIndex(goals.length)
  }

  function addGoalFromSearch(item) {
    addOrFocusCaseGoal(item)
  }

  function attachStrategyToExpanded(item) {
    const idx = expandedIdx >= 0 ? expandedIdx : 0
    if (!goals[idx]) return
    updateGoal(idx, {
      strategies: [strategyRowFromRepoItem({ ...item, goal_card_id: goals[idx].goal_card_id })],
    })
    setStrategyPanelIdx(null)
    focusGoalIndex(idx)
  }

  async function handleGoalAndStrategyCreated({ goal, strategy }) {
    await reloadRepo()
    const entry = {
      ...repoGoalToSessionEntry(
        {
          ...goal,
          label: goal.label,
          baseline_state: goal.baseline_state,
          desired_state: goal.desired_state,
          core_domains: goal.core_domains,
          core_environments: goal.core_environments,
          status: goal.status || 'local',
          id: goal.id,
        },
        goals.length,
      ),
      strategies: strategy?.label
        ? [
            {
              ...emptyStrategyRow(null),
              strategy_id: strategy.id,
              strategy_label: strategy.label,
              strategy_steps: strategy.strategy_steps || ['', '', ''],
              expected_outcome: strategy.expected_outcome || strategy.when_to_use || '',
              custom_strategy_id: strategy.id,
            },
          ]
        : [],
    }
    patchGoals([...goals, entry])
    focusGoalIndex(goals.length)
  }

  async function handleStrategyCreated(candidate, goalIdx = expandedIdx) {
    await reloadRepo()
    if (candidate?.label && goals[goalIdx]) {
      updateGoal(goalIdx, {
        strategies: [strategyRowFromRepoItem({ ...candidate, goal_card_id: goals[goalIdx].goal_card_id })],
      })
      focusGoalIndex(goalIdx)
    }
  }

  if (loading) {
    return <p className="gs-muted">Loading goals…</p>
  }

  if (value?.schema_version === 1) {
    return null
  }

  return (
    <section className="sl-goals-section" aria-labelledby="sl-goals-title">
      <header className="sl-goals-section__head">
        <h3 id="sl-goals-title" className="sl-goals-section__title">
          Goals worked on today
        </h3>
        {!readOnly ? (
          <button type="button" className="sl-v2-btn-add" onClick={() => setShowGoalOverlay(true)}>
            + Add goal
          </button>
        ) : null}
      </header>

      <SessionLogGoalSearch
        repo={repo}
        readOnly={readOnly}
        onPickGoal={addGoalFromSearch}
        onPickStrategy={attachStrategyToExpanded}
      />

      {!goals.length ? (
        <p className="gs-muted sl-goals-section__empty">
          No case goals loaded yet. Search above, pick from your case plan, or tap <strong>+ Add goal</strong>.
        </p>
      ) : null}

      {goals.map((g, i) => {
        const lid = goalLocalId(g, i)
        return (
          <GoalSessionCard
            key={lid}
            cardRef={(el) => {
              if (el) cardRefs.current[lid] = el
            }}
            goal={g}
            index={i}
            expanded={expandedIdx === i}
            onToggle={() => {
              if (expandedIdx === i) {
                setExpandedIdx(-1)
              } else {
                focusGoalIndex(i)
              }
            }}
            readOnly={readOnly}
            repo={repo}
            caseId={caseId}
            environment={environment}
            otherCaseGoals={otherGoalsByIndex[i] || []}
            onSelectCaseGoal={addOrFocusCaseGoal}
            showStrategyPanel={strategyPanelIdx === i}
            onToggleStrategyPanel={() => setStrategyPanelIdx(strategyPanelIdx === i ? null : i)}
            onCreateStrategy={() => {
              setStrategyOverlayIdx(i)
              setStrategyPanelIdx(null)
            }}
            onUpdate={(patch) => updateGoal(i, patch)}
            onPickStrategy={(item) => {
              updateGoal(i, { strategies: [strategyRowFromRepoItem({ ...item, goal_card_id: g.goal_card_id })] })
              setStrategyPanelIdx(null)
            }}
          />
        )
      })}

      {showGoalOverlay ? (
        <CreateGoalOverlay
          caseId={caseId}
          sessionId={sessionId}
          logId={logId}
          reportType="session"
          onClose={() => setShowGoalOverlay(false)}
          onCreated={handleGoalAndStrategyCreated}
        />
      ) : null}

      {strategyOverlayIdx != null ? (
        <AddStrategyOverlay
          caseId={caseId}
          logId={logId}
          goalCardId={goals[strategyOverlayIdx]?.goal_card_id}
          goalLabel={goals[strategyOverlayIdx]?.goal_label}
          onClose={() => setStrategyOverlayIdx(null)}
          onCreated={(candidate) => {
            handleStrategyCreated(candidate, strategyOverlayIdx)
            setStrategyOverlayIdx(null)
          }}
        />
      ) : null}
    </section>
  )
}

export function sessionEvidenceHasPayload(evidence) {
  if (!evidence || evidence.schema_version === 1) return false
  const goalRows = evidence.goals || []
  const hasGoal = goalRows.some((g) => goalHasSessionWork(g))
  const hasNestedStrat = goalRows.some((g) =>
    (g.strategies || []).some((s) => (s.strategy_label || '').trim() || s.strategy_feedback),
  )
  const hasLoose = (evidence.strategies || []).some((s) => (s.strategy_label || '').trim())
  const hasScores = goalRows.some(
    (g) =>
      g.participation_score != null ||
      g.independence_score != null ||
      g.goal_achievement_score != null ||
      g.marked_complete_today,
  )
  const hasActivities = goalRows.some((g) => {
    const steps = (g.strategies || [])[0]?.strategy_steps || []
    if (steps.some(Boolean)) return true
    const p = g.activity_phases || parseActivityPhases(g.activity_used)
    return p.initial || p.core || p.closing
  })
  return hasGoal || hasNestedStrat || hasLoose || hasScores || hasActivities
}

export function buildActivitiesDoneFromEvidence(evidence) {
  if (!evidence?.goals?.length) return ''
  const parts = evidence.goals.filter(goalHasSessionWork).flatMap((g) => {
    const label = g.goal_label ? `${g.goal_label}: ` : ''
    const steps = (g.strategies || [])[0]?.strategy_steps || []
    const fromSteps = steps.filter(Boolean).map((x) => `${label}${x}`)
    if (fromSteps.length) return fromSteps
    const p = g.activity_phases || parseActivityPhases(g.activity_used)
    return [p.initial, p.core, p.closing].filter(Boolean).map((x) => `${label}${x}`)
  })
  return parts.join('; ').slice(0, 2000)
}

export function prepareEvidenceForSubmit(evidence) {
  if (!evidence) return evidence
  const workedGoals = (evidence.goals || []).filter(goalHasSessionWork).map((g) => prepareGoalForSubmit(g))
  return {
    ...evidence,
    goals: workedGoals,
  }
}
