import { useSearchParams } from 'react-router-dom'
import { useParentPortal } from '../../hooks/useParentPortal.js'
import { ClientPortalLayout } from './ClientPortalLayout.jsx'
import { ClientSupportPage } from './ClientSupportPage.jsx'
import { ClientIncidentPage } from './ClientIncidentPage.jsx'
import './parent-support.css'

const TABS = [
  { id: 'support', label: 'Support Tickets' },
  { id: 'incidents', label: 'Incident Reports' },
]

export function ClientSupportHubPage() {
  const { cases } = useParentPortal()
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'support'

  function setTab(id) {
    setSearchParams({ tab: id }, { replace: true })
  }

  return (
    <ClientPortalLayout
      title="Support & incidents"
      subtitle="Open tickets with your care team or report an incident."
    >
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

      <div className="parent-support-hub__panel" hidden={tab !== 'support'}>
        <ClientSupportPage cases={cases} />
      </div>
      <div className="parent-support-hub__panel" hidden={tab !== 'incidents'}>
        <ClientIncidentPage cases={cases} />
      </div>
    </ClientPortalLayout>
  )
}
