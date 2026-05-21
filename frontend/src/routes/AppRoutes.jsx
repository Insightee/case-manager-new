import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { PortalShell } from '../layouts/PortalShell.jsx'
import { LoginPage } from '../pages/LoginPage.jsx'
import { AdminDashboardPage } from '../components/admin-portal/AdminDashboardPage.jsx'
import { AdminCasesPage } from '../components/admin-portal/AdminCasesPage.jsx'
import { AdminCaseDetailPage } from '../components/admin-portal/AdminCaseDetailPage.jsx'
import { AdminSessionLogsPage } from '../components/admin-portal/AdminSessionLogsPage.jsx'
import { AdminReportsPage } from '../components/admin-portal/AdminReportsPage.jsx'
import { AdminInvoicesPage } from '../components/admin-portal/AdminInvoicesPage.jsx'
import { AdminPeoplePage } from '../components/admin-portal/AdminPeoplePage.jsx'
import { AdminIepPage } from '../components/admin-portal/AdminIepPage.jsx'
import { TherapistDashboardPage } from '../pages/TherapistDashboardPage.jsx'
import { MyCasesPage } from '../components/cases/MyCasesPage.jsx'
import { CaseDetailPage } from '../components/cases/CaseDetailPage.jsx'
import { DailyLogsPage } from '../components/daily-logs/DailyLogsPage.jsx'
import { MonthlyReportsPage } from '../components/monthly-reports/MonthlyReportsPage.jsx'
import { ReportEditPage } from '../components/reports/ReportEditPage.jsx'
import { InvoicesPage } from '../components/invoices/InvoicesPage.jsx'
import { TherapistProfilePage } from '../components/therapist/TherapistProfilePage.jsx'
import { TherapistTicketsPage } from '../components/therapist/TherapistTicketsPage.jsx'
import { TherapistSupportHubPage } from '../components/therapist/TherapistSupportHubPage.jsx'
import { TherapistLeavePage } from '../components/therapist/TherapistLeavePage.jsx'
import { TherapistSlotsPage } from '../components/therapist/TherapistSlotsPage.jsx'
import { ParentRoutes } from './ParentRoutes.jsx'
import { HRRoutes } from './HRRoutes.jsx'
import { InvitePage } from '../pages/InvitePage.jsx'
import { AdminSupportHubPage } from '../components/admin-portal/AdminSupportHubPage.jsx'
import { AdminTicketsPage } from '../components/admin-portal/AdminTicketsPage.jsx'
import { AdminIncidentsPage } from '../components/admin-portal/AdminIncidentsPage.jsx'
import { AdminTherapistProfilesPage } from '../components/admin-portal/AdminTherapistProfilesPage.jsx'
import { CaseManagerMeetingsPage } from '../components/admin-portal/CaseManagerMeetingsPage.jsx'
import { AdminWorkbenchPage } from '../components/admin-portal/AdminWorkbenchPage.jsx'
import { LeaveManagementPage } from '../components/hr-portal/LeaveManagementPage.jsx'

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
        <Route index element={<TherapistDashboardPage />} />
        <Route path="cases" element={<MyCasesPage />} />
        <Route path="cases/:caseId" element={<CaseDetailPage />} />
        <Route path="logs" element={<DailyLogsPage />} />
        <Route path="reports" element={<MonthlyReportsPage />} />
        <Route path="reports/edit/:reportId" element={<ReportEditPage />} />
        <Route path="invoices" element={<InvoicesPage />} />
        <Route path="support" element={<TherapistSupportHubPage />} />
        <Route path="tickets" element={<Navigate to="/therapist/support?tab=tickets" replace />} />
        <Route path="incidents" element={<Navigate to="/therapist/support?tab=incidents" replace />} />
        <Route path="leave" element={<TherapistLeavePage />} />
        <Route path="slots" element={<TherapistSlotsPage />} />
        <Route path="profile" element={<TherapistProfilePage />} />
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
        <Route path="workbench" element={<AdminWorkbenchPage />} />
        <Route path="cases" element={<AdminCasesPage />} />
        <Route path="cases/:caseId" element={<AdminCaseDetailPage />} />
        <Route path="logs" element={<AdminSessionLogsPage />} />
        <Route path="reports" element={<AdminReportsPage />} />
        <Route path="invoices" element={<AdminInvoicesPage />} />
        <Route path="iep" element={<AdminIepPage />} />
        <Route path="support" element={<AdminSupportHubPage />} />
        <Route path="tickets" element={<Navigate to="/admin/support?tab=tickets" replace />} />
        <Route path="incidents" element={<Navigate to="/admin/support?tab=incidents" replace />} />
        <Route path="people" element={<AdminPeoplePage />} />
        <Route path="users" element={<Navigate to="/admin/people?tab=staff" replace />} />
        <Route path="therapist-profiles" element={<AdminTherapistProfilesPage />} />
        <Route path="cm-meetings" element={<CaseManagerMeetingsPage />} />
        <Route path="leave" element={<LeaveManagementPage portal="admin" />} />
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
