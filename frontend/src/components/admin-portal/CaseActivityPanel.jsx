import { useCaseTimeline } from '../../hooks/useAdminHome.js'
import { QueryState } from '../shared/QueryState.jsx'
import './case-activity.css'

function formatWhen(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    const today = new Date()
    const sameDay = d.toDateString() === today.toDateString()
    if (sameDay) {
      return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
    }
    return d.toLocaleString(undefined, {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

export function CaseActivityPanel({ caseId }) {
  const { data, isLoading, isError, error, refetch } = useCaseTimeline(caseId)
  const items = data?.items || []

  return (
    <section className="admin-panel case-activity-panel">
      <header className="case-activity-panel__header">
        <h3 className="case-activity-panel__title">Activity timeline</h3>
        <p className="case-activity-panel__lead">
          Assignments, session log reviews, report workflow, and other changes on this case.
        </p>
      </header>
      <div className="case-activity-panel__body">
        <QueryState
          isLoading={isLoading}
          isError={isError}
          error={error}
          onRetry={() => refetch()}
          isEmpty={!isLoading && items.length === 0}
          emptyMessage="No activity recorded yet."
          skeletonRows={5}
        >
          <ul className="case-activity-timeline" aria-label="Case activity">
            {items.map((item) => {
              const source = item.source === 'assignment' ? 'assignment' : 'audit'
              return (
                <li
                  key={item.id}
                  className={`case-activity-timeline__item case-activity-timeline__item--${source}`}
                >
                  <div className="case-activity-timeline__head">
                    <strong className="case-activity-timeline__action">
                      {item.action_label || item.action}
                    </strong>
                    {item.created_at ? (
                      <time className="case-activity-timeline__time" dateTime={item.created_at}>
                        {formatWhen(item.created_at)}
                      </time>
                    ) : null}
                  </div>
                  <div className="case-activity-timeline__meta">
                    <span>{item.actor_name || (source === 'assignment' ? 'Assignment' : 'System')}</span>
                    {item.entity_type ? (
                      <span className="case-activity-timeline__chip">
                        {String(item.entity_type).replaceAll('_', ' ')}
                      </span>
                    ) : null}
                  </div>
                </li>
              )
            })}
          </ul>
        </QueryState>
      </div>
    </section>
  )
}
