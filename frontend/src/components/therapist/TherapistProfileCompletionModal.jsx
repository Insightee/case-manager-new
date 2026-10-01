import { useNavigate } from 'react-router-dom'
import {
  PROFILE_COMPLETION_DEADLINE_LABEL,
  PROFILE_COMPLETION_EDIT_PATH,
  PROFILE_COMPLETION_FIELD_LABELS,
  orderedMissingFields,
} from '../../lib/therapistQualificationLevels.js'
import './therapist-profile-completion-modal.css'

export function TherapistProfileCompletionModal({
  open,
  completion,
  mode = 'welcome',
  onContinue,
  onSignOut,
}) {
  const navigate = useNavigate()
  if (!open || !completion || completion.complete) return null

  const missing = orderedMissingFields(completion.missing_fields).map(
    (key) => PROFILE_COMPLETION_FIELD_LABELS[key] || key.replace(/_/g, ' '),
  )
  const isLogout = mode === 'logout'

  function goEditDetails() {
    onContinue?.()
    navigate(PROFILE_COMPLETION_EDIT_PATH)
  }

  return (
    <div
      className="therapist-profile-completion-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="profile-completion-title"
    >
      <div className="therapist-profile-completion-modal__sheet">
        <p className="therapist-profile-completion-modal__eyebrow">A few details still help us support you</p>
        <h2 id="profile-completion-title">Please finish your profile by {PROFILE_COMPLETION_DEADLINE_LABEL}</h2>
        <p className="therapist-profile-completion-modal__body">
          You can keep starting sessions and submitting session logs. We still need these details by{' '}
          {PROFILE_COMPLETION_DEADLINE_LABEL} so scheduling and HR can reach you. Your profile is{' '}
          {completion.percent}% complete.
        </p>
        {missing.length ? (
          <ul className="therapist-profile-completion-modal__missing">
            {missing.slice(0, 4).map((label) => (
              <li key={label}>{label}</li>
            ))}
          </ul>
        ) : null}
        <div className="therapist-profile-completion-modal__actions">
          <button type="button" className="therapist-profile-completion-modal__primary" onClick={goEditDetails}>
            Edit your details
          </button>
          {isLogout ? (
            <button type="button" className="therapist-profile-completion-modal__secondary" onClick={onSignOut}>
              Sign out
            </button>
          ) : (
            <button type="button" className="therapist-profile-completion-modal__secondary" onClick={onContinue}>
              Continue to sessions
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
