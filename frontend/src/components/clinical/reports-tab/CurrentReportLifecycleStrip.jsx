/**
 * Stitch "Current Report Lifecycle" — 5 progress cards (bento).
 * Colored icon wells + status text + Updated/Next meta. No metric dashboard.
 */

const LIFECYCLE_META = {
  observation_report: { icon: 'check_circle', tone: 'green', fill: true },
  iep: { icon: 'description', tone: 'blue', fill: true },
  monthly_report: { icon: 'pending_actions', tone: 'amber', fill: false },
  progress_report: { icon: 'hourglass_empty', tone: 'muted', fill: false },
  cm_meeting_note: { icon: 'forum', tone: 'purple', fill: true },
}

function formatShortDate(iso) {
  if (!iso) return null
  if (iso === 'Completed' || iso === 'Not due') return iso
  try {
    const d = new Date(iso.includes('T') ? iso : `${iso}T00:00:00`)
    if (Number.isNaN(d.getTime())) return iso
    return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
  } catch {
    return iso
  }
}

function isMutedCard(item) {
  const s = String(item.status || item.status_label || '').toLowerCase()
  return s.includes('not due') || s === 'not_due'
}

export function CurrentReportLifecycleStrip({ items = [], onAction }) {
  if (!items.length) return null

  return (
    <section className="crt-lifecycle" aria-labelledby="crt-lifecycle-heading">
      <h2 id="crt-lifecycle-heading" className="crt-section-title">
        Current Report Lifecycle
      </h2>
      <div className="crt-lifecycle__grid">
        {items.map((item) => {
          const meta = LIFECYCLE_META[item.type] || { icon: 'description', tone: 'muted', fill: false }
          const muted = isMutedCard(item)
          const updated = formatShortDate(item.last_updated)
          const next = item.next_due_label || formatShortDate(item.due_date)
          const dueUrgent =
            String(item.status || '').includes('overdue') ||
            String(item.status_label || '').toLowerCase().includes('pending') ||
            String(item.status_label || '').toLowerCase().includes('due')

          return (
            <button
              key={item.type}
              type="button"
              className={`crt-lifecycle-card crt-lifecycle-card--${meta.tone}${muted ? ' crt-lifecycle-card--muted' : ''}`}
              onClick={() => onAction?.(item)}
            >
              <div className="crt-lifecycle-card__top">
                <div className={`crt-lifecycle-card__icon crt-lifecycle-card__icon--${meta.tone}`}>
                  <span
                    className="material-symbols-outlined"
                    aria-hidden="true"
                    style={meta.fill ? { fontVariationSettings: "'FILL' 1" } : undefined}
                  >
                    {meta.icon}
                  </span>
                </div>
                <p className="crt-lifecycle-card__eyebrow">
                  {item.type === 'iep' ? 'IEP Review' : item.title}
                </p>
                <p className={`crt-lifecycle-card__status crt-lifecycle-card__status--${meta.tone}`}>
                  {item.type === 'cm_meeting_note' && item.notes_count != null
                    ? `${item.notes_count} Note${item.notes_count === 1 ? '' : 's'}`
                    : item.status_label || item.status}
                </p>
              </div>
              <div className="crt-lifecycle-card__foot">
                {updated ? <p className="crt-lifecycle-card__meta-line">Updated: {updated}</p> : null}
                {next ? (
                  <p
                    className={`crt-lifecycle-card__meta-line${dueUrgent && !muted ? ' crt-lifecycle-card__meta-line--urgent' : ''}`}
                  >
                    {item.type === 'cm_meeting_note'
                      ? next
                      : `${item.type === 'monthly_report' && dueUrgent ? 'Due' : 'Next'}: ${next}`}
                  </p>
                ) : null}
              </div>
            </button>
          )
        })}
      </div>
    </section>
  )
}
