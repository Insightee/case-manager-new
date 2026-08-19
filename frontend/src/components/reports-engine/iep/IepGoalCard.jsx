import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { labelForMeasurement } from '../../../lib/clinicalMeasurementCriteria.js'
import { MeasurementCriteriaSelect } from '../../clinical/MeasurementCriteriaSelect.jsx'

const SOURCE_LABELS = {
  observation_candidate: 'Observation',
  repository: 'Repository',
  session_log_candidate: 'Session log',
  manual: 'Manual',
}

export function IepGoalCard({ goal, readOnly, onEdit, onRemove, onLinkStrategy, onMarkAchieved }) {
  const title = goal.title || goal.goal_statement || 'Goal'
  const strategies = goal.linked_strategy_ids?.length || 0

  return (
    <article className="rounded-xl overflow-hidden clinical-shadow border border-outline-variant/30 mb-4">
      <header className="bg-lush-forest text-white px-4 py-3 flex flex-wrap justify-between gap-2 items-start">
        <div>
          <p className="text-xs uppercase font-mono opacity-80 m-0">{goal.domain || 'General'}</p>
          <h3 className="text-base font-bold m-0 mt-1">{title}</h3>
        </div>
        <div className="flex flex-wrap gap-2">
          <span className="text-xs bg-white/20 px-2 py-0.5 rounded-full">{SOURCE_LABELS[goal.source_type] || goal.source_type}</span>
          <span className="text-xs bg-white/20 px-2 py-0.5 rounded-full">{goal.lifecycle_status || goal.status || 'draft'}</span>
        </div>
      </header>
      <div className="bg-surface-container-lowest p-4 space-y-3">
        {goal.baseline_current_state ? (
          <p className="text-sm m-0">
            <strong>Baseline:</strong> {goal.baseline_current_state}
          </p>
        ) : null}
        {goal.desired_state ? (
          <p className="text-sm m-0">
            <strong>Desired:</strong> {goal.desired_state}
          </p>
        ) : null}
        <div className="grid md:grid-cols-3 gap-2 text-xs text-on-surface-variant">
          <span>Participation: {labelForMeasurement('participation', goal.participation)}</span>
          <span>Support: {labelForMeasurement('independence_support_needed', goal.independence_support_needed)}</span>
          <span>Achievement: {labelForMeasurement('goal_achievement', goal.goal_achievement)}</span>
        </div>
        <p className="text-xs text-on-surface-variant m-0">
          {strategies} linked strateg{strategies === 1 ? 'y' : 'ies'}
        </p>
        {!readOnly ? (
          <div className="flex flex-wrap gap-2 pt-2">
            <button type="button" className="min-h-[44px] px-3 rounded-lg border text-sm font-semibold" onClick={() => onEdit?.(goal)}>
              Edit
            </button>
            <button type="button" className="min-h-[44px] px-3 rounded-lg border text-sm font-semibold" onClick={() => onLinkStrategy?.(goal)}>
              Link strategy
            </button>
            {goal.lifecycle_status === 'active' || goal.status === 'approved' ? (
              <button type="button" className="min-h-[44px] px-3 rounded-lg border text-sm font-semibold" onClick={() => onMarkAchieved?.(goal)}>
                Mark achieved
              </button>
            ) : null}
            <button type="button" className="min-h-[44px] px-3 rounded-lg border text-sm text-error" onClick={() => onRemove?.(goal)}>
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
  if (!open) return null
  return createPortal(
    <div
      className="sg-modal-root clinical-report-ui"
      role="dialog"
      aria-modal="true"
      aria-labelledby="iep-edit-goal-title"
    >
      <button type="button" className="sg-modal-root__backdrop" aria-label="Close" onClick={onClose} />
      <div className="sg-modal sg-modal--narrow" onClick={(e) => e.stopPropagation()}>
        <div className="sg-modal__body" style={{ display: 'block', overflowY: 'auto' }}>
        <h2 id="iep-edit-goal-title" className="text-lg font-bold m-0 mb-4">Edit goal</h2>
        <div className="space-y-3">
          <label className="block text-sm">
            Goal statement
            <textarea
              className="mt-1 w-full min-h-[80px] rounded-xl border border-outline-variant/50 p-3 bg-white"
              value={draft.goal_statement || draft.title || ''}
              onChange={(e) => setDraft({ ...draft, goal_statement: e.target.value, title: e.target.value })}
            />
          </label>
          <label className="block text-sm">
            Domain
            <input
              className="mt-1 w-full min-h-[44px] rounded-xl border border-outline-variant/50 px-3 bg-white"
              value={draft.domain || ''}
              onChange={(e) => setDraft({ ...draft, domain: e.target.value })}
            />
          </label>
          <label className="block text-sm">
            Baseline / current state
            <textarea
              className="mt-1 w-full rounded-xl border border-outline-variant/50 p-3 bg-white"
              value={draft.baseline_current_state || ''}
              onChange={(e) => setDraft({ ...draft, baseline_current_state: e.target.value })}
            />
          </label>
          <label className="block text-sm">
            Desired state
            <textarea
              className="mt-1 w-full rounded-xl border border-outline-variant/50 p-3 bg-white"
              value={draft.desired_state || ''}
              onChange={(e) => setDraft({ ...draft, desired_state: e.target.value })}
            />
          </label>
          <MeasurementCriteriaSelect values={draft} onChange={(m) => setDraft({ ...draft, ...m })} />
          <label className="block text-sm">
            Parent-facing wording
            <textarea
              className="mt-1 w-full rounded-xl border border-outline-variant/50 p-3 bg-white"
              value={draft.parent_facing_wording || ''}
              onChange={(e) => setDraft({ ...draft, parent_facing_wording: e.target.value })}
            />
          </label>
        </div>
        <div className="flex gap-3 mt-6">
          <button type="button" className="flex-1 min-h-[44px] rounded-xl font-bold" style={{ backgroundColor: '#0b1c16', color: '#fff' }} onClick={() => onSave?.(draft)}>
            Save goal
          </button>
          <button type="button" className="min-h-[44px] px-4 rounded-xl border bg-white" onClick={onClose}>
            Cancel
          </button>
        </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}
