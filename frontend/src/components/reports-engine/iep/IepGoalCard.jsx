import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { GOAL_MODAL_DOMAIN_CHIPS } from '../../../lib/clinicalUiContract.js'
import { labelForMeasurement } from '../../../lib/clinicalMeasurementCriteria.js'
import { MeasurementCriteriaSelect } from '../../clinical/MeasurementCriteriaSelect.jsx'

const SOURCE_LABELS = {
  observation_candidate: 'From observation',
  repository: 'From library',
  session_log_candidate: 'From session log',
  manual: 'Custom goal',
}

function domainLabel(domainId) {
  const chip = GOAL_MODAL_DOMAIN_CHIPS.find((c) => c.id === domainId)
  if (chip) return chip.label
  if (!domainId || domainId === 'general') return 'General'
  return String(domainId).replace(/_/g, ' ')
}

function statusLabel(goal) {
  const raw = goal.lifecycle_status || goal.status || 'draft'
  return raw.replace(/_/g, ' ')
}

export function IepGoalCard({ goal, readOnly, onEdit, onRemove, onLinkStrategy, onMarkAchieved }) {
  const statement = (goal.parent_facing_wording || goal.goal_statement || goal.title || '').trim()
  const displayStatement = statement || 'Goal statement not added yet — tap Edit to describe this goal.'
  const strategies = goal.linked_strategy_ids?.length || 0
  const hasBaseline = Boolean((goal.baseline_current_state || '').trim())
  const hasDesired = Boolean((goal.desired_state || '').trim())

  return (
    <article className="iep-goal-card">
      <header className="iep-goal-card__head">
        <div className="iep-goal-card__meta">
          <span className="iep-goal-card__badge">{domainLabel(goal.domain)}</span>
          <span className="iep-goal-card__badge iep-goal-card__badge--muted">{statusLabel(goal)}</span>
          <span className="iep-goal-card__badge iep-goal-card__badge--muted">
            {SOURCE_LABELS[goal.source_type] || goal.source_type || 'Custom goal'}
          </span>
        </div>
        <p className={`iep-goal-card__statement${statement ? '' : ' iep-goal-card__block-text--empty'}`} style={statement ? undefined : { opacity: 0.85, fontStyle: 'italic', fontWeight: 600 }}>
          {displayStatement}
        </p>
      </header>

      <div className="iep-goal-card__body">
        <div className="iep-goal-card__columns">
          <div className="iep-goal-card__block">
            <p className="iep-goal-card__block-label">Where we are now</p>
            <p className={`iep-goal-card__block-text${hasBaseline ? '' : ' iep-goal-card__block-text--empty'}`}>
              {hasBaseline ? goal.baseline_current_state : 'Add baseline when editing this goal.'}
            </p>
          </div>
          <div className="iep-goal-card__block">
            <p className="iep-goal-card__block-label">Where we&apos;re heading</p>
            <p className={`iep-goal-card__block-text${hasDesired ? '' : ' iep-goal-card__block-text--empty'}`}>
              {hasDesired ? goal.desired_state : 'Add desired outcome when editing this goal.'}
            </p>
          </div>
        </div>

        <div className="iep-goal-card__measures">
          <span className="iep-goal-card__measure">
            {labelForMeasurement('participation', goal.participation)}
          </span>
          <span className="iep-goal-card__measure">
            {labelForMeasurement('independence_support_needed', goal.independence_support_needed)}
          </span>
          <span className="iep-goal-card__measure">
            {labelForMeasurement('goal_achievement', goal.goal_achievement)}
          </span>
        </div>

        <p className="iep-goal-card__strategies">
          {strategies === 0
            ? 'No strategies linked yet — link at least one support strategy.'
            : `${strategies} linked strateg${strategies === 1 ? 'y' : 'ies'}`}
        </p>

        {!readOnly ? (
          <div className="iep-goal-card__actions">
            <button type="button" className="iep-goal-card__btn iep-goal-card__btn--primary" onClick={() => onEdit?.(goal)}>
              Edit goal
            </button>
            <button type="button" className="iep-goal-card__btn" onClick={() => onLinkStrategy?.(goal)}>
              Link strategy
            </button>
            {goal.lifecycle_status === 'active' || goal.status === 'approved' ? (
              <button type="button" className="iep-goal-card__btn" onClick={() => onMarkAchieved?.(goal)}>
                Mark achieved
              </button>
            ) : null}
            <button type="button" className="iep-goal-card__btn iep-goal-card__btn--danger" onClick={() => onRemove?.(goal)}>
              Remove
            </button>
          </div>
        ) : null}
      </div>
    </article>
  )
}

export function IepGoalEditor({ open, goal, onClose, onSave }) {
  const [draft, setDraft] = useState(goal || {})

  useEffect(() => {
    if (open) setDraft(goal || {})
  }, [open, goal])

  const previewText = useMemo(() => {
    const text = (draft.goal_statement || draft.title || '').trim()
    if (text) return text
    return 'Your goal statement will appear here as you type.'
  }, [draft.goal_statement, draft.title])

  if (!open) return null

  return createPortal(
    <div className="sg-modal-root clinical-report-ui" role="dialog" aria-modal="true" aria-labelledby="iep-edit-goal-title">
      <button type="button" className="sg-modal-root__backdrop" aria-label="Close" onClick={onClose} />
      <div className="sg-modal sg-modal--narrow sg-modal--iep-goal" onClick={(e) => e.stopPropagation()}>
        <header className="sg-modal__head">
          <div>
            <h2 id="iep-edit-goal-title" className="sg-modal__title">
              Edit goal
            </h2>
            <p className="sg-modal__subtitle">Update the goal statement, progress markers, and family-facing wording.</p>
          </div>
          <button type="button" className="sg-modal__close" aria-label="Close" onClick={onClose}>
            ×
          </button>
        </header>

        <div className="sg-modal__body">
          <div className="sg-modal__main">
            <div className="iep-goal-editor__preview">
              <p className="iep-goal-editor__preview-label">Goal preview</p>
              <p className="iep-goal-editor__preview-text">{previewText}</p>
            </div>

            <p className="iep-goal-editor__section-title">Goal details</p>

            <label className="sg-field">
              <span className="sg-field__label">Goal statement</span>
              <textarea
                placeholder="e.g. Alex will use 2-word phrases to request preferred items during structured play."
                value={draft.goal_statement || draft.title || ''}
                onChange={(e) => setDraft({ ...draft, goal_statement: e.target.value, title: e.target.value })}
              />
            </label>

            <p className="sg-field__label" style={{ marginBottom: '0.5rem' }}>
              Clinical domain
            </p>
            <div className="sg-domain-grid">
              {GOAL_MODAL_DOMAIN_CHIPS.map((chip) => (
                <button
                  key={chip.id}
                  type="button"
                  className={`sg-domain-tile${draft.domain === chip.id ? ' sg-domain-tile--active' : ''}`}
                  onClick={() => setDraft({ ...draft, domain: chip.id })}
                >
                  {chip.label}
                </button>
              ))}
            </div>

            <div className="iep-goal-card__columns" style={{ marginBottom: '1rem' }}>
              <label className="sg-field" style={{ marginBottom: 0 }}>
                <span className="sg-field__label">Baseline / current state</span>
                <textarea
                  placeholder="What does participation look like today?"
                  value={draft.baseline_current_state || ''}
                  onChange={(e) => setDraft({ ...draft, baseline_current_state: e.target.value })}
                />
              </label>
              <label className="sg-field" style={{ marginBottom: 0 }}>
                <span className="sg-field__label">Desired state</span>
                <textarea
                  placeholder="What would success look like by the review date?"
                  value={draft.desired_state || ''}
                  onChange={(e) => setDraft({ ...draft, desired_state: e.target.value })}
                />
              </label>
            </div>

            <p className="iep-goal-editor__section-title">Progress markers</p>
            <MeasurementCriteriaSelect values={draft} onChange={(m) => setDraft({ ...draft, ...m })} />

            <p className="iep-goal-editor__section-title">Family view</p>
            <label className="sg-field">
              <span className="sg-field__label">Parent-facing wording (optional)</span>
              <textarea
                placeholder="Plain-language version for families — leave blank to use the goal statement."
                value={draft.parent_facing_wording || ''}
                onChange={(e) => setDraft({ ...draft, parent_facing_wording: e.target.value })}
              />
            </label>
          </div>
        </div>

        <footer className="sg-modal__foot">
          <button type="button" className="iep-goal-card__btn" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="iep-goal-card__btn iep-goal-card__btn--primary"
            onClick={() => onSave?.(draft)}
          >
            Save goal
          </button>
        </footer>
      </div>
    </div>,
    document.body,
  )
}
