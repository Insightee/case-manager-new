import { ReportHistoryCard } from './ReportHistoryCard.jsx'

export function ReportHistoryTimeline({ groups = [], onAction }) {
  if (!groups.length) {
    return (
      <p className="crt-empty-note">No report history matches these filters.</p>
    )
  }

  return (
    <section className="crt-history" aria-labelledby="crt-history-heading">
      <h2 id="crt-history-heading" className="crt-section-title">Report History</h2>
      <div className="crt-history__timeline">
        {groups.map((group) => (
          <div key={group.month} className="crt-history__group">
            <div className="crt-history__month">
              <span className="crt-history__node" aria-hidden="true" />
              <h3>{group.label}</h3>
            </div>
            <ul className="crt-history__items">
              {group.items.map((item) => (
                <li key={item.id}>
                  <ReportHistoryCard item={item} onAction={onAction} />
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  )
}
