import { useSearchParams } from 'react-router-dom'
import { TherapistTicketsPage } from './TherapistTicketsPage.jsx'
import { TherapistIncidentsPage } from './TherapistIncidentsPage.jsx'

const TABS = [
  { id: 'tickets', label: 'Support Tickets' },
  { id: 'incidents', label: 'Incident Reports' },
]

export function TherapistSupportHubPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'tickets'

  function setTab(id) {
    setSearchParams({ tab: id }, { replace: true })
  }

  return (
    <div>
      {/* Tab bar — identical to ClientSupportHubPage */}
      <div
        style={{
          display: 'flex',
          gap: 0,
          borderBottom: '2px solid #e2e8f0',
          marginBottom: 0,
          paddingLeft: '1rem',
          paddingTop: '1rem',
          background: '#fff',
        }}
      >
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
              transition: 'color 0.15s',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Content — keep both mounted, show active tab */}
      <div style={{ display: tab === 'tickets' ? 'block' : 'none' }}>
        <TherapistTicketsPage />
      </div>
      <div style={{ display: tab === 'incidents' ? 'block' : 'none' }}>
        <TherapistIncidentsPage />
      </div>
    </div>
  )
}
