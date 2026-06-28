import { useState } from 'react'
import { ClinicalChipGroup } from '../../clinical-ui/ClinicalChipGroup.jsx'
import {
  CHILD_RESPONSE_OPTIONS,
  ENVIRONMENT_FIT_OPTIONS,
  NEXT_STEP_OPTIONS,
  OBSERVATION_SIGNAL_OPTIONS,
  PROGRESS_PARTICIPATION_OPTIONS,
} from '../../../lib/clinicalEvidenceFields.js'

const EMPTY = {
  domain: '',
  environment: '',
  activity_context: '',
  observation_signals: [],
  child_response: null,
  participation_quality: null,
  environment_fit: null,
  barrier: null,
  next_step: null,
}

export function ObservationEvidenceCard({
  readOnly = false,
  onKeepObservation,
  onAddGoalCandidate,
  onAddStrategyCandidate,
  onNeedsMoreEvidence,
  onSendToCmReview,
}) {
  const [draft, setDraft] = useState(EMPTY)

  function patch(field, value) {
    setDraft((prev) => ({ ...prev, [field]: value }))
  }

  const payload = {
    label: draft.activity_context || 'Observation evidence',
    domain_key: draft.domain || 'general',
    observation_signals: draft.observation_signals,
    child_response: draft.child_response,
    participation_quality: draft.participation_quality,
    environment_fit: draft.environment_fit,
    next_step: draft.next_step,
  }

  return (
    <section className="bg-surface-container-lowest p-5 sm:p-8 rounded-xl clinical-shadow border border-outline-variant/30">
      <h3 className="text-xl sm:text-2xl font-bold text-lush-forest mb-2 m-0">Observation evidence</h3>
      <p className="text-sm text-on-surface-variant mb-6 m-0">
        Tap structured signals — suggestions stay as candidates until case manager review.
      </p>

      <div className="space-y-4">
        <label className="block text-sm">
          Activity context
          <input
            className="mt-1 w-full min-h-[44px] rounded-xl border border-outline-variant/50 px-3"
            disabled={readOnly}
            value={draft.activity_context}
            onChange={(e) => patch('activity_context', e.target.value)}
            placeholder="What was happening during observation?"
          />
        </label>

        <ClinicalChipGroup
          label="Observation signals"
          options={OBSERVATION_SIGNAL_OPTIONS}
          value={draft.observation_signals}
          multiple
          disabled={readOnly}
          onChange={(v) => patch('observation_signals', v)}
        />

        <ClinicalChipGroup
          label="Child response"
          options={CHILD_RESPONSE_OPTIONS}
          value={draft.child_response}
          disabled={readOnly}
          onChange={(v) => patch('child_response', v)}
        />

        <ClinicalChipGroup
          label="Participation quality"
          options={PROGRESS_PARTICIPATION_OPTIONS}
          value={draft.participation_quality}
          disabled={readOnly}
          onChange={(v) => patch('participation_quality', v)}
        />

        <ClinicalChipGroup
          label="Environment fit"
          options={ENVIRONMENT_FIT_OPTIONS}
          value={draft.environment_fit}
          disabled={readOnly}
          onChange={(v) => patch('environment_fit', v)}
        />

        <ClinicalChipGroup
          label="Next step"
          options={NEXT_STEP_OPTIONS}
          value={draft.next_step}
          disabled={readOnly}
          onChange={(v) => patch('next_step', v)}
        />
      </div>

      {!readOnly ? (
        <div className="flex flex-wrap gap-2 mt-6">
          <button type="button" className="min-h-[44px] px-4 rounded-xl border text-sm font-semibold" onClick={() => onKeepObservation?.(payload)}>
            Keep as observation
          </button>
          <button type="button" className="min-h-[44px] px-4 rounded-xl bg-lush-forest text-white text-sm font-semibold" onClick={() => onAddGoalCandidate?.(payload)}>
            Add as candidate goal
          </button>
          <button type="button" className="min-h-[44px] px-4 rounded-xl border text-sm font-semibold" onClick={() => onAddStrategyCandidate?.(payload)}>
            Add as candidate strategy
          </button>
          <button type="button" className="min-h-[44px] px-4 rounded-xl border text-sm font-semibold" onClick={() => onNeedsMoreEvidence?.(payload)}>
            Needs more evidence
          </button>
          <button type="button" className="min-h-[44px] px-4 rounded-xl border text-sm font-semibold" onClick={() => onSendToCmReview?.(payload)}>
            Send to CM review
          </button>
        </div>
      ) : null}
    </section>
  )
}
