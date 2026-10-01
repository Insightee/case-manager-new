import { useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'

export function TherapistIepReminderBanner({ reminders = [], onDismiss }) {
  const [busyId, setBusyId] = useState(null)
  const [dismissed, setDismissed] = useState([])

  const visible = reminders.filter((r) => !dismissed.includes(r.notification_id))
  if (!visible.length) return null

  async function handleOpen(reminder) {
    setBusyId(reminder.notification_id)
    try {
      if (reminder.case_id) {
        await apiFetch(`/api/v1/therapist/iep-reminders/${reminder.case_id}/acknowledge`, { method: 'POST' })
      }
      setDismissed((prev) => [...prev, reminder.notification_id])
      onDismiss?.()
    } catch {
      /* still navigate */
    } finally {
      setBusyId(null)
    }
  }

  return (
    <section className="card therapist-iep-reminder" style={{ marginBottom: 16, padding: 16, borderColor: '#fcd34d', background: '#fffbeb' }}>
      <h3 style={{ margin: '0 0 8px', fontSize: '1rem' }}>IEP reminders</h3>
      <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
        {visible.map((item) => (
          <li key={item.notification_id}>
            <Link
              to={item.href}
              onClick={() => handleOpen(item)}
              className="therapist-pending-action therapist-pending-action--amber"
              style={{ display: 'flex', textDecoration: 'none', color: 'inherit' }}
            >
              <span className="therapist-pending-action__body" style={{ flex: 1 }}>
                <span className="therapist-pending-action__eyebrow">{item.title}</span>
                <strong className="therapist-pending-action__title">
                  {item.child_name || 'Client'}
                  {item.case_code ? ` · ${item.case_code}` : ''}
                </strong>
                <span className="therapist-pending-action__meta">{item.body}</span>
              </span>
              <span className="therapist-pending-action__chevron" aria-hidden>
                {busyId === item.notification_id ? '…' : '→'}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
