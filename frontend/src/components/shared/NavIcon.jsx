const STROKE = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.75, strokeLinecap: 'round', strokeLinejoin: 'round' }

function Svg({ children, className }) {
  return (
    <svg className={className} viewBox="0 0 20 20" width="1.125rem" height="1.125rem" aria-hidden>
      {children}
    </svg>
  )
}

const ICONS = {
  dashboard: (
    <Svg>
      <rect x="3" y="3" width="6" height="6" rx="1" {...STROKE} />
      <rect x="11" y="3" width="6" height="6" rx="1" {...STROKE} />
      <rect x="3" y="11" width="6" height="6" rx="1" {...STROKE} />
      <rect x="11" y="11" width="6" height="6" rx="1" {...STROKE} />
    </Svg>
  ),
  people: (
    <Svg>
      <circle cx="7" cy="8" r="2.5" {...STROKE} />
      <circle cx="13.5" cy="9" r="2" {...STROKE} />
      <path d="M3 16c0-2.2 1.8-4 4-4M13 16c0-1.7 1.3-3 3-3" {...STROKE} />
    </Svg>
  ),
  user: (
    <Svg>
      <circle cx="10" cy="7" r="3" {...STROKE} />
      <path d="M4 17c0-3.3 2.7-6 6-6s6 2.7 6 6" {...STROKE} />
    </Svg>
  ),
  cases: (
    <Svg>
      <circle cx="10" cy="10" r="6.5" {...STROKE} />
      <circle cx="10" cy="10" r="2" {...STROKE} />
    </Svg>
  ),
  calendar: (
    <Svg>
      <rect x="4" y="5" width="12" height="11" rx="1.5" {...STROKE} />
      <path d="M4 8.5h12M7 3v3M13 3v3" {...STROKE} />
    </Svg>
  ),
  mail: (
    <Svg>
      <rect x="3" y="5" width="14" height="10" rx="1.5" {...STROKE} />
      <path d="M3 7l7 5 7-5" {...STROKE} />
    </Svg>
  ),
  ticket: (
    <Svg>
      <path d="M4 6h12v8H4V6zM8 6v8M12 10h.01" {...STROKE} />
    </Svg>
  ),
  grid: (
    <Svg>
      <path d="M4 5h12M4 10h12M4 15h12" {...STROKE} />
    </Svg>
  ),
  workbench: (
    <Svg>
      <circle cx="10" cy="10" r="6.5" {...STROKE} />
      <path d="M10 6v4l2.5 2.5" {...STROKE} />
    </Svg>
  ),
  reports: (
    <Svg>
      <rect x="5" y="3" width="10" height="14" rx="1.5" {...STROKE} />
      <path d="M8 8h4M8 11h4M8 14h2.5" {...STROKE} />
    </Svg>
  ),
  invoices: (
    <Svg>
      <path d="M6 4h8l2 3v9H6V4zM8 10h4M8 13h3" {...STROKE} />
    </Svg>
  ),
  iep: (
    <Svg>
      <path d="M7 4h6v12H7V4zM9 8h4M9 11h3" {...STROKE} />
      <path d="M11 3v2" {...STROKE} />
    </Svg>
  ),
  stethoscope: (
    <Svg>
      <path d="M6 4v6a4 4 0 008 0V4M10 14v2M8 16h4" {...STROKE} />
    </Svg>
  ),
  meetings: (
    <Svg>
      <rect x="3" y="4" width="14" height="12" rx="1.5" {...STROKE} />
      <path d="M7 9h6M7 12h4" {...STROKE} />
    </Svg>
  ),
  leave: (
    <Svg>
      <path d="M4 10h12M10 4v12" {...STROKE} />
      <rect x="6" y="6" width="8" height="8" rx="1" {...STROKE} />
    </Svg>
  ),
}

export function NavIcon({ name, className = 'app-sidebar__link-icon' }) {
  const icon = ICONS[name] ?? ICONS.dashboard
  return <span className={className}>{icon}</span>
}
