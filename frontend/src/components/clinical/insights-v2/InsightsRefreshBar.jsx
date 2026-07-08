export function InsightsRefreshBar({ usage, onRefresh, isRefreshing, message }) {
  const remaining = usage?.remaining ?? usage?.cap ?? 2
  const cap = usage?.cap ?? 2

  return (
    <div className="ci-refresh-bar">
      <div className="ci-refresh-bar__text">
        <p className="ci-refresh-bar__title">Insights update automatically from session logs, IEP goals, and inputs.</p>
        <p className="ci-refresh-bar__subtext">
          "Refresh Insights" polishes wording using session logs, IEP goals, observation notes, parent inputs, and CM comments.
        </p>
      </div>
      <div className="ci-refresh-bar__actions">
        <span className="ci-refresh-bar__usage">
          {remaining}/{cap} refreshes left this week
        </span>
        <button type="button" className="ci-btn ci-btn--secondary" onClick={onRefresh} disabled={isRefreshing}>
          <span className="material-symbols-outlined" aria-hidden="true">
            autorenew
          </span>
          {isRefreshing ? 'Updating insights from latest logs…' : 'Refresh Insights'}
        </button>
      </div>
      {message ? <p className="ci-refresh-bar__message">{message}</p> : null}
    </div>
  )
}
