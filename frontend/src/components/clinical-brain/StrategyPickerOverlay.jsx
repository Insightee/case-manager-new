import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { coreDomainLabel } from '../../lib/coreClinicalTaxonomy.js'
import { enrichStrategyPoolFromApi, strategySelectionToExtension } from '../../lib/clinicalBrainMockData.js'
import { applyClinicalFilters, EMPTY_FILTERS } from '../../lib/clinicalBrainFilters.js'
import { EVIDENCE_LABELS } from '../../lib/clinicalBrainCopy.js'
import {
  feedbackBadgeLabel,
  feedbackMapByStrategy,
  fetchStrategyFeedback,
  saveStrategyFeedback,
} from '../../lib/clinicalBrainFeedbackApi.js'
import { PROGRESS_SUPPORT_NEEDED_OPTIONS, STRATEGY_USE_STATUS_OPTIONS } from '../../lib/clinicalEvidenceFields.js'
import { STRATEGY_FEEDBACK_OPTIONS } from '../../lib/clinicalScoring.js'
import { ClinicalBrainFilterOverlay } from './ClinicalBrainFilterOverlay.jsx'
import '../../styles/clinical-brain.css'

const PICKER_TABS = [
  { id: 'recommended', label: 'Recommended' },
  { id: 'recent', label: 'Recently used' },
  { id: 'pool', label: 'Strategy pool' },
  { id: 'custom', label: 'Custom' },
]

const USED_AS_OPTIONS = [
  { id: 'used_as_planned', label: 'Used as planned' },
  { id: 'adapted', label: 'Adapted' },
]

export function StrategyPickerOverlay({
  open,
  onClose,
  caseId,
  goalCardId,
  goalLabel,
  recommended = [],
  recent = [],
  onSelect,
  onCreateCustom,
}) {
  const [tab, setTab] = useState('recommended')
  const [query, setQuery] = useState('')
  const [filters, setFilters] = useState({ ...EMPTY_FILTERS })
  const [filterOpen, setFilterOpen] = useState(false)
  const [pool, setPool] = useState([])
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState(null)
  const [outcome, setOutcome] = useState('')
  const [usedAs, setUsedAs] = useState('used_as_planned')
  const [supportLevel, setSupportLevel] = useState('')
  const [childResponse, setChildResponse] = useState('')
  const [evidenceNote, setEvidenceNote] = useState('')
  const [feedbackByStrategy, setFeedbackByStrategy] = useState(new Map())
  const [adaptTarget, setAdaptTarget] = useState(null)
  const [adaptText, setAdaptText] = useState('')
  const [feedbackBusy, setFeedbackBusy] = useState('')
  const [feedbackMsg, setFeedbackMsg] = useState('')

  const loadFeedback = useCallback(async () => {
    if (!caseId) return
    try {
      const res = await fetchStrategyFeedback(caseId, { goal_card_id: goalCardId })
      setFeedbackByStrategy(feedbackMapByStrategy(res.items || []))
    } catch {
      setFeedbackByStrategy(new Map())
    }
  }, [caseId, goalCardId])

  useEffect(() => {
    if (open) loadFeedback()
  }, [open, loadFeedback])

  async function recordFeedback(strategy, status, extra = {}) {
    if (!caseId) return
    const sid = strategy.id || strategy.strategy_id
    setFeedbackBusy(`${sid}-${status}`)
    setFeedbackMsg('')
    try {
      const row = await saveStrategyFeedback(caseId, {
        strategy_repository_item_id: sid || null,
        goal_card_id: goalCardId || null,
        recommendation_source: tab === 'recommended' ? 'library_match' : 'therapist_search',
        feedback_status: status,
        ...extra,
      })
      setFeedbackByStrategy((prev) => {
        const next = new Map(prev)
        if (sid) next.set(sid, row)
        return next
      })
      setFeedbackMsg('Saved — thank you for helping the team learn.')
      if (status === 'accepted') pickStrategy(strategy)
    } catch (err) {
      setFeedbackMsg(err.message || 'Could not save feedback right now.')
    } finally {
      setFeedbackBusy('')
      setAdaptTarget(null)
      setAdaptText('')
    }
  }

  const loadPool = useCallback(async () => {
    if (!caseId || (tab !== 'recommended' && tab !== 'pool')) return
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (query.trim()) params.set('q', query.trim())
      if (filters.domain) params.set('domain', filters.domain)
      if (filters.support_need) params.set('support_need', filters.support_need)
      if (filters.environment) params.set('environment', filters.environment)
      if (filters.support_level) params.set('support_level', filters.support_level)
      if (goalCardId) params.set('goal_card_id', String(goalCardId))
      const path =
        tab === 'recommended'
          ? `/api/v1/cases/${caseId}/strategy-pool-matches?${params}`
          : `/api/v1/cases/${caseId}/clinical/repository-search?kind=strategies&${params}`
      const data = await apiFetch(path)
      setPool(enrichStrategyPoolFromApi(data.items || []))
    } catch {
      setPool(enrichStrategyPoolFromApi([]))
    } finally {
      setLoading(false)
    }
  }, [caseId, query, filters.domain, filters.support_need, filters.environment, filters.support_level, goalCardId, tab])

  useEffect(() => {
    if (open) loadPool()
  }, [open, loadPool])

  const tabItems = useMemo(() => {
    if (tab === 'recommended' || tab === 'pool') {
      return applyClinicalFilters(pool, { ...filters, query })
    }
    if (tab === 'recent') return recent
    return []
  }, [tab, recent, pool, filters, query])

  if (!open) return null

  function pickStrategy(item) {
    setSelected(item)
    setOutcome('')
    setUsedAs('used_as_planned')
    setSupportLevel('')
    setChildResponse('')
    setEvidenceNote('')
  }

  function confirmSelection() {
    if (!selected) return
    const feedbackMap = {
      HELPFUL: 'HELPFUL',
      PARTLY_HELPFUL: 'PARTLY_HELPFUL',
      NOT_HELPFUL: 'NOT_HELPFUL',
      CHILD_REJECTED: 'CHILD_REJECTED',
      NEEDS_ADAPTATION: 'NEEDS_ADAPTATION',
    }
    const sid = selected.id || selected.strategy_id
    const fb = sid ? feedbackByStrategy.get(sid) : null
    const ext = {
      ...strategySelectionToExtension({
        used_as: usedAs === 'adapted' ? 'adapted' : 'used_as_planned',
        child_response: childResponse || null,
        evidence_note: evidenceNote,
      }),
      ...(fb?.id ? { recommendation_feedback_id: fb.id } : {}),
    }
    onSelect?.({
      ...selected,
      strategy_label: selected.label,
      strategy_feedback: feedbackMap[outcome] || null,
      clinical_extension: ext,
      support_level: supportLevel || null,
      strategy_steps: String(selected.how_to_use || '')
        .split(/\n+/)
        .slice(0, 3)
        .concat(['', '', ''])
        .slice(0, 3),
      expected_outcome: selected.purpose || selected.when_to_use || '',
      goal_card_id: goalCardId,
    })
    onClose?.()
  }

  const activeFilterCount = Object.values(filters).filter(Boolean).length

  return (
    <div className="cb-strategy-picker" role="dialog" aria-modal="true" aria-label="Strategy picker">
      <header className="cb-strategy-picker__head">
        <div className="flex items-center justify-between gap-2">
          <div>
            <h2 className="m-0 text-lg font-bold text-[#2d4a3e]">Choose strategy</h2>
            {goalLabel ? <p className="m-0 text-sm text-slate-500">For: {goalLabel}</p> : null}
          </div>
          <button type="button" className="cb-filter-sheet__close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <input
          type="search"
          className="sg-search-input mt-3"
          placeholder="Search strategies by goal, support need, or environment"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button type="button" className="cb-btn mt-2" onClick={() => setFilterOpen(true)}>
          Filters{activeFilterCount ? ` (${activeFilterCount})` : ''}
        </button>
      </header>

      <div className="cb-strategy-picker__tabs" role="tablist">
        {PICKER_TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            className={`cb-strategy-picker__tab${tab === t.id ? ' is-active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="cb-strategy-picker__body">
        {tab === 'custom' ? (
          <div>
            <p className="gs-muted">Propose a strategy tailored to this session.</p>
            <button type="button" className="cb-btn cb-btn--primary" onClick={onCreateCustom}>
              Create custom strategy
            </button>
          </div>
        ) : loading ? (
          <p className="gs-muted">Loading strategies…</p>
        ) : tabItems.length ? (
          tabItems.map((s) => (
            <article
              key={`${s.id || s.strategy_id}-${s.label}`}
              className={`cb-card mb-3${selected?.id === s.id ? ' ring-2 ring-[#416656]' : ''}`}
            >
              <div className="cb-card__head">
                <h4 className="cb-card__title">{s.label}</h4>
                {s.evidence_label ? (
                  <span className="cb-pill cb-pill--progress">
                    {EVIDENCE_LABELS[s.evidence_label] || s.evidence_label}
                  </span>
                ) : null}
              </div>
              <p className="gs-muted">{s.purpose || s.when_to_use || s.expected_outcome}</p>
              <div className="cb-card__meta">
                <span className="cb-pill cb-pill--active">
                  {coreDomainLabel(s.domain_key || s.linked_goal_domain, { short: true })}
                </span>
                {(s.environments || s.core_environments || []).slice(0, 2).map((e) => (
                  <span key={e} className="cb-pill cb-pill--muted">{e}</span>
                ))}
                {s.support_level ? <span className="cb-pill cb-pill--muted">{s.support_level}</span> : null}
              </div>
              {s.caution || s.avoid ? (
                <p className="gs-muted text-sm"><strong>Caution:</strong> {s.caution || s.avoid}</p>
              ) : null}
              {(() => {
                const sid = s.id || s.strategy_id
                const saved = sid ? feedbackByStrategy.get(sid) : null
                return (
                  <div className="mt-2">
                    {saved ? (
                      <span className="cb-pill cb-pill--progress">{feedbackBadgeLabel(saved.feedback_status)}</span>
                    ) : (
                      <div className="cb-filter-chips">
                        <button
                          type="button"
                          className="cb-filter-chip"
                          disabled={!!feedbackBusy}
                          onClick={() => recordFeedback(s, 'accepted')}
                        >
                          Helpful for this child
                        </button>
                        <button
                          type="button"
                          className="cb-filter-chip"
                          disabled={!!feedbackBusy}
                          onClick={() => setAdaptTarget(sid)}
                        >
                          Adapted for this context
                        </button>
                        <button
                          type="button"
                          className="cb-filter-chip"
                          disabled={!!feedbackBusy}
                          onClick={() => recordFeedback(s, 'not_relevant')}
                        >
                          Not a fit right now
                        </button>
                        <button
                          type="button"
                          className="cb-filter-chip"
                          disabled={!!feedbackBusy}
                          onClick={() => recordFeedback(s, 'already_tried')}
                        >
                          Tried before
                        </button>
                        <button
                          type="button"
                          className="cb-filter-chip"
                          disabled={!!feedbackBusy}
                          onClick={() => recordFeedback(s, 'needs_cm_input')}
                        >
                          Needs CM support
                        </button>
                      </div>
                    )}
                    {adaptTarget === sid ? (
                      <div className="mt-2">
                        <textarea
                          rows={2}
                          maxLength={500}
                          placeholder="How did you adapt this for today?"
                          value={adaptText}
                          onChange={(e) => setAdaptText(e.target.value)}
                        />
                        <button
                          type="button"
                          className="cb-btn cb-btn--primary mt-1"
                          onClick={() =>
                            recordFeedback(s, 'adapted', { adaptation_text: adaptText })
                          }
                        >
                          Save adaptation
                        </button>
                      </div>
                    ) : null}
                  </div>
                )
              })()}
              <button type="button" className="cb-btn cb-btn--primary mt-2" onClick={() => pickStrategy(s)}>
                Use strategy
              </button>
            </article>
          ))
        ) : (
          <p className="gs-muted">No strategies match — try another filter or create a custom one.</p>
        )}
        {feedbackMsg ? <p className="gs-muted mt-2">{feedbackMsg}</p> : null}

        {selected ? (
          <section className="cb-card mt-4">
            <h3 className="cb-section__label">Capture how it went</h3>
            <p className="sg-field__label">Outcome</p>
            <div className="cb-filter-chips mb-3">
              {STRATEGY_FEEDBACK_OPTIONS.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  className={`cb-filter-chip${outcome === opt.id ? ' is-active' : ''}`}
                  onClick={() => setOutcome(opt.id)}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            <p className="sg-field__label">Used as</p>
            <div className="cb-filter-chips mb-3">
              {USED_AS_OPTIONS.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  className={`cb-filter-chip${usedAs === opt.id ? ' is-active' : ''}`}
                  onClick={() => setUsedAs(opt.id)}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            <p className="sg-field__label">Support level</p>
            <div className="cb-filter-chips mb-3">
              {PROGRESS_SUPPORT_NEEDED_OPTIONS.filter((o) => o.id !== 'not_observed').map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  className={`cb-filter-chip${supportLevel === opt.id ? ' is-active' : ''}`}
                  onClick={() => setSupportLevel(opt.id)}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            <label className="sg-field">
              <span className="sg-field__label">Child response (optional)</span>
              <input value={childResponse} onChange={(e) => setChildResponse(e.target.value)} />
            </label>
            <label className="sg-field">
              <span className="sg-field__label">Evidence note (optional, team only)</span>
              <input value={evidenceNote} onChange={(e) => setEvidenceNote(e.target.value)} />
            </label>
          </section>
        ) : null}
      </div>

      <footer className="cb-strategy-picker__foot">
        <button type="button" className="cb-btn" onClick={onClose}>
          Cancel
        </button>
        <button
          type="button"
          className="cb-btn cb-btn--primary"
          disabled={!selected}
          onClick={confirmSelection}
        >
          Confirm strategy
        </button>
      </footer>

      <ClinicalBrainFilterOverlay
        open={filterOpen}
        onClose={() => setFilterOpen(false)}
        filters={filters}
        onChange={setFilters}
        onApply={setFilters}
        showEvidence
      />
    </div>
  )
}
