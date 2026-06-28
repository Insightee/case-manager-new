export function InsightsPreviewStats({ preview, loading, error }) {
  if (loading) {
    return <p className="insights-preview-stats-bar insights-preview-stats-bar--loading">Loading session data…</p>
  }
  if (error) {
    return <p className="insights-preview-stats-bar insights-preview-stats-bar--error">{error}</p>
  }
  if (!preview) return null

  const items = [
    { value: preview.sessions_available ?? 0, label: 'Sessions available' },
    { value: preview.active_goals_count ?? 0, label: 'Active goals' },
    { value: preview.strategies_used_count ?? 0, label: 'Strategies used' },
    { value: preview.logs_missing_details ?? 0, label: 'Logs need details' },
  ]

  return (
    <ul className="insights-preview-stats-bar" aria-label="Monthly data preview">
      {items.map((item) => (
        <li key={item.label} className="insights-preview-stats-bar__item">
          <span className="insights-preview-stats-bar__value">{item.value}</span>
          <span className="insights-preview-stats-bar__label">{item.label}</span>
        </li>
      ))}
    </ul>
  )
}
