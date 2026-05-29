import { useSearchParams } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext.jsx'
import { PoliciesBotButton } from '../support/PoliciesBotButton.jsx'
import { AdminTicketsPage } from './AdminTicketsPage.jsx'
import { AdminIncidentsPage } from './AdminIncidentsPage.jsx'
import { AdminSupportReportsPage } from './AdminSupportReportsPage.jsx'
import { AdminMobilePillTabs, AdminPageHeader, PortalTabBar } from './ui/index.js'

const TABS = [
  { id: 'tickets', label: 'Tickets', perm: 'ticket.manage' },
  { id: 'incidents', label: 'Incidents', permAny: ['ticket.manage', 'incident.read_sensitive'] },
  { id: 'reports', label: 'History', permAny: ['ticket.manage', 'incident.read_sensitive'] },
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
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="Support"
        title="Support & incidents"
        subtitle="Tickets, incident reports, and combined history."
        actions={<PoliciesBotButton />}
      />

      <AdminMobilePillTabs
        ariaLabel="Support sections"
        activeId={tab}
        onChange={setTab}
        primaryIds={visibleTabs.map((t) => t.id)}
        overflowIds={[]}
        tabs={visibleTabs}
      />

      <PortalTabBar
        className="admin-page__tabs-scroll admin-desktop-only"
        ariaLabel="Support sections"
        activeId={tab}
        onChange={setTab}
        tabs={visibleTabs}
      />

      <div className="admin-hub-embedded" style={{ display: tab === 'tickets' ? 'block' : 'none' }}>
        <AdminTicketsPage embedded />
      </div>
      <div className="admin-hub-embedded" style={{ display: tab === 'incidents' ? 'block' : 'none' }}>
        <AdminIncidentsPage embedded />
      </div>
      <div className="admin-hub-embedded" style={{ display: tab === 'reports' ? 'block' : 'none' }}>
        <AdminSupportReportsPage embedded />
      </div>
    </div>
  )
}
