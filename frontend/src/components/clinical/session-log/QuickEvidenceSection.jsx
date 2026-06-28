import { useState } from 'react'
import { ClinicalChipGroup } from '../../clinical-ui/ClinicalChipGroup.jsx'
import {
  ADAPTATION_TYPE_OPTIONS,
  BARRIER_TYPE_OPTIONS,
  CHILD_RESPONSE_OPTIONS,
  ENVIRONMENT_FIT_OPTIONS,
  NEXT_STEP_OPTIONS,
  PARTICIPATION_QUALITY_QUICK_OPTIONS,
  getClinicalExtension,
  mergeClinicalExtension,
  shouldShowAdaptation,
  shouldShowBarrierTypes,
  suggestFromChildResponse,
} from '../../../lib/clinicalEvidenceFields.js'

const ADAPTATION_NOTE_MAX = 500

export function QuickEvidenceSection({ goal, strategyFeedback, readOnly, onUpdateGoal }) {
  const ext = getClinicalExtension(goal)
  const [adaptationOpen, setAdaptationOpen] = useState(false)
  const showBarriers = shouldShowBarrierTypes(ext.environment_fit)
  const showAdaptation = shouldShowAdaptation(strategyFeedback, adaptationOpen)

  function patchExt(patch) {
    let next = mergeClinicalExtension(ext, patch)
    if (patch.child_response) {
      next = mergeClinicalExtension(next, suggestFromChildResponse(patch.child_response, next))
    }
    if (patch.environment_fit && !shouldShowBarrierTypes(patch.environment_fit)) {
      next = mergeClinicalExtension(next, { barrier_type: [] })
    }
    onUpdateGoal({ clinical_extension: next })
  }

  return (
    <section className="sl-quick-evidence" aria-labelledby="sl-quick-evidence-title">
      <p id="sl-quick-evidence-title" className="sl-v2-section-label">
        What helped participation today?
      </p>

      <ClinicalChipGroup
        label="Child response"
        options={CHILD_RESPONSE_OPTIONS}
        value={ext.child_response}
        readOnly={readOnly}
        required
        onChange={(v) => patchExt({ child_response: v })}
      />

      <ClinicalChipGroup
        label="Participation quality"
        options={PARTICIPATION_QUALITY_QUICK_OPTIONS}
        value={ext.participation_quality}
        readOnly={readOnly}
        onChange={(v) => patchExt({ participation_quality: v })}
      />

      <ClinicalChipGroup
        label="Environment fit"
        options={ENVIRONMENT_FIT_OPTIONS}
        value={ext.environment_fit}
        readOnly={readOnly}
        onChange={(v) => patchExt({ environment_fit: v })}
      />

      {showBarriers ? (
        <ClinicalChipGroup
          label="Barrier type"
          options={BARRIER_TYPE_OPTIONS}
          values={ext.barrier_type || []}
          multi
          readOnly={readOnly}
          onChange={(vals) => patchExt({ barrier_type: vals })}
        />
      ) : null}

      {!showAdaptation && !readOnly ? (
        <button type="button" className="sl-disclosure-link" onClick={() => setAdaptationOpen(true)}>
          Add adaptation
        </button>
      ) : null}

      {showAdaptation ? (
        <>
          <ClinicalChipGroup
            label="Adaptation type"
            options={ADAPTATION_TYPE_OPTIONS}
            values={ext.adaptation_type || []}
            multi
            readOnly={readOnly}
            onChange={(vals) => patchExt({ adaptation_type: vals })}
          />
          <label className="gs-field">
            <span className="gs-field__label">Adaptation note (optional)</span>
            <textarea
              rows={2}
              maxLength={ADAPTATION_NOTE_MAX}
              disabled={readOnly}
              placeholder="Brief note on what was adapted today"
              value={ext.adaptation_note || ''}
              onChange={(e) => patchExt({ adaptation_note: e.target.value.slice(0, ADAPTATION_NOTE_MAX) })}
            />
          </label>
        </>
      ) : null}

      <ClinicalChipGroup
        label="Therapist interpretation"
        options={NEXT_STEP_OPTIONS}
        value={ext.therapist_interpretation}
        readOnly={readOnly}
        required
        onChange={(v) => patchExt({ therapist_interpretation: v })}
      />
    </section>
  )
}
