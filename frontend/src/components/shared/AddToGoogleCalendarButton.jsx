import {
  buildGoogleCalendarAccountChooserUrl,
  buildGoogleCalendarUrl,
} from '../../lib/googleCalendar.js'

const VARIANT_CLASS = {
  primary:
    'inline-flex min-h-[44px] items-center justify-center gap-2 rounded-xl bg-white border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-800 shadow-sm hover:bg-slate-50',
  ghost:
    'inline-flex min-h-[44px] items-center justify-center gap-2 rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-2.5 text-sm font-semibold text-indigo-800 hover:bg-indigo-100',
  inline:
    'inline-flex items-center gap-1.5 text-sm font-semibold text-indigo-700 hover:text-indigo-900 hover:underline',
}

const CALENDAR_ICON = (
  <svg aria-hidden="true" className="h-4 w-4 shrink-0" viewBox="0 0 24 24" fill="none">
    <path
      d="M7 3v2M17 3v2M4 9h16M6 5h12a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
    />
  </svg>
)

export function AddToGoogleCalendarButton({
  event,
  className = '',
  variant = 'ghost',
  children,
  showHelper = false,
  ...rest
}) {
  const calendarUrl = event ? buildGoogleCalendarUrl(event) : null
  const chooserUrl = event ? buildGoogleCalendarAccountChooserUrl(event) : null
  if (!calendarUrl || !chooserUrl) return null

  const label = children || 'Add to Google Calendar'
  const linkClass = `${VARIANT_CLASS[variant] || VARIANT_CLASS.ghost} ${className}`.trim()
  const hintVisible = showHelper || variant === 'ghost' || variant === 'primary'

  return (
    <div className="add-to-gcal">
      <a
        href={chooserUrl}
        target="_blank"
        rel="noopener noreferrer"
        className={linkClass}
        {...rest}
      >
        {CALENDAR_ICON}
        {label}
      </a>
      {hintVisible ? (
        <p className="add-to-gcal__hint">
          {showHelper
            ? 'Google opens the calendar for the account currently active in your browser. To add this to another Google account, use '
            : null}
          <a href={chooserUrl} target="_blank" rel="noopener noreferrer" className="add-to-gcal__link">
            Choose Google account
          </a>
          {showHelper ? ' before saving.' : null}
        </p>
      ) : null}
      <style>{`
        .add-to-gcal { display: flex; flex-direction: column; gap: 8px; }
        .add-to-gcal__hint { margin: 0; font-size: 0.75rem; line-height: 1.45; color: #64748b; }
        .add-to-gcal__hint--compact { text-align: center; }
        .add-to-gcal__link { font-weight: 600; color: #4f46e5; text-decoration: underline; }
      `}</style>
    </div>
  )
}
