import { submitHelperText } from '../../lib/therapistProfileQuality.js'
import './therapist-profile-quality-panel.css'

export function TherapistProfileQualityPanel({ quality, onJump }) {
  if (!quality) return null
  const percent = quality.percent ?? 0
  const helper = submitHelperText(quality)

  return (
    <section className="tp-quality" aria-labelledby="tp-quality-title">
      <div className="tp-quality__ring" aria-hidden="true">
        <svg viewBox="0 0 36 36">
          <circle className="tp-quality__track" cx="18" cy="18" r="15.5" />
          <circle
            className="tp-quality__fill"
            cx="18"
            cy="18"
            r="15.5"
            strokeDasharray={`${percent} ${100 - percent}`}
          />
        </svg>
        <span className="tp-quality__pct">{percent}%</span>
      </div>
      <div className="tp-quality__copy">
        <p className="tp-quality__eyebrow">Listing quality</p>
        <h2 id="tp-quality-title" className="tp-quality__title">
          {quality.auto_pass ? 'Ready to publish' : quality.can_submit ? 'Almost there' : 'A few details will help'}
        </h2>
        <p className="tp-quality__helper">{helper}</p>
        {quality.reminders?.length ? (
          <ul className="tp-quality__list">
            {quality.reminders.map((row) => (
              <li key={row.key}>
                <button type="button" className="tp-quality__link" onClick={() => onJump?.(row.key)}>
                  {row.message}
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="tp-quality__done">Every quality check looks good.</p>
        )}
      </div>
    </section>
  )
}
