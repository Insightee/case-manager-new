import { useSearchParams } from 'react-router-dom'
import { AdminPageHeader, PortalTabBar } from './ui/index.js'
import { TherapistPayoutsTab } from './TherapistPayoutsTab.jsx'
import { TherapistPayoutRaisePanel } from './TherapistPayoutRaisePanel.jsx'
import { TherapistPayoutQueuePanel } from './TherapistPayoutFinance.jsx'
import { AdminTherapistPayoutsDashboard } from './AdminTherapistPayoutsDashboard.jsx'

const SUB_TABS = [
  { id: 'queue', label: 'This month' },
  { id: 'records', label: 'All records' },
]

export function AdminTherapistPayoutsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const raw = searchParams.get('sub') || searchParams.get('therapist_sub') || 'queue'
  let mapped = raw
  if (raw === 'dashboard') mapped = 'queue'
  if (raw === 'payouts') mapped = searchParams.get('view') === 'queue' ? 'queue' : 'records'
  const activeSub = SUB_TABS.some((t) => t.id === mapped) ? mapped : 'queue'

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
        subtitle="System gross → add TDS → pay the net → mark paid. Raise an invoice if the therapist has not submitted one. Notes stay on the record."
      />

      <PortalTabBar
        className="admin-page__tabs-scroll"
        ariaLabel="Therapist payout sections"
        activeId={activeSub}
        onChange={setSub}
        tabs={SUB_TABS}
      />

      {activeSub === 'queue' ? (
        <>
          <AdminTherapistPayoutsDashboard />
          <TherapistPayoutRaisePanel />
          <TherapistPayoutQueuePanel />
        </>
      ) : (
        <TherapistPayoutsTab />
      )}
    </div>
  )
}
