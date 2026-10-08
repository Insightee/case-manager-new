/** @typedef {{ session_logs: boolean, therapist_leave: boolean, appointments: boolean, billing: boolean, reports: boolean, meetings: boolean }} ParentEmailPreferences */

export const DEFAULT_PARENT_EMAIL_PREFERENCES = {
  session_logs: true,
  therapist_leave: true,
  appointments: false,
  billing: true,
  reports: false,
  meetings: true,
}

/** @type {Array<{ key: keyof ParentEmailPreferences, label: string, description: string, examples: string }>} */
export const PARENT_EMAIL_PREFERENCE_OPTIONS = [
  {
    key: 'appointments',
    label: 'Appointments & scheduling',
    description: 'When sessions are booked, moved, cancelled, or set up on a recurring schedule.',
    examples: 'e.g. “Session confirmed”, “Session cancelled”',
  },
  {
    key: 'session_logs',
    label: 'Session logs',
    description: 'When your therapist submits a session log for review or it is approved.',
    examples: 'e.g. “Session log submitted”',
  },
  {
    key: 'therapist_leave',
    label: 'Therapist leave',
    description: 'When a therapist requests leave or a approved leave is cancelled.',
    examples: 'e.g. “Therapist leave under review”',
  },
  {
    key: 'billing',
    label: 'Invoices & payments',
    description: 'When a new invoice is ready or a payment reminder is sent.',
    examples: 'e.g. “Invoice ready”, payment reminders',
  },
  {
    key: 'reports',
    label: 'Reports',
    description: 'When a monthly or progress report is published to your portal.',
    examples: 'e.g. “New report available”',
  },
  {
    key: 'meetings',
    label: 'Case manager meetings',
    description: 'Meeting invites and reminders from your care team.',
    examples: 'e.g. meeting invite, 1-hour reminder',
  },
]

/**
 * @param {unknown} raw
 * @param {boolean | undefined} legacyLogLeaveEmails
 * @returns {ParentEmailPreferences}
 */
export function emailPreferencesFromApi(raw, legacyLogLeaveEmails) {
  if (raw && typeof raw === 'object' && ('session_logs' in raw || 'appointments' in raw)) {
    const src = raw
    return {
      session_logs: src.session_logs !== false,
      therapist_leave: src.therapist_leave !== false,
      appointments: src.appointments === true,
      billing: src.billing !== false,
      reports: src.reports === true,
      meetings: src.meetings !== false,
    }
  }
  if (legacyLogLeaveEmails === false) {
    return {
      ...DEFAULT_PARENT_EMAIL_PREFERENCES,
      session_logs: false,
      therapist_leave: false,
    }
  }
  return { ...DEFAULT_PARENT_EMAIL_PREFERENCES }
}

/**
 * @param {ParentEmailPreferences} prefs
 */
export function countEnabledEmailPreferences(prefs) {
  return PARENT_EMAIL_PREFERENCE_OPTIONS.filter((opt) => prefs[opt.key]).length
}

/**
 * @param {object} props
 * @param {ParentEmailPreferences} props.preferences
 * @param {(next: ParentEmailPreferences) => void} props.onChange
 * @param {boolean} [props.disabled]
 */
export function ParentEmailPreferencesSection({ preferences, onChange, disabled = false }) {
  const enabledCount = countEnabledEmailPreferences(preferences)
  const allOn = enabledCount === PARENT_EMAIL_PREFERENCE_OPTIONS.length
  const allOff = enabledCount === 0

  function setCategory(key, enabled) {
    onChange({ ...preferences, [key]: enabled })
  }

  function setAll(enabled) {
    onChange(
      PARENT_EMAIL_PREFERENCE_OPTIONS.reduce(
        (acc, opt) => ({ ...acc, [opt.key]: enabled }),
        { ...preferences },
      ),
    )
  }

  return (
    <section className="parent-profile__card parent-profile__email-prefs">
      <div className="parent-profile__email-prefs-head">
        <div>
          <h3>Email preferences</h3>
          <p className="parent-profile__hint parent-profile__hint--flush">
            Choose which updates we send to your inbox. You will still see everything in the portal.
          </p>
        </div>
        <div className="parent-profile__email-prefs-actions">
          <button
            type="button"
            className="parent-profile__email-prefs-link"
            disabled={disabled || allOn}
            onClick={() => setAll(true)}
          >
            Turn on all
          </button>
          <span className="parent-profile__email-prefs-divider" aria-hidden="true">
            ·
          </span>
          <button
            type="button"
            className="parent-profile__email-prefs-link"
            disabled={disabled || allOff}
            onClick={() => setAll(false)}
          >
            Turn off all
          </button>
        </div>
      </div>

      <p className="parent-profile__email-prefs-summary" aria-live="polite">
        {enabledCount === 0
          ? 'No email updates selected — we will only email you for password reset if you request one.'
          : `${enabledCount} of ${PARENT_EMAIL_PREFERENCE_OPTIONS.length} email types enabled`}
      </p>

      <ul className="parent-profile__email-prefs-list">
        {PARENT_EMAIL_PREFERENCE_OPTIONS.map((opt) => {
          const checked = Boolean(preferences[opt.key])
          return (
            <li key={opt.key} className={`parent-profile__email-pref-row${checked ? ' is-on' : ''}`}>
              <label className="parent-profile__email-pref-label">
                <input
                  type="checkbox"
                  checked={checked}
                  disabled={disabled}
                  onChange={(e) => setCategory(opt.key, e.target.checked)}
                />
                <span className="parent-profile__email-pref-copy">
                  <span className="parent-profile__email-pref-title">{opt.label}</span>
                  <span className="parent-profile__email-pref-desc">{opt.description}</span>
                  <span className="parent-profile__email-pref-examples">{opt.examples}</span>
                </span>
              </label>
            </li>
          )
        })}
      </ul>

      <p className="parent-profile__email-prefs-footnote">
        Portal invite and password-reset emails are always sent when needed so you can sign in securely.
      </p>
    </section>
  )
}
