import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Link, useNavigate } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { resolveNotificationLink } from './notificationLinks.js'

const DROPDOWN_WIDTH = 360
const DROPDOWN_MAX_HEIGHT = 520
const VIEWPORT_MARGIN = 12

/** Keep the panel fully inside the viewport (sidebar bell sits on the left). */
function computeDropdownPosition(btnEl) {
  const rect = btnEl.getBoundingClientRect()
  const width = Math.min(DROPDOWN_WIDTH, window.innerWidth - VIEWPORT_MARGIN * 2)
  const maxHeight = Math.min(window.innerHeight * 0.7, DROPDOWN_MAX_HEIGHT)

  let left = rect.left
  let top = rect.bottom + 8

  if (left + width > window.innerWidth - VIEWPORT_MARGIN) {
    left = window.innerWidth - width - VIEWPORT_MARGIN
  }
  if (left < VIEWPORT_MARGIN) {
    left = rect.right + 8
    if (left + width > window.innerWidth - VIEWPORT_MARGIN) {
      left = Math.max(VIEWPORT_MARGIN, window.innerWidth - width - VIEWPORT_MARGIN)
    }
  }

  if (top + maxHeight > window.innerHeight - VIEWPORT_MARGIN) {
    top = Math.max(VIEWPORT_MARGIN, rect.top - maxHeight - 8)
  }

  return { top, left, width, maxHeight }
}

function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const now = new Date()
  const diffMs = now - d
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'Just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffH = Math.floor(diffMin / 60)
  if (diffH < 24) return `${diffH}h ago`
  const diffD = Math.floor(diffH / 24)
  if (diffD < 7) return `${diffD}d ago`
  return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
}

export function NotificationBell({ portal }) {
  const [open, setOpen] = useState(false)
  const [data, setData] = useState({ notifications: [], unread_count: 0 })
  const [dropPos, setDropPos] = useState({ top: 0, left: 0, width: DROPDOWN_WIDTH, maxHeight: DROPDOWN_MAX_HEIGHT })
  const btnRef = useRef(null)
  const dropRef = useRef(null)
  const navigate = useNavigate()

  async function load() {
    try {
      const res = await apiFetch('/api/v1/notifications?limit=30')
      setData(res)
    } catch {
      setData({ notifications: [], unread_count: 0 })
    }
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 60000)
    return () => clearInterval(t)
  }, [])

  function openDropdown() {
    if (btnRef.current) {
      setDropPos(computeDropdownPosition(btnRef.current))
    }
    setOpen(true)
    load()
  }

  useEffect(() => {
    function onDoc(e) {
      if (
        dropRef.current && !dropRef.current.contains(e.target) &&
        btnRef.current && !btnRef.current.contains(e.target)
      ) {
        setOpen(false)
      }
    }
    if (open) document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  // Reposition on scroll/resize while open
  useEffect(() => {
    if (!open) return
    function reposition() {
      if (btnRef.current) {
        setDropPos(computeDropdownPosition(btnRef.current))
      }
    }
    window.addEventListener('scroll', reposition, true)
    window.addEventListener('resize', reposition)
    return () => {
      window.removeEventListener('scroll', reposition, true)
      window.removeEventListener('resize', reposition)
    }
  }, [open])

  async function markRead(id) {
    await apiFetch(`/api/v1/notifications/${id}/read`, { method: 'PATCH' })
    load()
  }

  async function markAll() {
    await apiFetch('/api/v1/notifications/read-all', { method: 'PATCH' })
    load()
  }

  async function handleClick(item) {
    setOpen(false)
    if (!item.is_read) await markRead(item.id)
    const path = resolveNotificationLink(item.entity_type, item.entity_id, portal)
    if (path) navigate(path)
  }

  const n = data.unread_count || 0
  const isAdmin = portal === 'admin' || portal === 'hr'

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        className="notification-bell__btn"
        aria-label={`Notifications${n ? `, ${n} unread` : ''}`}
        style={{ position: 'relative' }}
        onClick={(e) => {
          e.stopPropagation()
          if (open) setOpen(false)
          else openDropdown()
        }}
      >
        <span className="notification-bell__icon" aria-hidden>🔔</span>
        {n > 0 ? <span className="notification-bell__badge">{n > 99 ? '99+' : n}</span> : null}
      </button>

      {open
        ? createPortal(
            <div
              ref={dropRef}
              className={`notification-bell__dropdown${isAdmin ? ' notification-bell__dropdown--admin' : ''}`}
              role="dialog"
              aria-label="Notifications"
              style={{
                position: 'fixed',
                top: dropPos.top,
                left: dropPos.left,
                width: dropPos.width,
                maxHeight: dropPos.maxHeight,
                zIndex: 10000,
              }}
            >
              <div className="notification-bell__head">
                <span className="notification-bell__title">Notifications</span>
                {n > 0 ? (
                  <button type="button" className="notification-bell__link" onClick={markAll}>
                    Mark all read
                  </button>
                ) : null}
              </div>

              <ul className="notification-bell__list">
                {data.notifications?.length ? (
                  data.notifications.map((item) => {
                    const path = resolveNotificationLink(item.entity_type, item.entity_id, portal)
                    return (
                      <li key={item.id} className={`notification-bell__item ${item.is_read ? '' : 'is-unread'}`}>
                        <button
                          type="button"
                          className="notification-bell__item-btn"
                          onClick={() => handleClick(item)}
                        >
                          <div className="notification-bell__item-row">
                            <span className="notification-bell__item-title">{item.title}</span>
                            <span className="notification-bell__item-time">{fmtTime(item.created_at)}</span>
                          </div>
                          <span className="notification-bell__item-body">{item.body}</span>
                          {path ? (
                            <span className="notification-bell__item-cta">View →</span>
                          ) : null}
                        </button>
                      </li>
                    )
                  })
                ) : (
                  <li className="notification-bell__empty">No notifications</li>
                )}
              </ul>

              <div className="notification-bell__foot">
                <Link
                  to={
                    portal === 'parent'
                      ? '/parent/notifications'
                      : portal === 'therapist'
                        ? '/therapist/notifications'
                        : '/admin/notifications'
                  }
                  className="notification-bell__foot-link"
                  onClick={() => setOpen(false)}
                >
                  View all notifications
                </Link>
              </div>
            </div>,
            document.body,
          )
        : null}
    </>
  )
}
