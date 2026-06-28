import { STRATEGY_FEEDBACK_OPTIONS, emptyStrategyRow, goalSessionStatus } from '../../../lib/clinicalScoring.js'
import { matchRecommendedStrategies } from '../../../lib/coreClinicalTaxonomy.js'
import {
  getClinicalExtension,
  mergeClinicalExtension,
  suggestDefaultsFromFeedback,
} from '../../../lib/clinicalEvidenceFields.js'
import { ClinicalTaxonomyPicker } from '../ClinicalTaxonomyPicker.jsx'
import { EvidenceQualityNudge, collectGoalEvidenceGaps } from '../../clinical-ui/EvidenceQualityNudge.jsx'
import { strategyNeedsAlternatives } from './SessionLogStrategyRow.jsx'
import { StrategyAlternativesPanel } from './StrategyAlternativesPanel.jsx'
import { StrategyUseTodaySection } from './StrategyUseTodaySection.jsx'
import { QuickEvidenceSection } from './QuickEvidenceSection.jsx'
import { ProgressSignalsSection } from './ProgressSignalsSection.jsx'

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
  showNudges = false,
}) {
  const status = goalSessionStatus(goal)
  const strategies = goal.strategies || []
  const primary = strategies[0] || null
  const shortTitle = goal.goal_label?.trim() || `Goal ${index + 1}`
  const recommended = matchRecommendedStrategies(repo?.strategies || [], goal)
  const evidenceGaps = showNudges ? collectGoalEvidenceGaps(goal) : []

  function updatePrimary(patch) {
    const base = primary || emptyStrategyRow(goal.goal_card_id)
    const next = strategies.length
      ? strategies.map((s, i) => (i === 0 ? { ...base, ...s, ...patch } : s))
      : [{ ...base, ...patch }]
    onUpdate({ strategies: next })
  }

  function setFeedback(feedbackId) {
    const nextId = feedbackId === primary?.strategy_feedback ? null : feedbackId
    updatePrimary({ strategy_feedback: nextId })
    if (nextId) {
      const ext = getClinicalExtension(goal)
      const suggested = suggestDefaultsFromFeedback(nextId, ext)
      if (Object.keys(suggested).length) {
        onUpdate({ clinical_extension: mergeClinicalExtension(ext, suggested) })
      }
    }
  }

  function setShortNote(note) {
    updatePrimary({ short_note: note })
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

          <ClinicalTaxonomyPicker
            domains={goal.core_domains || []}
            environments={goal.core_environments || []}
            disabled={readOnly}
            onDomainsChange={(core_domains) => onUpdate({ core_domains })}
            onEnvironmentsChange={(core_environments) => onUpdate({ core_environments })}
          />

          <StrategyUseTodaySection
            primary={primary}
            goal={goal}
            readOnly={readOnly}
            onUpdatePrimary={updatePrimary}
            onUpdateGoal={onUpdate}
            showStrategyPanel={showStrategyPanel}
            onToggleStrategyPanel={onToggleStrategyPanel}
            repo={repo}
            recommended={recommended}
            onPickStrategy={applyStrategy}
            onCreateStrategy={onCreateStrategy}
            caseId={caseId}
          />

          {primary?.strategy_label ? (
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
          ) : null}

          <QuickEvidenceSection
            goal={goal}
            strategyFeedback={primary?.strategy_feedback}
            readOnly={readOnly}
            onUpdateGoal={onUpdate}
          />

          <ProgressSignalsSection goal={goal} readOnly={readOnly} onUpdateGoal={onUpdate} />

          {evidenceGaps.map((gap) => (
            <EvidenceQualityNudge key={gap} gap={gap} />
          ))}

          <label className="gs-field sl-short-note-field">
            <span className="gs-field__label">Optional note</span>
            <textarea
              rows={2}
              disabled={readOnly}
              placeholder="Anything else to remember for the team?"
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
