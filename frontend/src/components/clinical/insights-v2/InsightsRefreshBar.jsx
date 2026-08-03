export function InsightsRefreshBar({ usage, onRefresh, isRefreshing, message }) {
  const remaining = usage?.remaining ?? usage?.cap ?? 2
  const cap = usage?.cap ?? 2

  return (
    <div className="ci-refresh-bar">
      <div className="ci-refresh-bar__text">
        <p className="ci-refresh-bar__title">Generate your weekly insights</p>
        <p className="ci-refresh-bar__subtext">
          Insights load automatically from session logs and IEP goals. Tap generate to polish wording for this week.
        </p>
      </div>
      <div className="ci-refresh-bar__actions">
        <span className="ci-refresh-bar__usage">
          {remaining}/{cap} left this week
        </span>
        <button type="button" className="ci-btn ci-btn--primary" onClick={onRefresh} disabled={isRefreshing}>
          <span className="material-symbols-outlined" aria-hidden="true">
            autorenew
          </span>
          {isRefreshing ? 'Updating insights from latest logs…' : 'Generate weekly insights'}
        </button>
      </div>
      {message ? <p className="ci-refresh-bar__message">{message}</p> : null}
    </div>
  )
}
