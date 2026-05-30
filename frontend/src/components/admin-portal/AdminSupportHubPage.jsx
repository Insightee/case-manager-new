import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { tabsFromCapabilities } from '../../lib/supportAccess.js'
import { PoliciesBotButton } from '../support/PoliciesBotButton.jsx'
import { AdminTicketsPage } from './AdminTicketsPage.jsx'
import { AdminIncidentsPage } from './AdminIncidentsPage.jsx'
import { AdminSupportReportsPage } from './AdminSupportReportsPage.jsx'
import { AdminMobilePillTabs, AdminPageHeader, PortalTabBar } from './ui/index.js'

function normalizeSupportTab(raw) {
  if (raw === 'history') return 'reports'
  return raw
}

export function AdminSupportHubPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [capabilities, setCapabilities] = useState(null)
  const [capError, setCapError] = useState('')

  useEffect(() => {
    apiFetch('/api/v1/admin/support/capabilities')
      .then((data) => {
        setCapabilities(data)
        setCapError('')
      })
      .catch((err) => {
        setCapabilities(null)
        setCapError(err.message || 'Could not load support access')
      })
  }, [])

  const visibleTabs = useMemo(() => tabsFromCapabilities(capabilities), [capabilities])

  const tabParam = normalizeSupportTab(searchParams.get('tab'))
  const defaultTab = visibleTabs[0]?.id || 'tickets'
  const tab = visibleTabs.some((t) => t.id === tabParam) ? tabParam : defaultTab

  useEffect(() => {
    if (!tabParam || tab === tabParam) return
    const next = new URLSearchParams(searchParams)
    next.set('tab', tab)
    setSearchParams(next, { replace: true })
  }, [tab, tabParam, searchParams, setSearchParams])

  function setTab(id) {
    const next = new URLSearchParams(searchParams)
    next.set('tab', id)
    setSearchParams(next, { replace: true })
  }

  const canManageIncidents = capabilities?.can_manage_incidents === true

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="Support"
        title="Support & incidents"
        subtitle="Tickets, incident reports, and combined history."
        actions={<PoliciesBotButton />}
      />

      {capError ? <p className="admin-alert admin-alert--error">{capError}</p> : null}

      {visibleTabs.length === 0 && !capError ? (
        <p className="admin-muted">You do not have access to the support hub.</p>
      ) : null}

      {visibleTabs.length > 0 ? (
        <>
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
        </>
      ) : null}

      {tab === 'tickets' && visibleTabs.some((t) => t.id === 'tickets') ? (
        <div className="admin-hub-embedded">
          <AdminTicketsPage embedded />
        </div>
      ) : null}
      {tab === 'incidents' && visibleTabs.some((t) => t.id === 'incidents') ? (
        <div className="admin-hub-embedded">
          <AdminIncidentsPage embedded canManageIncidents={canManageIncidents} />
        </div>
      ) : null}
      {tab === 'reports' && visibleTabs.some((t) => t.id === 'reports') ? (
        <div className="admin-hub-embedded">
          <AdminSupportReportsPage embedded capabilities={capabilities} />
        </div>
      ) : null}
    </div>
  )
}
