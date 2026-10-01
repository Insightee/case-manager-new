import {
  orderedMissingFields,
  PROFILE_COMPLETION_FIELD_LABELS,
  PROFILE_COMPLETION_SECTION_IDS,
} from '../../lib/therapistQualificationLevels.js'

/**
 * Profile page header: next pending completion item and count remaining.
 */
export function TherapistProfileCompletionGuide({ completion, onGoToField }) {
  if (!completion || completion.complete) return null

  const ordered = orderedMissingFields(completion.missing_fields)
  if (!ordered.length) return null

  const nextKey = ordered[0]
  const remaining = ordered.length
  const label = PROFILE_COMPLETION_FIELD_LABELS[nextKey] || nextKey.replace(/_/g, ' ')
  const totalSteps = completion.total_steps ?? remaining + (completion.completed_steps ?? 0)

  function handleGo() {
    const sectionId = PROFILE_COMPLETION_SECTION_IDS[nextKey]
    onGoToField?.(nextKey, sectionId)
    if (sectionId && typeof document !== 'undefined') {
      document.getElementById(sectionId)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }

  return (
    <section className="therapist-profile-completion-guide" aria-labelledby="profile-completion-guide-title">
      <div className="therapist-profile-completion-guide__head">
        <p className="therapist-profile-completion-guide__eyebrow">Still to finish</p>
        <h2 id="profile-completion-guide-title" className="therapist-profile-completion-guide__title">
          1 of {remaining} remaining
        </h2>
      </div>
      <p className="therapist-profile-completion-guide__next">
        <strong>{label}</strong> pending
      </p>
      <p className="therapist-profile-completion-guide__meta">
        {completion.completed_steps ?? totalSteps - remaining} of {totalSteps} profile steps done ({completion.percent}
        %)
      </p>
      {remaining > 1 ? (
        <p className="therapist-profile-completion-guide__up-next">
          Up next after this:{' '}
          {ordered.slice(1, 3).map((key, i) => (
            <span key={key}>
              {i > 0 ? ', ' : ''}
              {PROFILE_COMPLETION_FIELD_LABELS[key]}
            </span>
          ))}
          {remaining > 3 ? '…' : ''}
        </p>
      ) : null}
      <button type="button" className="therapist-profile-completion-guide__action" onClick={handleGo}>
        Go to {label.toLowerCase()}
      </button>
    </section>
  )
}
