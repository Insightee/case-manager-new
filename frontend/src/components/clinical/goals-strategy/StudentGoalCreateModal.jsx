import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../../lib/apiClient.js'
import { GOAL_MODAL_DOMAIN_CHIPS, GOAL_MODAL_TABS } from '../../../lib/clinicalUiContract.js'
import { STRATEGY_TYPE_OPTIONS } from '../../../lib/clinicalEvidenceFields.js'
import { AI_ENABLED } from '../../../lib/reportsRevampFlags.js'
import { GoalUseCards } from '../../clinical-brain/GoalUseCards.jsx'
import { GoalTemplateLibrary } from '../../clinical-brain/GoalTemplateLibrary.jsx'
import '../../../styles/clinical-brain.css'

const EMPTY_FORM = {
  label: '',
  goal_statement: '',
  baseline_state: '',
  desired_state: '',
  supports: '',
  domain: 'communication_aac',
  strategy_label: '',
  strategy_steps: ['', '', ''],
  goal_use: 'case_candidate',
  strategy_type: 'case_specific',
}

/**
 * Canonical Create Student Goal modal — IEP, observation, session log.
 * Visual contract: docs/design/UI_CONTRACT.md + Stitch mockups.
 */
export function StudentGoalCreateModal({
  caseId,
  clinicalReportId,
  reportType = 'iep',
  childName = 'Student',
  preSelectedGoal = null,
  initialRepositoryKind = null,
  standaloneStrategy = false,
  sessionId,
  logId,
  captureGoalUse = false,
  captureStrategyType = false,
  onClose,
  onCreated,
}) {
  const strategyOnly = Boolean(
    standaloneStrategy ||
      preSelectedGoal?.iep_goal_id ||
      preSelectedGoal?.goal_card_id ||
      preSelectedGoal?.id,
  )
  const [tab, setTab] = useState(standaloneStrategy ? 'custom' : 'templates')
  const [repositoryKind, setRepositoryKind] = useState(
    initialRepositoryKind || (strategyOnly ? 'strategies' : 'goals'),
  )
  const [searchQuery, setSearchQuery] = useState('')
  const [domainFilter, setDomainFilter] = useState('')
  const [templates, setTemplates] = useState([])
  const [templatesLoading, setTemplatesLoading] = useState(false)
  const [form, setForm] = useState({ ...EMPTY_FORM })
  const [previewStrategies, setPreviewStrategies] = useState([])
  const [aiDrafts, setAiDrafts] = useState([])
  const [aiLoading, setAiLoading] = useState(false)
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)
  const wizardIep = reportType === 'iep' && !preSelectedGoal && !standaloneStrategy
  const [wizardStep, setWizardStep] = useState('goal')
  const [createdGoal, setCreatedGoal] = useState(null)
  const [strategyOptions, setStrategyOptions] = useState([])
  const [selectedStrategies, setSelectedStrategies] = useState([])

  async function loadStrategyOptions(domainKey) {
    const params = new URLSearchParams({ kind: 'strategies' })
    if (domainKey) params.set('domain', domainKey)
    const data = await apiFetch(`/api/v1/cases/${caseId}/clinical/repository-search?${params}`)
    setStrategyOptions(data.items || [])
  }

  async function createIepGoalRecord(payload) {
    return apiFetch(`/api/v1/reports/${clinicalReportId}/iep/goals`, {
      method: 'POST',
      body: JSON.stringify({
        goal_source_id: payload.source_id || undefined,
        source_type: payload.source_type || 'manual',
        title: payload.label,
        goal_statement: payload.goal_statement || payload.label,
        domain: payload.domain_key || payload.domain || 'general',
        baseline_current_state: payload.baseline_state || '',
        desired_state: payload.desired_state || '',
        participation: 'emerging_participation',
        independence_support_needed: 'moderate_support',
        goal_achievement: 'emerging',
      }),
    })
  }

  async function linkStrategyToIepGoal(strategyItem, iepGoalId) {
    const sourceType =
      strategyItem._pool === 'repository' || strategyItem.status === 'approved' ? 'repository' : 'candidate'
    await apiFetch(`/api/v1/reports/${clinicalReportId}/iep/goals/${iepGoalId}/strategies`, {
      method: 'POST',
      body: JSON.stringify({
        strategy_id: strategyItem.id,
        strategy_source_type: sourceType,
      }),
    })
  }

  async function beginStrategyStep(goal, domainKey) {
    setCreatedGoal(goal)
    setSelectedStrategies([])
    await loadStrategyOptions(domainKey || form.domain)
    setWizardStep('strategy')
    setMsg('')
  }

  async function finishStrategyStep() {
    if (!createdGoal?.iep_goal_id) {
      setMsg('Goal was not saved — go back and try again.')
      return
    }
    if (!selectedStrategies.length && form.strategy_label.trim().length < 3) {
      setMsg('Choose at least one strategy or add a custom strategy name.')
      return
    }
    setBusy(true)
    setMsg('')
    try {
      const linked = []
      for (const sid of selectedStrategies) {
        const item = strategyOptions.find((s) => s.id === sid)
        if (item) {
          await linkStrategyToIepGoal(item, createdGoal.iep_goal_id)
          linked.push(item)
        }
      }
      if (form.strategy_label.trim().length >= 3) {
        const custom = await apiFetch(
          `/api/v1/reports/${clinicalReportId}/iep/goals/${createdGoal.iep_goal_id}/strategy-candidates`,
          {
            method: 'POST',
            body: JSON.stringify({
              label: form.strategy_label.trim(),
              how_to_use: form.strategy_steps.filter(Boolean).join('\n'),
              strategy_steps: form.strategy_steps.filter(Boolean),
              domain_key: form.domain,
            }),
          },
        )
        linked.push(custom)
      }
      onCreated?.({ goal: createdGoal, strategies: linked })
      onClose?.()
    } catch (err) {
      setMsg(err.message || 'Could not link strategies')
    } finally {
      setBusy(false)
    }
  }

  function toggleStrategy(id) {
    setSelectedStrategies((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  const loadTemplates = useCallback(async () => {
    if (!caseId) return
    setTemplatesLoading(true)
    try {
      const params = new URLSearchParams({ kind: repositoryKind })
      if (searchQuery.trim()) params.set('q', searchQuery.trim())
      if (domainFilter) params.set('domain', domainFilter)
      const data = await apiFetch(`/api/v1/cases/${caseId}/clinical/repository-search?${params}`)
      setTemplates(data.items || [])
    } catch {
      setTemplates([])
    } finally {
      setTemplatesLoading(false)
    }
  }, [caseId, repositoryKind, searchQuery, domainFilter])

  useEffect(() => {
    if (tab === 'templates') loadTemplates()
  }, [tab, loadTemplates])

  const statementPreview = useMemo(() => {
    if (form.goal_statement.trim()) return form.goal_statement.trim()
    if (form.label.trim()) {
      return `By the end of the IEP period, ${childName} will ${form.label.trim().toLowerCase()}.`
    }
    return 'Select a template or write a goal statement to see the preview.'
  }, [form.goal_statement, form.label, childName])

  async function linkStrategyToGoal(strategyItem, goalRef) {
    if (reportType === 'iep' && clinicalReportId && goalRef?.iep_goal_id) {
      await apiFetch(`/api/v1/reports/${clinicalReportId}/iep/goals/${goalRef.iep_goal_id}/strategies`, {
        method: 'POST',
        body: JSON.stringify({
          strategy_id: strategyItem.id,
          strategy_source_type: strategyItem._pool === 'repository' ? 'repository' : 'candidate',
        }),
      })
      return
    }
    const strategyUrl =
      reportType === 'iep' && clinicalReportId
        ? `/api/v1/reports/${clinicalReportId}/observation/strategy-candidates`
        : `/api/v1/cases/${caseId}/strategy-candidates`
    await apiFetch(strategyUrl, {
      method: 'POST',
      body: JSON.stringify({
        label: strategyItem.label,
        description: strategyItem.description || strategyItem.how_to_use,
        linked_goal_card_id: goalRef?.goal_card_id || goalRef?.id,
        source: 'therapist',
        source_daily_log_id: logId || undefined,
      }),
    })
  }

  async function addGoalPayload(payload, strategies = []) {
    if (reportType === 'iep' && clinicalReportId) {
      const goal = await apiFetch(`/api/v1/reports/${clinicalReportId}/iep/goals`, {
        method: 'POST',
        body: JSON.stringify({
          goal_source_id: payload.source_id || undefined,
          source_type: payload.source_type || 'manual',
          title: payload.label,
          goal_statement: payload.goal_statement || payload.label,
          domain: payload.domain_key || payload.domain || 'general',
          baseline_current_state: payload.baseline_state || '',
          desired_state: payload.desired_state || '',
          participation: 'emerging_participation',
          independence_support_needed: 'moderate_support',
          goal_achievement: 'emerging',
        }),
      })
      for (const s of strategies) {
        if (s?.id && goal?.iep_goal_id) {
          await apiFetch(`/api/v1/reports/${clinicalReportId}/iep/goals/${goal.iep_goal_id}/strategies`, {
            method: 'POST',
            body: JSON.stringify({ strategy_id: s.id, strategy_source_type: 'repository' }),
          }).catch(() => {})
        }
      }
      return { goal, strategies }
    }
    const goalUrl =
      clinicalReportId && reportType === 'observation'
        ? `/api/v1/reports/${clinicalReportId}/observation/goal-candidates`
        : `/api/v1/cases/${caseId}/goal-candidates`
    const goal = await apiFetch(goalUrl, {
      method: 'POST',
      body: JSON.stringify({
        label: payload.label,
        goal_statement: payload.goal_statement || payload.label,
        rationale: payload.supports || '',
        baseline_note: payload.baseline_state,
        desired_direction: payload.desired_state,
        domain_key: payload.domain_key || payload.domain,
        source: 'therapist',
        source_daily_log_id: logId || undefined,
        source_session_id: sessionId || undefined,
        goal_use: captureGoalUse ? form.goal_use : undefined,
      }),
    })
    const linked = []
    for (const s of strategies.length ? strategies : previewStrategies) {
      const strat = await apiFetch(
        clinicalReportId && reportType === 'observation'
          ? `/api/v1/reports/${clinicalReportId}/observation/strategy-candidates`
          : `/api/v1/cases/${caseId}/strategy-candidates`,
        {
          method: 'POST',
          body: JSON.stringify({
            label: s.label || form.strategy_label,
            description: s.description || form.strategy_steps.filter(Boolean).join('\n'),
            strategy_steps: form.strategy_steps.filter(Boolean),
            linked_goal_card_id: goal.id || goal.goal_card_id,
            source: 'therapist',
            source_daily_log_id: logId || undefined,
            strategy_type: captureStrategyType ? form.strategy_type : undefined,
          }),
        },
      )
      linked.push(strat)
    }
    if (!strategies.length && form.strategy_label.trim().length >= 3) {
      const strat = await apiFetch(
        clinicalReportId && reportType === 'observation'
          ? `/api/v1/reports/${clinicalReportId}/observation/strategy-candidates`
          : `/api/v1/cases/${caseId}/strategy-candidates`,
        {
          method: 'POST',
          body: JSON.stringify({
            label: form.strategy_label.trim(),
            description: form.strategy_steps.filter(Boolean).join('\n'),
            strategy_steps: form.strategy_steps.filter(Boolean),
            linked_goal_card_id: goal.id || goal.goal_card_id,
            source: 'therapist',
            source_daily_log_id: logId || undefined,
            strategy_type: captureStrategyType ? form.strategy_type : undefined,
          }),
        },
      )
      linked.push(strat)
    }
    return { goal, strategies: linked }
  }

  async function handleAddTemplate(item) {
    setBusy(true)
    setMsg('')
    try {
      if (repositoryKind === 'strategies') {
        const goalRef = preSelectedGoal
        if (!goalRef) {
          setMsg('Select a goal first, then add a linked strategy.')
          return
        }
        await linkStrategyToGoal(item, goalRef)
        onCreated?.({ strategy: item, goal: goalRef })
        onClose?.()
        return
      }
      const payload = {
        label: item.label,
        goal_statement: item.goal_statement || item.label,
        domain_key: item.domain_key || domainFilter || 'general',
        baseline_state: item.baseline_state || item.baseline_note || '',
        desired_state: item.desired_state || item.desired_direction || '',
        source_id: item.id,
        source_type: item._pool === 'repository_goals' ? 'repository' : 'observation_candidate',
      }
      if (wizardIep && clinicalReportId) {
        const goal = await createIepGoalRecord(payload)
        await beginStrategyStep(goal, payload.domain_key)
        return
      }
      const result = await addGoalPayload(payload)
      onCreated?.(result)
      onClose?.()
    } catch (err) {
      setMsg(err.message || 'Could not add from template')
    } finally {
      setBusy(false)
    }
  }

  async function handleCustomSubmit(e) {
    e.preventDefault()
    if (standaloneStrategy && !preSelectedGoal) {
      if (form.strategy_label.trim().length < 3) {
        setMsg('Add a strategy name with at least a few words.')
        return
      }
      setBusy(true)
      setMsg('')
      try {
        const created = await apiFetch(`/api/v1/cases/${caseId}/strategy-candidates`, {
          method: 'POST',
          body: JSON.stringify({
            label: form.strategy_label.trim(),
            strategy_steps: form.strategy_steps.filter(Boolean),
            how_to_use: form.strategy_steps.filter(Boolean).join('\n'),
            domain_key: form.domain,
            source: 'therapist',
            source_daily_log_id: logId || undefined,
            strategy_type: captureStrategyType ? form.strategy_type : undefined,
          }),
        })
        onCreated?.({ strategy: created })
        onClose?.()
      } catch (err) {
        setMsg(err.message || 'Could not save strategy')
      } finally {
        setBusy(false)
      }
      return
    }
    if (wizardStep === 'strategy') {
      e.preventDefault()
      await finishStrategyStep()
      return
    }
    if (form.label.trim().length < 3) {
      setMsg('Add a goal title with at least a few words.')
      return
    }
    if (!strategyOnly && reportType !== 'iep' && form.strategy_label.trim().length < 3 && previewStrategies.length === 0) {
      setMsg('Link at least one strategy to this goal.')
      return
    }
    setBusy(true)
    setMsg('')
    try {
      const payload = {
        label: form.label.trim(),
        goal_statement: form.goal_statement.trim() || form.label.trim(),
        domain: form.domain,
        baseline_state: form.baseline_state,
        desired_state: form.desired_state,
        supports: form.supports,
      }
      if (wizardIep && clinicalReportId) {
        const goal = await createIepGoalRecord(payload)
        await beginStrategyStep(goal, form.domain)
        return
      }
      const result = await addGoalPayload(payload)
      onCreated?.(result)
      onClose?.()
    } catch (err) {
      setMsg(err.message || 'Could not save goal')
    } finally {
      setBusy(false)
    }
  }

  async function handleGenerateAi() {
    if (!clinicalReportId) {
      setMsg('Save the report draft first, then generate AI suggestions.')
      return
    }
    setAiLoading(true)
    setMsg('')
    try {
      const data = await apiFetch(`/api/v1/reports/${clinicalReportId}/clinical/generate-goal-strategy-drafts`, {
        method: 'POST',
      })
      setAiDrafts(data.drafts || [])
      if (!data.drafts?.length) setMsg('No drafts yet — add observation context or repository goals first.')
    } catch (err) {
      setMsg(err.message || 'Could not generate drafts')
    } finally {
      setAiLoading(false)
    }
  }

  async function handleAddAiDraft(draft) {
    setBusy(true)
    try {
      const result = await addGoalPayload(draft.goal, draft.strategies || [])
      onCreated?.(result)
      onClose?.()
    } catch (err) {
      setMsg(err.message || 'Could not add AI draft')
    } finally {
      setBusy(false)
    }
  }

  function selectTemplateForCustom(item) {
    setForm({
      ...form,
      label: item.label,
      goal_statement: item.goal_statement || item.label,
      baseline_state: item.baseline_state || item.baseline_note || '',
      desired_state: item.desired_state || item.desired_direction || '',
      domain: item.domain_key || domainFilter || form.domain,
    })
    setTab('custom')
  }

  return (
    <div className="sg-modal-root clinical-report-ui" role="dialog" aria-modal="true" aria-labelledby="sg-modal-title">
      <div className="sg-modal">
        <header className="sg-modal__head">
          <div>
            <h2 id="sg-modal-title" className="sg-modal__title">
              {wizardStep === 'strategy'
                ? 'Link strategies to goal'
                : standaloneStrategy && !preSelectedGoal
                  ? 'Create strategy'
                  : strategyOnly
                    ? 'Add linked strategy'
                    : 'Create student goal'}
            </h2>
            <p className="sg-modal__subtitle">
              {wizardStep === 'strategy'
                ? createdGoal?.title || createdGoal?.goal_statement || 'New goal'
                : `Drafting for: ${childName}`}
            </p>
          </div>
          <button type="button" className="sg-modal__close" aria-label="Close" onClick={onClose}>
            ×
          </button>
        </header>

        <div className="sg-modal__body">
          <div className="sg-modal__main">
            {wizardStep === 'strategy' ? (
              <>
                <p className="sg-hint">Choose existing strategies or add a custom one. Selected strategies link to this goal.</p>
                <ul className="sg-template-list">
                  {strategyOptions.map((item) => (
                    <li key={`${item.id}-${item.label}`} className="sg-template-item">
                      <label className="flex items-start gap-3 cursor-pointer w-full">
                        <input
                          type="checkbox"
                          className="mt-1"
                          checked={selectedStrategies.includes(item.id)}
                          onChange={() => toggleStrategy(item.id)}
                        />
                        <span>
                          <p className="sg-template-item__title m-0">{item.label}</p>
                          <p className="sg-template-item__desc m-0">
                            {item.description || item.how_to_use || item.when_to_use || '—'}
                          </p>
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
                {!strategyOptions.length ? (
                  <p className="sg-hint">No repository strategies yet — add a custom strategy below.</p>
                ) : null}
                <label className="sg-field">
                  <span className="sg-field__label">Custom strategy (optional)</span>
                  <input
                    value={form.strategy_label}
                    onChange={(e) => setForm({ ...form, strategy_label: e.target.value })}
                    placeholder="Visual countdown"
                  />
                </label>
                {[0, 1, 2].map((i) => (
                  <label key={i} className="sg-field">
                    <span className="sg-field__label">Step {i + 1}</span>
                    <input
                      value={form.strategy_steps[i]}
                      onChange={(e) => {
                        const next = [...form.strategy_steps]
                        next[i] = e.target.value
                        setForm({ ...form, strategy_steps: next })
                      }}
                    />
                  </label>
                ))}
                {msg ? <p className="sg-error">{msg}</p> : null}
                <div className="flex gap-2">
                  <button type="button" className="cr-btn" disabled={busy} onClick={() => setWizardStep('goal')}>
                    Back
                  </button>
                  <button type="button" className="cr-btn cr-btn--primary flex-1" disabled={busy} onClick={finishStrategyStep}>
                    {busy ? 'Saving…' : 'Save goal & strategies'}
                  </button>
                </div>
              </>
            ) : (
              <>
            <div className="sg-tabs" role="tablist">
              {GOAL_MODAL_TABS.map((t) => {
                if (standaloneStrategy && !preSelectedGoal) return null
                if (t.id === 'ai' && !AI_ENABLED && !clinicalReportId) return null
                return (
                  <button
                    key={t.id}
                    type="button"
                    role="tab"
                    aria-selected={tab === t.id}
                    className={`sg-tab${tab === t.id ? ' sg-tab--active' : ''}`}
                    onClick={() => setTab(t.id)}
                  >
                    {t.label}
                  </button>
                )
              })}
            </div>

            {tab === 'templates' ? (
              repositoryKind === 'goals' && !strategyOnly ? (
                <GoalTemplateLibrary
                  caseId={caseId}
                  onUseTemplate={handleAddTemplate}
                  onPreview={(item) => selectTemplateForCustom(item)}
                  onSelectForCustom={selectTemplateForCustom}
                />
              ) : (
              <>
                <div className="sg-search-row">
                  <input
                    type="search"
                    className="sg-search-input"
                    placeholder="Search goal templates…"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                  <div className="sg-kind-toggle" role="group" aria-label="Repository kind">
                    <button
                      type="button"
                      className={repositoryKind === 'goals' ? 'is-active' : ''}
                      onClick={() => setRepositoryKind('goals')}
                    >
                      Goals
                    </button>
                    <button
                      type="button"
                      className={repositoryKind === 'strategies' ? 'is-active' : ''}
                      onClick={() => setRepositoryKind('strategies')}
                    >
                      Strategies
                    </button>
                  </div>
                </div>
                <div className="sg-chips">
                  {GOAL_MODAL_DOMAIN_CHIPS.map((c) => (
                    <button
                      key={c.id}
                      type="button"
                      className={`sg-chip${domainFilter === c.id ? ' sg-chip--active' : ''}`}
                      onClick={() => setDomainFilter(domainFilter === c.id ? '' : c.id)}
                    >
                      {c.label}
                    </button>
                  ))}
                </div>
                {templatesLoading ? <p className="sg-hint">Searching repository…</p> : null}
                <ul className="sg-template-list">
                  {templates.map((item) => (
                    <li key={`${item.id || item.label}-${item._pool || ''}`} className="sg-template-item">
                      <div>
                        <p className="sg-template-item__title">{item.label}</p>
                        <p className="sg-template-item__desc">
                          {item.goal_statement || item.description || item.rationale || item.how_to_use || '—'}
                        </p>
                      </div>
                      <div className="flex flex-col gap-1 shrink-0">
                        <button
                          type="button"
                          className="cr-btn cr-btn--forest text-xs"
                          disabled={busy}
                          onClick={() => handleAddTemplate(item)}
                        >
                          {repositoryKind === 'strategies' ? 'Add' : 'Add'}
                        </button>
                        {repositoryKind === 'goals' ? (
                          <button type="button" className="cr-btn text-xs" disabled={busy} onClick={() => selectTemplateForCustom(item)}>
                            Select
                          </button>
                        ) : null}
                      </div>
                    </li>
                  ))}
                </ul>
                {!templatesLoading && templates.length === 0 ? (
                  <p className="sg-hint">No templates match — try another domain or search term.</p>
                ) : null}
              </>
              )
            ) : null}

            {tab === 'custom' ? (
              <form onSubmit={handleCustomSubmit}>
                {!standaloneStrategy || preSelectedGoal ? (
                  <label className="sg-field">
                    <span className="sg-field__label">Goal title</span>
                    <input
                      value={form.label}
                      onChange={(e) => setForm({ ...form, label: e.target.value })}
                      placeholder="Social interaction: initiation & maintenance"
                    />
                  </label>
                ) : null}
                <span className="sg-field__label">Domain</span>
                <div className="sg-domain-grid">
                  {GOAL_MODAL_DOMAIN_CHIPS.map((c) => (
                    <button
                      key={c.id}
                      type="button"
                      className={`sg-domain-tile${form.domain === c.id ? ' sg-domain-tile--active' : ''}`}
                      onClick={() => setForm({ ...form, domain: c.id })}
                    >
                      {c.label}
                    </button>
                  ))}
                </div>
                <label className="sg-field">
                  <span className="sg-field__label">Goal statement (IEP language)</span>
                  <textarea
                    rows={4}
                    value={form.goal_statement}
                    onChange={(e) => setForm({ ...form, goal_statement: e.target.value })}
                    placeholder="By the end of the IEP period…"
                    disabled={standaloneStrategy && !preSelectedGoal}
                  />
                </label>
                {!standaloneStrategy || preSelectedGoal ? (
                  <label className="sg-field">
                    <span className="sg-field__label">Supports</span>
                    <input
                      value={form.supports}
                      onChange={(e) => setForm({ ...form, supports: e.target.value })}
                      placeholder="Verbal initiation (greeting or question)"
                    />
                  </label>
                ) : null}
                {captureGoalUse && !standaloneStrategy ? (
                  <fieldset className="sg-field">
                    <legend className="sg-field__label">Goal use</legend>
                    <GoalUseCards
                      value={form.goal_use}
                      onChange={(goal_use) => setForm({ ...form, goal_use })}
                      disabled={busy}
                    />
                  </fieldset>
                ) : null}
                {captureStrategyType && (standaloneStrategy || form.strategy_label || preSelectedGoal) ? (
                  <fieldset className="sg-field">
                    <legend className="sg-field__label">Strategy type</legend>
                    <div className="sg-radio-row">
                      {STRATEGY_TYPE_OPTIONS.map((opt) => (
                        <label key={opt.id} className="sg-radio">
                          <input
                            type="radio"
                            name="strategy_type"
                            checked={form.strategy_type === opt.id}
                            onChange={() => setForm({ ...form, strategy_type: opt.id })}
                          />
                          {opt.label}
                        </label>
                      ))}
                    </div>
                  </fieldset>
                ) : null}
                {(standaloneStrategy && !preSelectedGoal) || (!strategyOnly && reportType !== 'iep') ? (
                  <>
                    <label className="sg-field">
                      <span className="sg-field__label">
                        {standaloneStrategy && !preSelectedGoal ? 'Strategy name' : 'Linked strategy (required)'}
                      </span>
                      <input
                        value={form.strategy_label}
                        onChange={(e) => setForm({ ...form, strategy_label: e.target.value })}
                        placeholder="Visual countdown"
                      />
                    </label>
                    {[0, 1, 2].map((i) => (
                      <label key={i} className="sg-field">
                        <span className="sg-field__label">Step {i + 1}</span>
                        <input
                          value={form.strategy_steps[i]}
                          onChange={(e) => {
                            const next = [...form.strategy_steps]
                            next[i] = e.target.value
                            setForm({ ...form, strategy_steps: next })
                          }}
                        />
                      </label>
                    ))}
                  </>
                ) : null}
                {msg ? <p className="sg-error">{msg}</p> : null}
                <button type="submit" className="cr-btn cr-btn--primary w-full" disabled={busy}>
                  {busy
                    ? 'Saving…'
                    : wizardIep
                      ? 'Continue to strategies'
                      : standaloneStrategy && !preSelectedGoal
                        ? 'Create strategy'
                        : strategyOnly
                          ? 'Add strategy'
                          : 'Add goal & strategy'}
                </button>
              </form>
            ) : null}

            {tab === 'ai' ? (
              <>
                <p className="sg-hint">Generate draft goals and linked strategies from observation and repository context.</p>
                <button type="button" className="cr-btn cr-btn--forest mb-4" disabled={aiLoading || !clinicalReportId} onClick={handleGenerateAi}>
                  {aiLoading ? 'Generating…' : 'Generate suggestions'}
                </button>
                <ul className="sg-template-list">
                  {aiDrafts.map((draft) => (
                    <li key={draft.goal.label} className="sg-template-item">
                      <div>
                        <p className="sg-template-item__title">{draft.goal.label}</p>
                        <p className="sg-template-item__desc">{draft.goal.goal_statement}</p>
                        <p className="sg-template-item__desc">{draft.strategies?.length || 0} linked strategies</p>
                      </div>
                      <button type="button" className="cr-btn cr-btn--forest text-xs" disabled={busy} onClick={() => handleAddAiDraft(draft)}>
                        Add
                      </button>
                    </li>
                  ))}
                </ul>
                {msg ? <p className="sg-error">{msg}</p> : null}
              </>
            ) : null}
              </>
            )}
          </div>

          <aside className="sg-modal__rail" aria-label="Goal preview">
            <p className="sg-rail__badge">● Drafting</p>
            <div className="sg-rail__block">
              <p className="sg-rail__block-title">Statement summary</p>
              <p className="sg-rail__summary">{statementPreview}</p>
            </div>
            <div className="sg-rail__block">
              <p className="sg-rail__block-title">Parent-safe preview</p>
              <p className="sg-rail__summary">
                {form.label.trim()
                  ? `Your child is working on: ${form.label}. ${form.desired_state || form.supports || ''}`
                  : 'Parent-friendly wording appears after you draft a goal statement.'}
              </p>
            </div>
            <div className="sg-rail__block">
              <p className="sg-rail__block-title">Active strategies ({previewStrategies.length || form.strategy_label ? 1 : 0})</p>
              {previewStrategies.map((s) => (
                <p key={s.label} className="sg-strategy-line">
                  <span aria-hidden>✓</span> {s.label}
                </p>
              ))}
              {form.strategy_label ? (
                <p className="sg-strategy-line">
                  <span aria-hidden>✓</span> {form.strategy_label}
                </p>
              ) : null}
              {!previewStrategies.length && !form.strategy_label ? (
                <p className="sg-hint">Strategies appear here when linked.</p>
              ) : null}
            </div>
            <div className="sg-rail__block">
              <p className="sg-rail__block-title">Clinical environment</p>
              <p className="text-xs m-0">
                <strong>Setting:</strong> General classroom
              </p>
              <p className="text-xs m-0 mt-1">
                <strong>Supports:</strong> From case accommodations
              </p>
            </div>
          </aside>
        </div>

        {tab === 'templates' && msg ? (
          <footer className="sg-modal__foot">
            <p className="sg-error m-0">{msg}</p>
          </footer>
        ) : null}
      </div>
    </div>
  )
}
