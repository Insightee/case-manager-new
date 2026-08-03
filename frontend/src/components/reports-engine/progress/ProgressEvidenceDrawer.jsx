export function ProgressEvidenceDrawer({ open, onClose, goalLabel, evidence, loading }) {
  if (!open) return null
  const summary = evidence?.evidence_summary || {}
  return (
    <aside className="fixed right-0 top-0 bottom-0 w-full max-w-md bg-surface-container-lowest border-l border-outline-variant/30 z-40 p-6 overflow-y-auto clinical-shadow">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-bold m-0">Evidence — {goalLabel || 'Goal'}</h2>
        <button type="button" className="min-h-[44px] px-3" onClick={onClose}>
          Close
        </button>
      </div>
      {loading ? <p className="text-sm text-on-surface-variant">Loading evidence…</p> : null}
      {summary.missing_evidence_warning ? (
        <p className="text-sm text-amber-800 mb-4">{summary.missing_evidence_warning}</p>
      ) : null}
      <dl className="text-sm space-y-3">
        <div>
          <dt className="text-xs font-bold uppercase font-mono text-outline">Sessions</dt>
          <dd className="mt-1">{summary.session_count ?? 0} approved in period</dd>
        </div>
        <div>
          <dt className="text-xs font-bold uppercase font-mono text-outline">Structured events</dt>
          <dd className="mt-1">{summary.evidence_event_count ?? 0}</dd>
        </div>
        {summary.strategies_used?.length ? (
          <div>
            <dt className="text-xs font-bold uppercase font-mono text-outline">Strategies</dt>
            <dd className="mt-1 flex flex-wrap gap-1">
              {summary.strategies_used.map((s) => (
                <span key={s} className="px-2 py-0.5 rounded-full bg-surface-container text-xs">{s}</span>
              ))}
            </dd>
          </div>
        ) : null}
        {summary.environments?.length ? (
          <div>
            <dt className="text-xs font-bold uppercase font-mono text-outline">Environments</dt>
            <dd className="mt-1">{summary.environments.join(', ')}</dd>
          </div>
        ) : null}
        {evidence?.sessions?.length ? (
          <div>
            <dt className="text-xs font-bold uppercase font-mono text-outline">Session dates</dt>
            <dd className="mt-1">
              <ul className="space-y-1">
                {evidence.sessions.map((s) => (
                  <li key={s.date}>{s.date}</li>
                ))}
              </ul>
            </dd>
          </div>
        ) : null}
      </dl>
    </aside>
  )
}
