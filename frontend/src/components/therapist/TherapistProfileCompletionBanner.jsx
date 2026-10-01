import { Link, useLocation } from 'react-router-dom'
import { PROFILE_COMPLETION_DEADLINE_LABEL } from '../../lib/therapistQualificationLevels.js'
import './therapist-profile-completion-banner.css'

/**
 * Non-blocking top reminder until therapist profile reaches 100% (hidden on /therapist/profile).
 */
export function TherapistProfileCompletionBanner({ completion }) {
  const location = useLocation()
  const onProfilePage = location.pathname.startsWith('/therapist/profile')
  const incomplete = completion && !completion.complete

  if (!incomplete || onProfilePage) return null

  return (
    <Link
      to="/therapist/profile"
      className="therapist-profile-completion-banner"
      role="status"
      aria-label={`Important: your profile is ${completion.percent} percent complete. Go to profile to finish.`}
    >
      <span className="therapist-profile-completion-banner__label">Important</span>
      <span className="therapist-profile-completion-banner__text">
        Your profile is {completion.percent}% complete — finish by {PROFILE_COMPLETION_DEADLINE_LABEL}. Sessions and
        logs stay available.
      </span>
      <span className="therapist-profile-completion-banner__chevron" aria-hidden>
        →
      </span>
    </Link>
  )
}
