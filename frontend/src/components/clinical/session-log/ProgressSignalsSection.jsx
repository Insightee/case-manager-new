import { ClinicalChipGroup } from '../../clinical-ui/ClinicalChipGroup.jsx'
import {
  PROGRESS_GOAL_MOVEMENT_OPTIONS,
  PROGRESS_PARTICIPATION_OPTIONS,
  PROGRESS_SUPPORT_NEEDED_OPTIONS,
  getClinicalExtension,
  mergeClinicalExtension,
} from '../../../lib/clinicalEvidenceFields.js'

export function ProgressSignalsSection({ goal, readOnly, onUpdateGoal }) {
  const ext = getClinicalExtension(goal)

  function patchExt(patch) {
    onUpdateGoal({ clinical_extension: mergeClinicalExtension(ext, patch) })
  }

  return (
    <section className="sl-progress-signals">
      <div className="sl-measurement-block__head">
        <p className="sl-v2-section-label">Progress signals</p>
        <p className="gs-muted sl-progress-signals__sub">What changed today?</p>
      </div>
      <ClinicalChipGroup
        label="Participation"
        options={PROGRESS_PARTICIPATION_OPTIONS}
        value={ext.participation_quality}
        readOnly={readOnly}
        onChange={(v) => patchExt({ participation_quality: v })}
      />
      <ClinicalChipGroup
        label="Support needed"
        options={PROGRESS_SUPPORT_NEEDED_OPTIONS}
        value={ext.support_needed}
        readOnly={readOnly}
        onChange={(v) => patchExt({ support_needed: v })}
      />
      <ClinicalChipGroup
        label="Goal movement"
        options={PROGRESS_GOAL_MOVEMENT_OPTIONS}
        value={ext.goal_movement}
        readOnly={readOnly}
        onChange={(v) => patchExt({ goal_movement: v })}
      />
    </section>
  )
}
