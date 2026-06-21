const DEFAULT_SOURCES = [
  'Session logs',
  'Active IEP',
  'Strategy pool',
  'Evidence guide',
]

export function InsightsSourcesFooter({ month, sources = DEFAULT_SOURCES }) {
  const monthLabel = month
    ? new Date(`${month}-01`).toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })
    : null

  return (
    <div className="insights-sources">
      <h4 className="insights-sources__title">Sources</h4>
      <ul className="insights-sources__list">
        {monthLabel ? <li>{monthLabel} session logs</li> : null}
        {sources.filter((s) => s !== 'Session logs').map((s) => (
          <li key={s}>{s}</li>
        ))}
      </ul>
    </div>
  )
}
