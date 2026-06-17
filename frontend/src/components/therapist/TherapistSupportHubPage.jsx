import { useSearchParams } from 'react-router-dom'
import { TherapistTicketsPage } from './TherapistTicketsPage.jsx'
import { TherapistIncidentsPage } from './TherapistIncidentsPage.jsx'
import { TherapistMemosPage } from './TherapistMemosPage.jsx'
import '../client-portal/parent-support.css'

const TABS = [
  { id: 'tickets', label: 'Support Tickets' },
  { id: 'incidents', label: 'Incident Reports' },
  { id: 'memos', label: 'Memos Received' },
]

export function TherapistSupportHubPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'tickets'

  function setTab(id) {
    setSearchParams({ tab: id }, { replace: true })
  }

  return (
    <div>
      <nav className="parent-support-hub__tabs" aria-label="Support sections">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`parent-support-hub__tab${tab === t.id ? ' is-active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <div className="parent-support-hub__panel" hidden={tab !== 'tickets'}>
        <TherapistTicketsPage />
      </div>
      <div className="parent-support-hub__panel" hidden={tab !== 'incidents'}>
        <TherapistIncidentsPage />
      </div>
      <div className="parent-support-hub__panel" hidden={tab !== 'memos'}>
        <TherapistMemosPage />
      </div>
    </div>
  )
}
