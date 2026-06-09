/**
 * Recent case status-change requests (operational timeline).
 */
export function CaseOperationalTimeline({ history = [] }) {
  const events = (history || []).slice(0, 5)
  if (!events.length) {
    return (
      <section className="ic-case-panel">
        <h3>Operational timeline</h3>
        <p className="ic-case-panel__hint">No status change requests yet for this case.</p>
      </section>
    )
  }

  return (
    <section className="ic-case-panel">
      <h3>Operational timeline</h3>
      <ol className="ic-case-timeline">
        {events.map((ev) => {
          const status = (ev.status || '').toUpperCase()
          const label =
            status === 'PENDING'
              ? 'Requested'
              : status === 'APPROVED'
                ? 'Approved'
                : status === 'REJECTED'
                  ? 'Rejected'
                  : status || 'Update'
          const when = ev.created_at || ev.requested_at || ''
          const whenLabel = when ? String(when).slice(0, 10) : ''
          const detail = ev.to_status
            ? `${ev.from_status || '—'} → ${ev.to_status}`
            : ev.toStatus
              ? `${ev.fromStatus || '—'} → ${ev.toStatus}`
              : ''
          return (
            <li key={ev.id || `${when}-${detail}`} className="ic-case-timeline__item">
              <span className="ic-case-timeline__dot" aria-hidden />
              <div className="ic-case-timeline__body">
                <strong>{label}</strong>
                {detail ? <span>{detail}</span> : null}
                {whenLabel ? <time dateTime={whenLabel}>{whenLabel}</time> : null}
              </div>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
