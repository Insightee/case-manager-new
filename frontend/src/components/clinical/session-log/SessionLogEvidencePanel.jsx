import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../../lib/apiClient.js'
import {
  emptyGoalEntry,
  emptyStrategyRow,
  normalizeGoalEntry,
  prepareGoalForSubmit,
  parseActivityPhases,
} from '../../../lib/clinicalScoring.js'
import { loadSessionLogRepository } from '../../../lib/sessionLogRepository.js'
import { AddStrategyOverlay } from './AddStrategyOverlay.jsx'
import { CreateGoalOverlay } from './CreateGoalOverlay.jsx'
import { GoalSessionCard } from './GoalSessionCard.jsx'

function repoGoalToEntry(g) {
  return emptyGoalEntry({
    id: g.goal_card_id,
    label: g.label,
    goal_statement: g.label,
    domain_key: g.domain_key,
    baseline: g.goal_brief || g.baseline,
    core_domains: g.core_domains || [],
    core_environments: g.core_environments || [],
  })
}

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
  const [expandedIdx, setExpandedIdx] = useState(0)
  const [showGoalOverlay, setShowGoalOverlay] = useState(false)
  const [strategyPanelIdx, setStrategyPanelIdx] = useState(null)
  const [strategyOverlayIdx, setStrategyOverlayIdx] = useState(null)

  const reloadRepo = useCallback(async () => {
    if (!caseId) return null
    const data = await loadSessionLogRepository(caseId)
    setRepo(data)
    return data
  }, [caseId])

  useEffect(() => {
    let cancelled = false
    async function hydrate() {
      if (!caseId) {
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
              goals: evidence.goals.map((g) => normalizeGoalEntry(g)),
              strategies: evidence.strategies || [],
            })
            return
          }
        }

        if (!value?.goals?.length && data.goals.length) {
          onChange?.({
            schema_version: 2,
            goals: data.goals.slice(0, 3).map(repoGoalToEntry),
            strategies: [],
          })
        } else if (!value?.goals?.length) {
          onChange?.({ schema_version: 2, goals: [emptyGoalEntry()], strategies: [] })
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

  async function handleGoalCreated(candidate) {
    await reloadRepo()
    if (candidate?.label) {
      patchGoals([
        ...goals,
        repoGoalToEntry({
          goal_card_id: null,
          label: candidate.label,
          domain_key: candidate.domain_key,
          core_domains: candidate.core_domains,
          core_environments: candidate.core_environments,
        }),
      ])
      setExpandedIdx(goals.length)
    }
  }

  async function handleStrategyCreated(candidate, goalIdx = expandedIdx) {
    await reloadRepo()
    if (candidate?.label) {
      updateGoal(goalIdx, {
        strategies: [
          ...(goals[goalIdx]?.strategies || []),
          {
            ...emptyStrategyRow(goals[goalIdx]?.goal_card_id),
            strategy_id: candidate.id,
            strategy_label: candidate.label,
            custom_strategy_id: candidate.id,
          },
        ],
      })
    }
  }

  function selectCaseGoal(i, caseGoal) {
    updateGoal(i, repoGoalToEntry(caseGoal))
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
          Goals
        </h3>
        {!readOnly ? (
          <button type="button" className="sl-v2-btn-add" onClick={() => setShowGoalOverlay(true)}>
            + Add goal
          </button>
        ) : null}
      </header>

      {goals.map((g, i) => (
        <GoalSessionCard
          key={i}
          goal={g}
          index={i}
          expanded={expandedIdx === i}
          onToggle={() => setExpandedIdx(expandedIdx === i ? -1 : i)}
          readOnly={readOnly}
          repo={repo}
          caseId={caseId}
          environment={environment}
          otherCaseGoals={otherGoalsByIndex[i] || []}
          onSelectCaseGoal={(caseGoal) => selectCaseGoal(i, caseGoal)}
          showStrategyPanel={strategyPanelIdx === i}
          onToggleStrategyPanel={() => setStrategyPanelIdx(strategyPanelIdx === i ? null : i)}
          onCreateStrategy={() => {
            setStrategyOverlayIdx(i)
            setStrategyPanelIdx(null)
          }}
          onUpdate={(patch) => updateGoal(i, patch)}
          onPickStrategy={(item) => {
            updateGoal(i, {
              strategies: [
                {
                  ...emptyStrategyRow(g.goal_card_id),
                  strategy_id: item.strategy_id,
                  strategy_label: item.label,
                  strategy_steps: item.strategy_steps || ['', '', ''],
                  expected_outcome: item.expected_outcome || item.when_to_use || '',
                },
              ],
            })
            setStrategyPanelIdx(null)
          }}
        />
      ))}

      {showGoalOverlay ? (
        <CreateGoalOverlay
          caseId={caseId}
          sessionId={sessionId}
          logId={logId}
          onClose={() => setShowGoalOverlay(false)}
          onCreated={handleGoalCreated}
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
  const hasGoal = goalRows.some((g) => (g.goal_label || '').trim())
  const hasNestedStrat = goalRows.some((g) =>
    (g.strategies || []).some((s) => (s.strategy_label || '').trim() || s.strategy_feedback)
  )
  const hasLoose = (evidence.strategies || []).some((s) => (s.strategy_label || '').trim())
  const hasScores = goalRows.some(
    (g) =>
      g.participation_score != null ||
      g.independence_score != null ||
      g.goal_achievement_score != null
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
  const parts = evidence.goals.flatMap((g) => {
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
  return {
    ...evidence,
    goals: (evidence.goals || []).map((g) => prepareGoalForSubmit(g)),
  }
}
