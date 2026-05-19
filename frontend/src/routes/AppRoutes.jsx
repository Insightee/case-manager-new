import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { PortalShell } from '../layouts/PortalShell.jsx'
import { LoginPage } from '../pages/LoginPage.jsx'
import { AdminDashboardPage } from '../components/admin-portal/AdminDashboardPage.jsx'
import { AdminCasesPage } from '../components/admin-portal/AdminCasesPage.jsx'
import { AdminCaseDetailPage } from '../components/admin-portal/AdminCaseDetailPage.jsx'
import { AdminSessionLogsPage } from '../components/admin-portal/AdminSessionLogsPage.jsx'
import { AdminReportReviewPage } from '../components/admin-portal/AdminReportReviewPage.jsx'
import { AdminInvoicesPage } from '../components/admin-portal/AdminInvoicesPage.jsx'
import { AdminUsersPage } from '../components/admin-portal/AdminUsersPage.jsx'
import { AdminIepPage } from '../components/admin-portal/AdminIepPage.jsx'
import { AdminTicketsPage } from '../components/admin-portal/AdminTicketsPage.jsx'
import { TherapistRoutes } from './TherapistRoutes.jsx'
import { ParentRoutes } from './ParentRoutes.jsx'
import { HRRoutes } from './HRRoutes.jsx'
import { InvitePage } from '../pages/InvitePage.jsx'
import { AdminIncidentsPage } from '../components/admin-portal/AdminIncidentsPage.jsx'
import { AdminTherapistProfilesPage } from '../components/admin-portal/AdminTherapistProfilesPage.jsx'

function PortalRedirect() {
  const { portal, loading } = useAuth()
  if (loading) return <p style={{ padding: '2rem' }}>Loading…</p>
  if (portal === 'admin') return <Navigate to="/admin" replace />
  if (portal === 'parent') return <Navigate to="/parent" replace />
  if (portal === 'therapist') return <Navigate to="/therapist" replace />
  if (portal === 'hr') return <Navigate to="/hr" replace />
  return <Navigate to="/login" replace />
}

function Protected({ portal, children }) {
  const { user, portal: current, loading } = useAuth()
  if (loading) return <p style={{ padding: '2rem' }}>Loading…</p>
  if (!user) return <Navigate to="/login" replace />
  if (current !== portal) return <Navigate to="/" replace />
  return children
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/invite/:token" element={<InvitePage />} />
      <Route path="/" element={<PortalRedirect />} />

      <Route
        path="/therapist/*"
        element={
          <Protected portal="therapist">
            <PortalShell portal="therapist" />
          </Protected>
        }
      >
        <Route path="*" element={<TherapistRoutes />} />
      </Route>

      <Route
        path="/parent/*"
        element={
          <Protected portal="parent">
            <PortalShell portal="parent" />
          </Protected>
        }
      >
        <Route path="*" element={<ParentRoutes />} />
      </Route>

      <Route
        path="/admin/*"
        element={
          <Protected portal="admin">
            <PortalShell portal="admin" />
          </Protected>
        }
      >
        <Route index element={<AdminDashboardPage />} />
        <Route path="cases" element={<AdminCasesPage />} />
        <Route path="cases/:caseId" element={<AdminCaseDetailPage />} />
        <Route path="logs" element={<AdminSessionLogsPage />} />
        <Route path="reports" element={<AdminReportReviewPage />} />
        <Route path="invoices" element={<AdminInvoicesPage />} />
        <Route path="iep" element={<AdminIepPage />} />
        <Route path="tickets" element={<AdminTicketsPage />} />
        <Route path="incidents" element={<AdminIncidentsPage />} />
        <Route path="users" element={<AdminUsersPage />} />
        <Route path="therapist-profiles" element={<AdminTherapistProfilesPage />} />
      </Route>

      <Route
        path="/hr/*"
        element={
          <Protected portal="hr">
            <PortalShell portal="hr" />
          </Protected>
        }
      >
        <Route path="*" element={<HRRoutes />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
