import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'

/**
 * Derive a navigation path from entity_type + entity_id + portal.
 * Falls back to the portal home when no specific route is known.
 */
function resolveLink(entityType, entityId, portal) {
  if (!entityType) return null
  const et = entityType.toLowerCase()
  switch (et) {
    // --- therapy sessions / slots ---
    case 'therapist_slot':
    case 'slot':
      if (portal === 'parent') return '/parent/book'
      if (portal === 'therapist') return '/therapist/slots'
      return '/admin/cases'

    case 'session':
      if (portal === 'parent') return '/parent/session-logs'
      if (portal === 'therapist') return '/therapist/logs'
      return '/admin/logs'

    // --- invoices / billing ---
    case 'invoice':
    case 'client_invoice':
      if (portal === 'parent') return '/parent/billing'
      return '/admin/invoices'

    // --- cases ---
    case 'case':
      if (portal === 'parent' && entityId) return `/parent/cases/${entityId}`
      if (portal === 'admin' && entityId) return `/admin/cases/${entityId}`
      if (portal === 'therapist' && entityId) return `/therapist/cases/${entityId}`
      return portal === 'parent' ? '/parent' : '/admin/cases'

    // --- reports ---
    case 'monthly_report':
    case 'report':
      if (portal === 'parent') return '/parent/reports'
      if (portal === 'therapist') return '/therapist/reports'
      return '/admin/reports'

    // --- IEP ---
    case 'iep':
    case 'iep_document':
      if (portal === 'parent') return '/parent/reports?type=iep'
      return '/admin/iep'

    // --- leave ---
    case 'leave':
    case 'therapist_leave':
      if (portal === 'therapist') return '/therapist/leave'
      return '/hr/leave'

    // --- support tickets ---
    case 'support_ticket':
    case 'ticket':
      if (portal === 'parent') return '/parent/support'
      if (portal === 'therapist') return '/therapist/tickets'
      return '/admin/tickets'

    // --- incidents ---
    case 'incident':
      return '/admin/incidents'

    // --- case manager meetings ---
    case 'case_manager_meeting':
    case 'cm_meeting':
      if (portal === 'parent') return '/parent/session-logs'
      return '/admin/cm-meetings'

    // --- people / users ---
    case 'user':
    case 'invite_token':
      return '/admin/people'

    // --- payout ---
    case 'payout':
      return portal === 'therapist' ? '/therapist/invoices' : '/admin/invoices'

    default:
      return null
  }
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
  const [dropPos, setDropPos] = useState({ top: 0, right: 0 })
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

  // Position the fixed dropdown relative to the button
  function openDropdown() {
    if (btnRef.current) {
      const rect = btnRef.current.getBoundingClientRect()
      const rightGap = window.innerWidth - rect.right
      setDropPos({
        top: rect.bottom + 8,
        right: Math.max(8, rightGap),
      })
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
        const rect = btnRef.current.getBoundingClientRect()
        const rightGap = window.innerWidth - rect.right
        setDropPos({ top: rect.bottom + 8, right: Math.max(8, rightGap) })
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
    const path = resolveLink(item.entity_type, item.entity_id, portal)
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

      {open ? (
        <div
          ref={dropRef}
          className={`notification-bell__dropdown${isAdmin ? ' notification-bell__dropdown--admin' : ''}`}
          role="dialog"
          aria-label="Notifications"
          style={{
            position: 'fixed',
            top: dropPos.top,
            right: dropPos.right,
            zIndex: 9999,
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
                const path = resolveLink(item.entity_type, item.entity_id, portal)
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
            <button
              type="button"
              className="notification-bell__foot-link"
              onClick={() => {
                setOpen(false)
                navigate(
                  portal === 'parent' ? '/parent' :
                  portal === 'therapist' ? '/therapist' :
                  portal === 'hr' ? '/hr' : '/admin'
                )
              }}
            >
              Go to dashboard
            </button>
          </div>
        </div>
      ) : null}
    </>
  )
}
