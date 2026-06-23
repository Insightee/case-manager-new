import { STRATEGY_FEEDBACK_OPTIONS, emptyStrategyRow, goalSessionStatus } from '../../../lib/clinicalScoring.js'
import { matchRecommendedStrategies } from '../../../lib/coreClinicalTaxonomy.js'
import { ClinicalTaxonomyPicker } from '../ClinicalTaxonomyPicker.jsx'
import { MeasurementCriteriaSelect } from '../MeasurementCriteriaSelect.jsx'
import { MeasurementHelpTicker } from './ScoreHelpButton.jsx'
import { strategyNeedsAlternatives } from './SessionLogStrategyRow.jsx'
import { StrategyAlternativesPanel } from './StrategyAlternativesPanel.jsx'

const FEEDBACK_CLASS = {
  HELPFUL: 'is-active--helpful',
  PARTLY_HELPFUL: 'is-active--partly',
  NOT_HELPFUL: 'is-active--negative',
  CHILD_REJECTED: 'is-active--negative',
  NEEDS_ADAPTATION: 'is-active--adapt',
}

function stepsFromRepo(item) {
  const parts = String(item?.how_to_use || '')
    .split(/\n+/)
    .map((s) => s.trim())
    .filter(Boolean)
  return [parts[0] || '', parts[1] || '', parts[2] || '']
}

function normalizeSteps(raw) {
  const arr = Array.isArray(raw) ? raw : []
  return [arr[0] || '', arr[1] || '', arr[2] || '']
}

export function GoalSessionCard({
  goal,
  index,
  expanded,
  onToggle,
  readOnly,
  repo,
  onUpdate,
  caseId,
  environment,
  onPickStrategy,
  showStrategyPanel,
  onToggleStrategyPanel,
  onCreateStrategy,
  otherCaseGoals = [],
  onSelectCaseGoal,
  cardRef,
}) {
  const status = goalSessionStatus(goal)
  const strategies = goal.strategies || []
  const primary = strategies[0] || null
  const steps = normalizeSteps(primary?.strategy_steps)
  const shortTitle = goal.goal_label?.trim() || `Goal ${index + 1}`
  const recommended = matchRecommendedStrategies(repo?.strategies || [], goal)

  function updatePrimary(patch) {
    const base = primary || emptyStrategyRow(goal.goal_card_id)
    const next = strategies.length
      ? strategies.map((s, i) => (i === 0 ? { ...base, ...s, ...patch } : s))
      : [{ ...base, ...patch }]
    onUpdate({ strategies: next })
  }

  function setFeedback(feedbackId) {
    updatePrimary({ strategy_feedback: feedbackId === primary?.strategy_feedback ? null : feedbackId })
  }

  function setShortNote(note) {
    updatePrimary({ short_note: note })
  }

  function setStep(i, val) {
    const next = [...steps]
    next[i] = val
    updatePrimary({ strategy_steps: next })
  }

  function applyStrategy(item) {
    onPickStrategy({
      ...item,
      strategy_steps: stepsFromRepo(item),
      expected_outcome: item.when_to_use || '',
    })
  }

  const showAlternatives = strategies.some(strategyNeedsAlternatives)

  function markCompleteForToday() {
    onUpdate({ marked_complete_today: !goal.marked_complete_today })
  }

  return (
    <article ref={cardRef} className={`sl-goal-accordion${expanded ? ' is-expanded' : ''}`}>
      <button type="button" className="sl-goal-accordion__header" onClick={onToggle} aria-expanded={expanded}>
        <span className="sl-goal-accordion__num">{index + 1}</span>
        <span className="sl-goal-accordion__title-wrap">
          <p className="sl-goal-accordion__title">{shortTitle}</p>
          {status.worked ? (
            <span className="sl-goal-accordion__worked-badge">Worked on this session</span>
          ) : null}
        </span>
        {status.label === 'add' ? (
          <span className="sl-goal-accordion__add-btn" aria-hidden="true">
            +
          </span>
        ) : (
          <span className={`sl-goal-accordion__status sl-goal-accordion__status--${status.tone}`}>{status.label}</span>
        )}
        <span className="sl-goal-accordion__chevron" aria-hidden="true">
          ▾
        </span>
      </button>

      {expanded ? (
        <div className="sl-goal-accordion__body">
          {goal.pending_review ? (
            <p className="sl-goal-accordion__review-badge">Under review — usable for this client while pending</p>
          ) : null}

          <label className="gs-field">
            <span className="gs-field__label">Goal title</span>
            <input
              type="text"
              disabled={readOnly}
              value={goal.goal_label || ''}
              placeholder="What are we working on today?"
              onChange={(e) => onUpdate({ goal_label: e.target.value })}
            />
          </label>

          <label className="gs-field">
            <span className="gs-field__label">Goal brief</span>
            <textarea
              rows={2}
              disabled={readOnly}
              value={goal.goal_description || ''}
              placeholder="Baseline, desired state, or why this matters today…"
              onChange={(e) => onUpdate({ goal_description: e.target.value })}
            />
          </label>

          <ClinicalTaxonomyPicker
            domains={goal.core_domains || []}
            environments={goal.core_environments || []}
            disabled={readOnly}
            onDomainsChange={(core_domains) => onUpdate({ core_domains })}
            onEnvironmentsChange={(core_environments) => onUpdate({ core_environments })}
          />

          <section className="sl-strategy-block">
            {!readOnly && !primary?.strategy_label ? (
              <button type="button" className="gs-btn gs-btn--secondary sl-strategy-block__add-full" onClick={onToggleStrategyPanel}>
                + Add strategy
              </button>
            ) : null}

            {primary?.strategy_label || readOnly ? (
              <div className="sl-strategy-block__head">
                <p className="sl-v2-section-label">Strategy this session</p>
                {!readOnly && primary?.strategy_label ? (
                  <button type="button" className="sl-strategy-block__change" onClick={onToggleStrategyPanel}>
                    Change
                  </button>
                ) : null}
              </div>
            ) : null}

            {showStrategyPanel && !readOnly ? (
              <div className="sl-strategy-panel">
                {recommended.length ? (
                  <>
                    <p className="sl-strategy-panel__subtitle">Recommended for selected domains</p>
                    <div className="sl-repo-picker">
                      {recommended.map((s) => (
                        <button
                          key={`rec-${s.strategy_id}-${s.label}`}
                          type="button"
                          className="sl-repo-picker__row sl-repo-picker__row--rec"
                          onClick={() => applyStrategy(s)}
                        >
                          <span>{s.label}</span>
                          <span className="sl-repo-picker__badge">{s.category || 'Recommended'}</span>
                        </button>
                      ))}
                    </div>
                  </>
                ) : null}
                {(repo?.strategies || []).length ? (
                  <>
                    <p className="sl-strategy-panel__subtitle">All strategies</p>
                    <div className="sl-repo-picker">
                      {(repo?.strategies || []).map((s) => (
                        <button
                          key={`${s.strategy_id}-${s.label}`}
                          type="button"
                          className="sl-repo-picker__row"
                          onClick={() => applyStrategy(s)}
                        >
                          <span>{s.label}</span>
                          <span className="sl-repo-picker__badge">{s.category || s.source}</span>
                        </button>
                      ))}
                    </div>
                  </>
                ) : (
                  <p className="gs-muted">No strategies in library yet.</p>
                )}
                <button type="button" className="sl-v2-btn-add" onClick={onCreateStrategy}>
                  Create custom strategy
                </button>
              </div>
            ) : null}

            {primary?.strategy_label ? (
              <div className="sl-strategy-detail">
                <p className="sl-strategy-detail__name">{primary.strategy_label}</p>
                <div className="sl-strategy-steps">
                  <p className="sl-strategy-steps__label">Steps (activity for this session)</p>
                  {[0, 1, 2].map((i) => (
                    <label key={i} className="sl-strategy-step-row">
                      <span className="sl-strategy-step-row__num">{i + 1}</span>
                      <input
                        type="text"
                        disabled={readOnly}
                        placeholder={`Step ${i + 1}…`}
                        value={steps[i]}
                        onChange={(e) => setStep(i, e.target.value)}
                      />
                    </label>
                  ))}
                </div>
                <label className="gs-field">
                  <span className="gs-field__label">Expected outcome</span>
                  <input
                    type="text"
                    disabled={readOnly}
                    value={primary.expected_outcome || ''}
                    placeholder="What success looks like in this session…"
                    onChange={(e) => updatePrimary({ expected_outcome: e.target.value })}
                  />
                </label>
                <div>
                  <p className="sl-v2-section-label">Strategy feedback this session</p>
                  <div className="sl-strategy-feedback" role="group" aria-label="Strategy feedback">
                    {STRATEGY_FEEDBACK_OPTIONS.map((opt) => (
                      <button
                        key={opt.id}
                        type="button"
                        disabled={readOnly}
                        className={`sl-strategy-feedback__btn${
                          primary?.strategy_feedback === opt.id ? ` ${FEEDBACK_CLASS[opt.id] || ''}` : ''
                        }`}
                        aria-pressed={primary?.strategy_feedback === opt.id}
                        onClick={() => setFeedback(opt.id)}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <p className="gs-muted">Choose a strategy to document steps and session feedback.</p>
            )}
          </section>

          <div className="sl-measurement-block">
            <div className="sl-measurement-block__head">
              <p className="sl-v2-section-label">Goal achievement</p>
              <MeasurementHelpTicker />
            </div>
            <MeasurementCriteriaSelect
              compact
              readOnly={readOnly}
              values={{
                participation: goal.participation || '',
                independence_support_needed: goal.independence_support_needed || '',
                goal_achievement: goal.goal_achievement || '',
              }}
              onChange={(next) =>
                onUpdate({
                  schema_version: 2,
                  participation: next.participation || null,
                  independence_support_needed: next.independence_support_needed || null,
                  goal_achievement: next.goal_achievement || null,
                })
              }
            />
          </div>

          <label className="gs-field sl-short-note-field">
            <span className="gs-field__label">Short note (shared tone with family preview)</span>
            <textarea
              rows={3}
              disabled={readOnly}
              placeholder="What helped? What changed? What should we try next?"
              value={primary?.short_note || goal.measurement_note || ''}
              onChange={(e) => setShortNote(e.target.value)}
            />
          </label>

          {!readOnly ? (
            <button
              type="button"
              className={`gs-btn sl-goal-mark-complete${goal.marked_complete_today ? ' is-done' : ''}`}
              onClick={markCompleteForToday}
            >
              {goal.marked_complete_today ? '✓ Marked complete for today' : 'Mark completed for today'}
            </button>
          ) : goal.marked_complete_today ? (
            <p className="sl-goal-mark-complete sl-goal-mark-complete--readonly">✓ Completed for today</p>
          ) : null}

          {otherCaseGoals.length ? (
            <section className="sl-case-goals-rail">
              <p className="sl-v2-section-label">Other goals from IEP / case plan</p>
              <div className="sl-case-goals-rail__list">
                {otherCaseGoals.map((g) => (
                  <button
                    key={g.goal_card_id || g.label}
                    type="button"
                    className="sl-case-goals-rail__item"
                    disabled={readOnly}
                    onClick={() => onSelectCaseGoal?.(g)}
                  >
                    <strong>{g.label}</strong>
                    {g.goal_brief ? (
                      <span>{g.goal_brief.length > 80 ? `${g.goal_brief.slice(0, 80)}…` : g.goal_brief}</span>
                    ) : null}
                  </button>
                ))}
              </div>
            </section>
          ) : null}

          {showAlternatives && goal.goal_card_id ? (
            <StrategyAlternativesPanel
              caseId={caseId}
              goalCardId={goal.goal_card_id}
              environment={environment}
              excludeStrategyIds={strategies.map((s) => s.strategy_id).filter(Boolean)}
              onTryStrategy={(row) => onUpdate({ strategies: [...strategies, row] })}
            />
          ) : null}
        </div>
      ) : null}
    </article>
  )
}
