import { useSearchParams } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext.jsx'
import { AdminTicketsPage } from './AdminTicketsPage.jsx'
import { AdminIncidentsPage } from './AdminIncidentsPage.jsx'
import { AdminSupportReportsPage } from './AdminSupportReportsPage.jsx'

const TABS = [
  { id: 'tickets', label: '✉ Support Tickets', perm: 'ticket.manage' },
  { id: 'incidents', label: '⚠ Incident Reports', perm: 'incident.read_sensitive' },
  { id: 'reports', label: '📊 Reports', permAny: ['ticket.manage', 'incident.read_sensitive'] },
]

export function AdminSupportHubPage() {
  const { can } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'tickets'

  function setTab(id) {
    setSearchParams({ tab: id }, { replace: true })
  }

  const visibleTabs = TABS.filter((t) => {
    if (t.permAny) return t.permAny.some((p) => can(p))
    return can(t.perm)
  })

  return (
    <div>
      {/* Tab bar — uses admin styling */}
      <div style={{
        display: 'flex',
        gap: 0,
        borderBottom: '2px solid #e2e8f0',
        marginBottom: 0,
        paddingLeft: 0,
        paddingTop: '1.5rem',
        paddingBottom: 0,
        background: 'transparent',
      }}>
        {visibleTabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            style={{
              padding: '10px 22px',
              fontSize: '0.875rem',
              fontWeight: 600,
              border: 'none',
              background: 'none',
              cursor: 'pointer',
              borderBottom: tab === t.id ? '2px solid #6366f1' : '2px solid transparent',
              color: tab === t.id ? '#4338ca' : '#64748b',
              marginBottom: -2,
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Content panels */}
      <div style={{ display: tab === 'tickets' ? 'block' : 'none' }}>
        <AdminTicketsPage />
      </div>
      <div style={{ display: tab === 'incidents' ? 'block' : 'none' }}>
        <AdminIncidentsPage />
      </div>
      <div style={{ display: tab === 'reports' ? 'block' : 'none' }}>
        <AdminSupportReportsPage />
      </div>
    </div>
  )
}
