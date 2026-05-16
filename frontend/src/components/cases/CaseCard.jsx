import { StatusBadge } from './StatusBadge.jsx'

function MenuDots() {
  return (
    <button type="button" className="ic-card__menu" aria-label="Case actions">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
        <circle cx="12" cy="5" r="2" />
        <circle cx="12" cy="12" r="2" />
        <circle cx="12" cy="19" r="2" />
      </svg>
    </button>
  )
}

function IconPlus() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden>
      <path d="M12 5v14M5 12h14" />
    </svg>
  )
}

function IconEye() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  )
}

function IconReport() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6M12 18v-6M9 15h6" />
    </svg>
  )
}

function IconBell() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 7-3 14h18c0-7-3-7-3-14M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  )
}

function IconInfo() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 16v-4M12 8h.01" />
    </svg>
  )
}

function CardActions({ showSubmitReport, showSetReminder }) {
  return (
    <div className="ic-card__actions">
      <button type="button" className="ic-btn ic-btn--primary">
        <IconPlus />
        Add Log
      </button>
      <button type="button" className="ic-btn ic-btn--ghost">
        <IconEye />
        View Case
      </button>
      {showSubmitReport ? (
        <button type="button" className="ic-btn ic-btn--accent">
          <IconReport />
          Submit Report
        </button>
      ) : null}
      {showSetReminder ? (
        <button type="button" className="ic-btn ic-btn--muted">
          <IconBell />
          Set Reminder
        </button>
      ) : null}
    </div>
  )
}

export function CaseCard({ data }) {
  const accent = data.borderAccent || 'yellow'

  if (data.layout === 'standard') {
    return (
      <article className={`ic-card ic-card--accent-${accent}`}>
        <div className="ic-card__top">
          <span className="ic-card__id">{data.caseId}</span>
          <div className="ic-card__top-right">
            {data.critical ? <span className="ic-critical" title="Urgent" /> : null}
            <MenuDots />
          </div>
        </div>
        <StatusBadge variant={data.badgeVariant}>{data.stage}</StatusBadge>
        <h3 className="ic-card__name">{data.child}</h3>
        <p className="ic-card__service">{data.service}</p>
        {data.due ? (
          <p className="ic-card__due">
            <IconInfo />
            {data.due}
          </p>
        ) : null}
        <CardActions showSubmitReport={!!data.showSubmitReport} showSetReminder={false} />
      </article>
    )
  }

  if (data.layout === 'split') {
    return (
      <article className={`ic-card ic-card--accent-${accent}`}>
        <div className="ic-card__top">
          <span className="ic-card__id">{data.caseId}</span>
          <div className="ic-card__top-right">
            {data.critical ? <span className="ic-critical" title="Urgent" /> : null}
            <MenuDots />
          </div>
        </div>
        <h3 className="ic-card__name">{data.child}</h3>
        <div className="ic-card__split">
          <div className="ic-card__split-col">
            <StatusBadge variant={data.left.badgeVariant}>{data.left.tag}</StatusBadge>
            <p className="ic-card__service">{data.left.service}</p>
          </div>
          <div className="ic-card__split-col ic-card__split-col--muted">
            <StatusBadge variant={data.right.badgeVariant}>{data.right.title}</StatusBadge>
            <p className="ic-card__due ic-card__due--plain">
              <IconInfo />
              {data.right.note}
            </p>
          </div>
        </div>
        <CardActions
          showSubmitReport={!!data.showSubmitReport}
          showSetReminder={!!data.showSetReminder}
        />
      </article>
    )
  }

  if (data.layout === 'dual') {
    return (
      <article className={`ic-card ic-card--accent-${accent}`}>
        <div className="ic-card__dual">
          <div className="ic-card__dual-col">
            <div className="ic-card__top">
              <span className="ic-card__id">{data.left.caseId}</span>
              <MenuDots />
            </div>
            <StatusBadge variant={data.left.badgeVariant}>{data.left.stage}</StatusBadge>
            <h3 className="ic-card__name">{data.left.child}</h3>
            <p className="ic-card__service">{data.left.service}</p>
            {data.left.due ? (
              <p className="ic-card__due">
                <IconInfo />
                {data.left.due}
              </p>
            ) : null}
          </div>
          <div className="ic-card__dual-col">
            <div className="ic-card__top">
              <span className="ic-card__id">{data.right.caseId}</span>
              <MenuDots />
            </div>
            <StatusBadge variant={data.right.badgeVariant}>{data.right.stage}</StatusBadge>
            <h3 className="ic-card__name">{data.right.child}</h3>
            <p className="ic-card__service">{data.right.service}</p>
            {data.right.due ? (
              <p className="ic-card__due">
                <IconInfo />
                {data.right.due}
              </p>
            ) : null}
          </div>
        </div>
        <CardActions showSubmitReport={!!data.showSubmitReport} showSetReminder={false} />
      </article>
    )
  }

  if (data.layout === 'completed') {
    return (
      <article className={`ic-card ic-card--accent-${accent}`}>
        <div className="ic-card__top">
          <span className="ic-card__id">{data.caseId}</span>
          <MenuDots />
        </div>
        <h3 className="ic-card__name">{data.child}</h3>
        <p className="ic-card__service">{data.service}</p>
        <div className="ic-card__panels">
          {data.panels.map((p, i) => (
            <div key={i} className="ic-panel ic-panel--teal">
              {p.check ? (
                <span className="ic-panel__check" aria-hidden>
                  {'\u2713'}
                </span>
              ) : null}
              <span className="ic-panel__text">{p.label}</span>
            </div>
          ))}
        </div>
        <div className="ic-card__actions ic-card__actions--pair">
          <button type="button" className="ic-btn ic-btn--ghost ic-btn--ghost-wide">
            <IconEye />
            View Case
          </button>
          <button type="button" className="ic-btn ic-btn--muted">
            <IconBell />
            Set Reminder
          </button>
        </div>
      </article>
    )
  }

  return null
}
