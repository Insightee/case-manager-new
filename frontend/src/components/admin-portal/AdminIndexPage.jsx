import { Navigate } from 'react-router-dom'
import { useAdminHome } from '../../hooks/useAdminHome.js'
import { AdminDashboardPage } from './AdminDashboardPage.jsx'

/** Role-aware admin index: redirect CM/finance or render operations dashboard. */
export function AdminIndexPage() {
  const { data: roleHome, isLoading } = useAdminHome()

  if (isLoading) {
    return <p className="admin-muted" style={{ padding: '1.5rem' }}>Loading your dashboard…</p>
  }

  const landing = roleHome?.landing_route || '/admin'
  if (landing !== '/admin') {
    return <Navigate to={landing} replace />
  }

  return (
    <AdminDashboardPage
      dashboardVariant={roleHome?.dashboard_variant || 'operations'}
      primaryRole={roleHome?.role}
    />
  )
}
