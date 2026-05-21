import { useSearchParams } from 'react-router-dom'
import { ClientSupportPage } from './ClientSupportPage.jsx'
import { ClientIncidentPage } from './ClientIncidentPage.jsx'

const TABS = [
  { id: 'support', label: 'Support Tickets' },
  { id: 'incidents', label: 'Incident Reports' },
]

export function ClientSupportHubPage({ cases = [] }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'support'

  function setTab(id) {
    setSearchParams({ tab: id }, { replace: true })
  }

  return (
    <div>
      {/* Tab bar */}
      <div style={{
        display: 'flex',
        gap: 0,
        borderBottom: '2px solid #e2e8f0',
        marginBottom: 0,
        paddingLeft: '1rem',
        paddingTop: '1rem',
        background: '#fff',
      }}>
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            style={{
              padding: '10px 20px',
              fontSize: '0.875rem',
              fontWeight: 600,
              border: 'none',
              background: 'none',
              cursor: 'pointer',
              borderBottom: tab === t.id ? '2px solid #6366f1' : '2px solid transparent',
              color: tab === t.id ? '#4338ca' : '#64748b',
              marginBottom: -2,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ display: tab === 'support' ? 'block' : 'none' }}>
        <ClientSupportPage cases={cases} />
      </div>
      <div style={{ display: tab === 'incidents' ? 'block' : 'none' }}>
        <ClientIncidentPage cases={cases} />
      </div>
    </div>
  )
}
