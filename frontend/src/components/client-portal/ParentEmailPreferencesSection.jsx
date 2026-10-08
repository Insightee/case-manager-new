import {
  countEnabledEmailPreferences,
  DEFAULT_PARENT_EMAIL_PREFERENCES,
  emailPreferencesFromApi,
  PARENT_EMAIL_PREFERENCE_OPTIONS,
} from './parentEmailPreferenceUtils.js'

export {
  DEFAULT_PARENT_EMAIL_PREFERENCES,
  emailPreferencesFromApi,
  PARENT_EMAIL_PREFERENCE_OPTIONS,
} from './parentEmailPreferenceUtils.js'

/**
 * @param {object} props
 * @param {import('./parentEmailPreferenceUtils.js').ParentEmailPreferences} props.preferences
 * @param {(next: import('./parentEmailPreferenceUtils.js').ParentEmailPreferences) => void} props.onChange
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
    <section
      id="email-preferences"
      className="parent-profile__card parent-profile__email-prefs"
    >
      <div className="parent-profile__email-prefs-head">
        <div>
          <h3>Email preferences</h3>
          <p className="parent-profile__hint parent-profile__hint--flush">
            We only email what matters; everything else stays in your notifications.
          </p>
        </div>
        <div className="parent-profile__email-prefs-actions">
          <button
            type="button"
            className="parent-profile__link-btn"
            disabled={disabled || allOn}
            onClick={() => setAll(true)}
          >
            Turn on all
          </button>
          <button
            type="button"
            className="parent-profile__link-btn"
            disabled={disabled || allOff}
            onClick={() => setAll(false)}
          >
            Turn off all
          </button>
        </div>
      </div>
      <ul className="parent-profile__email-prefs-list">
        {PARENT_EMAIL_PREFERENCE_OPTIONS.map((opt) => (
          <li key={opt.key} className="parent-profile__email-pref-row">
            <label className="parent-profile__email-pref-label">
              <input
                type="checkbox"
                checked={Boolean(preferences[opt.key])}
                disabled={disabled}
                onChange={(e) => setCategory(opt.key, e.target.checked)}
              />
              <span className="parent-profile__email-pref-text">
                <span className="parent-profile__email-pref-title">{opt.label}</span>
                <span className="parent-profile__email-pref-desc">{opt.description}</span>
                <span className="parent-profile__email-pref-examples">{opt.examples}</span>
              </span>
            </label>
          </li>
        ))}
      </ul>
    </section>
  )
}
