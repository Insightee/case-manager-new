import { useCaseTimeline } from '../../hooks/useAdminHome.js'
import { QueryState } from '../shared/QueryState.jsx'

export function CaseActivityPanel({ caseId }) {
  const { data, isLoading, isError, error, refetch } = useCaseTimeline(caseId)
  const items = data?.items || []

  return (
    <section className="admin-panel" style={{ padding: 16 }}>
      <h3 style={{ marginTop: 0 }}>Activity</h3>
      <p className="admin-muted" style={{ marginBottom: 12 }}>
        Who changed what on this case — assignments and audit events.
      </p>
      <QueryState
        isLoading={isLoading}
        isError={isError}
        error={error}
        onRetry={() => refetch()}
        isEmpty={!isLoading && items.length === 0}
        emptyMessage="No activity recorded yet."
        skeletonRows={5}
      >
        <ul className="case-activity-timeline">
          {items.map((item) => (
            <li key={item.id} className="case-activity-timeline__item">
              <strong>{item.action_label || item.action}</strong>
              <span className="admin-muted">
                {item.actor_name || 'System'}
                {item.created_at ? ` · ${new Date(item.created_at).toLocaleString()}` : ''}
              </span>
              {item.source === 'audit' && item.entity_type ? (
                <span className="admin-chip">{item.entity_type}</span>
              ) : null}
            </li>
          ))}
        </ul>
      </QueryState>
    </section>
  )
}
