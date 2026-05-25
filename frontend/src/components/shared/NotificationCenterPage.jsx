import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  useMarkAllNotificationsRead,
  useMarkNotificationRead,
  useNotifications,
} from '../../hooks/useNotifications.js'
import { QueryState } from './QueryState.jsx'
import { resolveNotificationLink } from './notificationLinks.js'

export function NotificationCenterPage({ portal }) {
  const [filter, setFilter] = useState('all')
  const unreadOnly = filter === 'unread'
  const { data, isLoading, isError, error, refetch } = useNotifications(unreadOnly)
  const markRead = useMarkNotificationRead()
  const markAll = useMarkAllNotificationsRead()

  const notifications = data?.notifications || []
  const centerPath =
    portal === 'parent'
      ? '/parent/notifications'
      : portal === 'therapist'
        ? '/therapist/notifications'
        : '/admin/notifications'

  return (
    <div className="notification-center">
      <header className="topbar">
        <div>
          <h2>Notifications</h2>
          <p>{data?.unread_count ? `${data.unread_count} unread` : 'You’re all caught up'}</p>
        </div>
        <div className="topbar-actions">
          {data?.unread_count > 0 ? (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => markAll.mutate()}
              disabled={markAll.isPending}
            >
              Mark all read
            </button>
          ) : null}
        </div>
      </header>

      <div className="notification-center__filters">
        <button
          type="button"
          className={filter === 'all' ? 'is-active' : ''}
          onClick={() => setFilter('all')}
        >
          All
        </button>
        <button
          type="button"
          className={filter === 'unread' ? 'is-active' : ''}
          onClick={() => setFilter('unread')}
        >
          Unread
        </button>
      </div>

      <QueryState
        isLoading={isLoading}
        isError={isError}
        error={error}
        onRetry={() => refetch()}
        isEmpty={!isLoading && notifications.length === 0}
        emptyMessage="No notifications yet."
      >
        <ul className="notification-center__list">
          {notifications.map((n) => {
            const href = resolveNotificationLink(n.entity_type, n.entity_id, portal)
            return (
              <li key={n.id} className={n.is_read ? '' : 'is-unread'}>
                <div className="notification-center__item">
                  <div>
                    <strong>{n.title}</strong>
                    {n.body ? <p>{n.body}</p> : null}
                    <time dateTime={n.created_at}>
                      {new Date(n.created_at).toLocaleString()}
                    </time>
                  </div>
                  <div className="notification-center__actions">
                    {href ? (
                      <Link to={href} className="btn btn-secondary btn-sm">
                        Open
                      </Link>
                    ) : null}
                    {!n.is_read ? (
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => markRead.mutate(n.id)}
                      >
                        Mark read
                      </button>
                    ) : null}
                  </div>
                </div>
              </li>
            )
          })}
        </ul>
      </QueryState>
      <p className="notification-center__foot">
        <Link to={centerPath}>Refresh list</Link>
      </p>
    </div>
  )
}
