import { useState } from 'react'
import { GOALS_STRATEGIES_ENGINE_V2 } from '../../../lib/reportsRevampFlags.js'
import { ClinicalChipGroup, ClinicalSegmentControl } from '../../clinical-ui/ClinicalChipGroup.jsx'
import {
  ADAPTATION_TYPE_OPTIONS,
  STRATEGY_USE_STATUS_OPTIONS,
  getClinicalExtension,
  mergeClinicalExtension,
  suggestDefaultsFromFeedback,
  suggestFromStrategyStatus,
} from '../../../lib/clinicalEvidenceFields.js'
import { NEGATIVE_STRATEGY_FEEDBACK } from '../../../lib/clinicalScoring.js'
import { StrategyPickerOverlay } from '../../clinical-brain/StrategyPickerOverlay.jsx'

export function StrategyUseTodaySection({
  primary,
  goal,
  readOnly,
  onUpdatePrimary,
  onUpdateGoal,
  onToggleStrategyPanel,
  showStrategyPanel,
  repo,
  recommended,
  onPickStrategy,
  onCreateStrategy,
  caseId,
  recentStrategies = [],
}) {
  const [showSteps, setShowSteps] = useState(false)
  const goalExt = getClinicalExtension(goal)
  const stratExt = getClinicalExtension(primary || {})
  const strategyStatus = stratExt.strategy_status || goalExt.strategy_status
  const adaptationTypes = stratExt.adaptation_type?.length ? stratExt.adaptation_type : goalExt.adaptation_type || []
  const adaptationNote = stratExt.adaptation_note || goalExt.adaptation_note || ''

  function patchStrategyExt(patch) {
    const merged = mergeClinicalExtension(stratExt, patch)
    onUpdatePrimary?.({ clinical_extension: merged })
    onUpdateGoal?.({ clinical_extension: mergeClinicalExtension(goalExt, patch) })
  }

  function setStrategyStatus(status) {
    let extPatch = { strategy_status: status }
    extPatch = suggestFromStrategyStatus(status, extPatch)
    if (primary?.strategy_feedback && NEGATIVE_STRATEGY_FEEDBACK.has(primary.strategy_feedback)) {
      extPatch = suggestDefaultsFromFeedback(primary.strategy_feedback, extPatch)
    }
    patchStrategyExt(extPatch)
  }

  const steps = primary?.strategy_steps || ['', '', '']

  return (
    <section className="sl-strategy-block">
      {!readOnly && !primary?.strategy_label ? (
        <button type="button" className="gs-btn gs-btn--secondary sl-strategy-block__add-full" onClick={onToggleStrategyPanel}>
          + Add strategy
        </button>
      ) : null}

      {primary?.strategy_label || readOnly ? (
        <div className="sl-strategy-block__head">
          <p className="sl-v2-section-label">Strategy used today</p>
          {!readOnly && primary?.strategy_label ? (
            <button type="button" className="sl-strategy-block__change" onClick={onToggleStrategyPanel}>
              Change
            </button>
          ) : null}
        </div>
      ) : null}

      {GOALS_STRATEGIES_ENGINE_V2 && showStrategyPanel && !readOnly ? (
        <StrategyPickerOverlay
          open
          caseId={caseId}
          goalCardId={goal?.goal_card_id}
          goalLabel={goal?.goal_label}
          recommended={recommended}
          recent={recentStrategies}
          onClose={onToggleStrategyPanel}
          onSelect={(item) => {
            onPickStrategy(item)
            onToggleStrategyPanel?.()
          }}
          onCreateCustom={onCreateStrategy}
        />
      ) : showStrategyPanel && !readOnly ? (
        <div className="sl-strategy-panel">
          {recommended?.length ? (
            <>
              <p className="sl-strategy-panel__subtitle">Recommended for selected domains</p>
              <div className="sl-repo-picker">
                {recommended.map((s) => (
                  <button
                    key={`rec-${s.strategy_id}-${s.label}`}
                    type="button"
                    className="sl-repo-picker__row sl-repo-picker__row--rec"
                    onClick={() => onPickStrategy(s)}
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
                    onClick={() => onPickStrategy(s)}
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

          <ClinicalSegmentControl
            label="How was it used?"
            options={STRATEGY_USE_STATUS_OPTIONS}
            value={strategyStatus}
            readOnly={readOnly}
            onChange={setStrategyStatus}
          />

          {strategyStatus === 'adapted_today' ? (
            <>
              <ClinicalChipGroup
                label="Adaptations made"
                options={ADAPTATION_TYPE_OPTIONS}
                values={adaptationTypes}
                multi
                readOnly={readOnly}
                onChange={(vals) => patchStrategyExt({ adaptation_type: vals })}
              />
              <label className="gs-field">
                <span className="gs-field__label">What changed today?</span>
                <input
                  type="text"
                  disabled={readOnly}
                  value={adaptationNote}
                  placeholder="Optional — brief note on adaptation"
                  onChange={(e) => patchStrategyExt({ adaptation_note: e.target.value })}
                />
              </label>
            </>
          ) : null}

          {!readOnly ? (
            <button type="button" className="sl-disclosure-link" onClick={() => setShowSteps((v) => !v)}>
              {showSteps ? 'Hide activity steps' : 'Edit activity steps (optional)'}
            </button>
          ) : null}

          {showSteps || readOnly ? (
            <div className="sl-strategy-steps">
              {[0, 1, 2].map((i) => (
                <label key={i} className="sl-strategy-step-row">
                  <span className="sl-strategy-step-row__num">{i + 1}</span>
                  <input
                    type="text"
                    disabled={readOnly}
                    placeholder={`Step ${i + 1}…`}
                    value={steps[i] || ''}
                    onChange={(e) => {
                      const next = [...steps]
                      next[i] = e.target.value
                      onUpdatePrimary({ strategy_steps: next })
                    }}
                  />
                </label>
              ))}
            </div>
          ) : null}
        </div>
      ) : (
        <p className="gs-muted">Choose a strategy to document how it was used today.</p>
      )}
    </section>
  )
}
