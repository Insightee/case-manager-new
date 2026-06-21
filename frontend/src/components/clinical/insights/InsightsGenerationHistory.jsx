import { SNAPSHOT_STATUS_LABELS } from '../../../lib/insightsConstants.js'

function formatMonthLabel(month) {
  if (!month) return month
  return new Date(`${month}-01`).toLocaleDateString('en-IN', { month: 'short', year: 'numeric' })
}

export function InsightsGenerationHistory({ items, onOpen, emptyLabel = 'No snapshots yet.' }) {
  return (
    <details className="insights-history" open={Boolean(items?.length)}>
      <summary className="insights-history__summary">
        Last 6 months
        {items?.length ? <span className="insights-history__count">{items.length}</span> : null}
      </summary>
      {!items?.length ? (
        <p className="insights-history__empty">{emptyLabel}</p>
      ) : (
        <ul className="insights-history__list">
          {items.slice(0, 12).map((item) => (
            <li key={item.id} className="insights-history__row">
              <span>{formatMonthLabel(item.month)}</span>
              <span className="insights-history__status">
                {SNAPSHOT_STATUS_LABELS[item.status] || item.status}
              </span>
              <button type="button" className="clinical-text-action" onClick={() => onOpen(item)}>
                Open
              </button>
            </li>
          ))}
        </ul>
      )}
    </details>
  )
}
