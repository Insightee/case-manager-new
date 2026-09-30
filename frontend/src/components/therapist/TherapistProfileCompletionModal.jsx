import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { PROFILE_COMPLETION_FIELD_LABELS } from '../../lib/therapistQualificationLevels.js'

/**
 * Blocking reminder until therapist profile reaches 100% (hidden on /therapist/profile).
 */
export function TherapistProfileCompletionModal({ completion }) {
  const location = useLocation()
  const onProfilePage = location.pathname.startsWith('/therapist/profile')
  const incomplete = completion && !completion.complete
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (incomplete && !onProfilePage) {
      setOpen(true)
    } else {
      setOpen(false)
    }
  }, [incomplete, onProfilePage, location.pathname, completion?.percent])

  if (!open || !completion) return null

  const missing = (completion.missing_fields || []).map(
    (key) => PROFILE_COMPLETION_FIELD_LABELS[key] || key.replace(/_/g, ' '),
  )

  return (
    <div className="ic-case-status-modal therapist-profile-completion-modal" role="dialog" aria-modal="true" aria-labelledby="profile-completion-title">
      <div className="ic-case-status-modal__backdrop therapist-profile-completion-modal__backdrop" aria-hidden />
      <div className="ic-case-status-modal__sheet">
        <p className="therapist-profile__eyebrow" style={{ marginTop: 0 }}>
          Important
        </p>
        <h2 id="profile-completion-title">Your profile is {completion.percent}% complete</h2>
        <p className="ic-case-panel__hint">
          Please complete your profile so scheduling, homecare planning, and your service listing stay up to date.
        </p>
        {missing.length ? (
          <ul className="therapist-profile-completion-modal__missing">
            {missing.map((label) => (
              <li key={label}>{label}</li>
            ))}
          </ul>
        ) : null}
        <div className="ic-case-status-modal__actions" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
          <Link to="/therapist/profile" className="ic-btn ic-btn--primary" style={{ textAlign: 'center', textDecoration: 'none' }}>
            Complete profile
          </Link>
        </div>
      </div>
    </div>
  )
}
