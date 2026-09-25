import { Navigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext.jsx'
import { useAdminHome } from '../../hooks/useAdminHome.js'
import { isSpotOnlyUser } from '../../lib/spotPortal.js'
import { AdminDashboardPage } from './AdminDashboardPage.jsx'
import { SpotDashboardPage } from './SpotPortalPages.jsx'

/** Role-aware admin index: redirect CM/finance or render operations dashboard. */
export function AdminIndexPage() {
  const { user } = useAuth()
  const { data: roleHome, isLoading } = useAdminHome()

  if (isSpotOnlyUser(user)) {
    return <SpotDashboardPage />
  }

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
