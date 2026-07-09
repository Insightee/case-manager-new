import { ClientPortalLayout } from './ClientPortalLayout.jsx'
import { PortalComingSoon } from '../shared/PortalComingSoon.jsx'

const PARENT_COPY = {
  Reports: {
    variant: 'parentReports',
    subtitle: 'Monthly reports, IEP plans, and documents shared by your care team.',
  },
  Billing: {
    variant: 'parentBilling',
    subtitle: 'Invoices, payments, and package balances for your care plans.',
  },
}

export function ParentComingSoon({ title, subtitle }) {
  const preset = PARENT_COPY[title] || {}
  return (
    <ClientPortalLayout title={title} subtitle={subtitle || preset.subtitle}>
      <PortalComingSoon variant={preset.variant || 'generic'} className="parent-coming-soon-panel" />
    </ClientPortalLayout>
  )
}
