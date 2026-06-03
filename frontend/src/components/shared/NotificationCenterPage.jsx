import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMarkNotificationRead, useNotifications } from '../../hooks/useNotifications.js'
import { QueryState } from './QueryState.jsx'
import { resolveNotificationLink } from './notificationLinks.js'
import './notification-center.css'

function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const now = new Date()
  const diffMin = Math.floor((now - d) / 60000)
  if (diffMin < 1) return 'Just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffH = Math.floor(diffMin / 60)
  if (diffH < 24) return `${diffH}h ago`
  const diffD = Math.floor(diffH / 24)
  if (diffD < 7) return `${diffD}d ago`
  return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
}

export function NotificationCenterPage({ portal }) {
  const navigate = useNavigate()
  const [filter, setFilter] = useState('all')
  const unreadOnly = filter === 'unread'
  const { data, isLoading, isError, error, refetch } = useNotifications(unreadOnly)
  const markRead = useMarkNotificationRead()

  const notifications = data?.notifications || []
  const unreadCount = data?.unread_count ?? 0

  async function handleOpen(n) {
    if (!n.is_read) {
      markRead.mutate(n.id)
    }
    const href = resolveNotificationLink(n.entity_type, n.entity_id, portal)
    if (href) navigate(href)
  }

  return (
    <div className="notification-center">
      <header className="notification-center__header">
        <h2 className="notification-center__title">Notifications</h2>
        <p className="notification-center__subtitle">
          {unreadCount > 0 ? `${unreadCount} unread` : 'All caught up'}
        </p>
      </header>

      <div className="notification-center__filters" role="tablist" aria-label="Filter notifications">
        <button
          type="button"
          role="tab"
          aria-selected={filter === 'all'}
          className={filter === 'all' ? 'is-active' : ''}
          onClick={() => setFilter('all')}
        >
          All
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={filter === 'unread'}
          className={filter === 'unread' ? 'is-active' : ''}
          onClick={() => setFilter('unread')}
        >
          Unread{unreadCount > 0 ? ` (${unreadCount})` : ''}
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
          {notifications.map((n) => (
            <li key={n.id}>
              <button
                type="button"
                className={`notification-center__row${n.is_read ? ' is-read' : ' is-unread'}`}
                onClick={() => handleOpen(n)}
              >
                <span className="notification-center__dot" aria-hidden />
                <span className="notification-center__body">
                  <span className="notification-center__row-title">{n.title}</span>
                  {n.body ? <p className="notification-center__row-text">{n.body}</p> : null}
                  <time className="notification-center__row-time" dateTime={n.created_at}>
                    {fmtTime(n.created_at)}
                  </time>
                </span>
              </button>
            </li>
          ))}
        </ul>
      </QueryState>
    </div>
  )
}
