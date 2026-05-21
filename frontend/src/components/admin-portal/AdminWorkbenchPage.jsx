import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { AdminPageHeader, AdminPanel } from './ui/index.js'
import './admin-reports.css'

const SECTION_META = {
  reports: { title: 'Reports to review', empty: 'No reports awaiting review.' },
  logs: { title: 'Session logs pending', empty: 'No logs pending approval.' },
  tickets: { title: 'Open support tickets', empty: 'No open tickets on your caseload.' },
  incidents: { title: 'Active incidents', empty: 'No active incidents.' },
  iep: { title: 'IEP attention', empty: 'All IEP documents up to date.' },
  meetings: { title: 'Upcoming CM meetings', empty: 'No scheduled meetings.' },
  reschedules: { title: 'Pending reschedules', empty: 'No reschedule requests awaiting confirmation.' },
}

function WorkbenchSection({ id, section }) {
  const meta = SECTION_META[id] || { title: id, empty: 'Nothing here.' }
  const items = section?.items || []
  return (
    <AdminPanel title={`${meta.title} (${section?.count ?? items.length})`} padded={false}>
      <div className="admin-panel__body">
        {items.length === 0 ? (
          <p className="admin-muted" style={{ padding: '12px 16px' }}>{meta.empty}</p>
        ) : (
          <ul className="admin-queue">
            {items.map((item) => (
              <li key={`${id}-${item.id}`} className="admin-queue__item">
                <div>
                  <p className="admin-queue__title">
                    {item.label || item.subject || item.title || `#${item.id}`}
                  </p>
                  <p className="admin-queue__meta">
                    {item.case_code ? `${item.case_code} · ` : ''}
                    {item.child_name || ''}
                    {item.status ? ` · ${item.status}` : ''}
                    {item.iep_status ? ` · ${item.iep_status}` : ''}
                    {item.scheduled_date ? ` · ${item.scheduled_date}` : ''}
                  </p>
                </div>
                <Link to={item.href} className="admin-btn admin-btn--ghost admin-btn--sm">
                  Open →
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </AdminPanel>
  )
}

export function AdminWorkbenchPage() {
  const { can } = useAuth()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiFetch('/api/v1/admin/workbench/summary')
      .then(setData)
      .catch(() => setData({ sections: {} }))
      .finally(() => setLoading(false))
  }, [])

  const sections = data?.sections || {}
  const order = ['reports', 'logs', 'reschedules', 'tickets', 'incidents', 'iep', 'meetings'].filter((id) => {
    if (id === 'tickets' && !can('ticket.manage')) return false
    if (id === 'incidents' && !can('incident.read_sensitive')) return false
    if (id === 'reports' && !can('monthly_report.approve')) return false
    if (id === 'logs' && !can('daily_log.review')) return false
    if (id === 'iep' && !can('iep.read')) return false
    return sections[id]
  })

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="Operations"
        title="My caseload"
        subtitle="Reports, logs, support, IEP, and meetings for cases in your region or assigned to you."
      />

      <p className="admin-muted" style={{ marginBottom: 16, fontSize: '0.875rem' }}>
        Scheduled CM supervision sessions are on{' '}
        <Link to="/admin/cm-meetings?queue=supervision" style={{ color: '#4f46e5', fontWeight: 600 }}>
          CM meetings (supervision filter)
        </Link>
        — not a separate supervisor request inbox.
      </p>

      {loading ? (
        <p className="admin-muted">Loading workbench…</p>
      ) : order.length === 0 ? (
        <p className="admin-muted">No work items right now.</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {order.map((id) => (
            <WorkbenchSection key={id} id={id} section={sections[id]} />
          ))}
        </div>
      )}
    </div>
  )
}
