import { useSearchParams } from 'react-router-dom'
import { AdminPageHeader, PortalTabBar } from './ui/index.js'
import { AdminTherapistPayoutsDashboard } from './AdminTherapistPayoutsDashboard.jsx'
import { TherapistPayoutsTab } from './TherapistPayoutsTab.jsx'

const SUB_TABS = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'payouts', label: 'Payout invoices' },
]

export function AdminTherapistPayoutsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const sub =
    searchParams.get('sub') ||
    searchParams.get('therapist_sub') ||
    'dashboard'
  const activeSub = SUB_TABS.some((t) => t.id === sub) ? sub : 'dashboard'

  function setSub(id) {
    const next = new URLSearchParams(searchParams)
    next.set('sub', id)
    next.delete('therapist_sub')
    setSearchParams(next)
  }

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="Finance"
        title="Therapist payouts"
        subtitle="Review submitted therapist invoices, approve payouts, and record payments after leave adjustments."
      />

      <PortalTabBar
        className="admin-page__tabs-scroll"
        ariaLabel="Therapist payout sections"
        activeId={activeSub}
        onChange={setSub}
        tabs={SUB_TABS}
      />

      {activeSub === 'payouts' ? <TherapistPayoutsTab /> : <AdminTherapistPayoutsDashboard />}
    </div>
  )
}
