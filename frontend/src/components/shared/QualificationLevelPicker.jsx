import { THERAPIST_QUALIFICATION_LEVELS } from '../../lib/therapistQualificationLevels.js'

/**
 * Single-select highest academic qualification level (UG, PG, …).
 */
export function QualificationLevelPicker({ value, onChange, disabled, name = 'academic_qualification_level' }) {
  return (
    <fieldset
      style={{ border: 'none', margin: 0, padding: 0 }}
      disabled={disabled}
      aria-label="Highest qualification level"
    >
      <div className="therapist-profile__qual-levels" role="radiogroup">
        {THERAPIST_QUALIFICATION_LEVELS.map((row) => {
          const checked = value === row.value
          return (
            <label
              key={row.value}
              className={`therapist-profile__qual-level${checked ? ' therapist-profile__qual-level--active' : ''}`}
            >
              <input
                type="radio"
                name={name}
                value={row.value}
                checked={checked}
                onChange={() => onChange?.(row.value)}
              />
              <span>{row.label}</span>
            </label>
          )
        })}
      </div>
    </fieldset>
  )
}
