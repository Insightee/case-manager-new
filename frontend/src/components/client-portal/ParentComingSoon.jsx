import { ClientPortalLayout } from './ClientPortalLayout.jsx'

export function ParentComingSoon({ title, subtitle }) {
  return (
    <ClientPortalLayout title={title} subtitle={subtitle}>
      <p className="parent-coming-soon">Coming soon</p>
    </ClientPortalLayout>
  )
}
