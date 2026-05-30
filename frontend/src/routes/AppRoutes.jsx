import { lazy, Suspense, useEffect, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { apiFetch } from '../lib/apiClient.js'
import { PortalShell } from '../layouts/PortalShell.jsx'
import { LoginPage } from '../pages/LoginPage.jsx'
import { InvitePage } from '../pages/InvitePage.jsx'
import { ForgotPasswordPage } from '../pages/ForgotPasswordPage.jsx'
import { ResetPasswordPage } from '../pages/ResetPasswordPage.jsx'
import { TherapistDashboardPage } from '../pages/TherapistDashboardPage.jsx'
import { MyCasesPage } from '../components/cases/MyCasesPage.jsx'
import { CaseDetailPage } from '../components/cases/CaseDetailPage.jsx'
import { DailyLogsPage } from '../components/daily-logs/DailyLogsPage.jsx'
import { MonthlyReportsPage } from '../components/monthly-reports/MonthlyReportsPage.jsx'
import { InvoicesPage } from '../components/invoices/InvoicesPage.jsx'
import { TherapistProfilePage } from '../components/therapist/TherapistProfilePage.jsx'
import { TherapistSupportHubPage } from '../components/therapist/TherapistSupportHubPage.jsx'
import { TherapistLeavePage } from '../components/therapist/TherapistLeavePage.jsx'
import { TherapistSlotsPage } from '../components/therapist/TherapistSlotsPage.jsx'
import { NotificationCenterPage } from '../components/shared/NotificationCenterPage.jsx'
import { RouteLoading } from '../components/shared/RouteLoading.jsx'
import { PortalRouteError } from '../components/shared/PortalRouteError.jsx'

const ReportEditPage = lazy(() =>
  import('../components/reports/ReportEditPage.jsx').then((m) => ({ default: m.ReportEditPage }))
)
const ParentPortalLayout = lazy(() =>
  import('./ParentPortalLayout.jsx').then((m) => ({ default: m.ParentPortalLayout }))
)
const ParentDashboardRoute = lazy(() =>
  import('./ParentRoutes.jsx').then((m) => ({ default: m.ParentDashboardRoute }))
)
const ClientBookAppointmentPage = lazy(() =>
  import('../components/client-portal/ClientBookAppointmentPage.jsx').then((m) => ({
    default: m.ClientBookAppointmentPage,
  }))
)
const ClientSessionLogsPage = lazy(() =>
  import('../components/client-portal/ClientSessionLogsPage.jsx').then((m) => ({
    default: m.ClientSessionLogsPage,
  }))
)
const ParentReportsPage = lazy(() =>
  import('../components/client-portal/ParentReportsPage.jsx').then((m) => ({ default: m.ParentReportsPage }))
)
const ParentBillingPage = lazy(() =>
  import('../components/client-portal/ParentBillingPage.jsx').then((m) => ({ default: m.ParentBillingPage }))
)
const ParentProfilePage = lazy(() =>
  import('../components/client-portal/ParentProfilePage.jsx').then((m) => ({ default: m.ParentProfilePage }))
)
const ClientSupportHubPage = lazy(() =>
  import('../components/client-portal/ClientSupportHubPage.jsx').then((m) => ({ default: m.ClientSupportHubPage }))
)
const ParentCaseDetailPage = lazy(() =>
  import('../components/client-portal/ParentCaseDetailPage.jsx').then((m) => ({ default: m.ParentCaseDetailPage }))
)
const HRMemosPage = lazy(() =>
  import('../components/hr-portal/HRMemosPage.jsx').then((m) => ({ default: m.HRMemosPage }))
)
const HRCasesPage = lazy(() =>
  import('../components/hr-portal/HRCasesPage.jsx').then((m) => ({ default: m.HRCasesPage }))
)
const AdminIndexPage = lazy(() =>
  import('../components/admin-portal/AdminIndexPage.jsx').then((m) => ({ default: m.AdminIndexPage }))
)
const AdminCasesPage = lazy(() =>
  import('../components/admin-portal/AdminCasesPage.jsx').then((m) => ({ default: m.AdminCasesPage }))
)
const AdminCaseDetailPage = lazy(() =>
  import('../components/admin-portal/AdminCaseDetailPage.jsx').then((m) => ({ default: m.AdminCaseDetailPage }))
)
const AdminSessionLogsPage = lazy(() =>
  import('../components/admin-portal/AdminSessionLogsPage.jsx').then((m) => ({ default: m.AdminSessionLogsPage }))
)
const AdminReportsPage = lazy(() =>
  import('../components/admin-portal/AdminReportsPage.jsx').then((m) => ({ default: m.AdminReportsPage }))
)
const AdminReportViewPage = lazy(() =>
  import('../components/admin-portal/AdminReportViewPage.jsx').then((m) => ({ default: m.AdminReportViewPage }))
)
const AdminInvoicesPage = lazy(() =>
  import('../components/admin-portal/AdminInvoicesPage.jsx').then((m) => ({ default: m.AdminInvoicesPage }))
)
const AdminTherapistPayoutsPage = lazy(() =>
  import('../components/admin-portal/AdminTherapistPayoutsPage.jsx').then((m) => ({
    default: m.AdminTherapistPayoutsPage,
  }))
)
const AdminClientInvoicePage = lazy(() =>
  import('../components/admin-portal/AdminClientInvoicePage.jsx').then((m) => ({ default: m.AdminClientInvoicePage }))
)
const InvoiceComposer = lazy(() =>
  import('../components/admin-portal/InvoiceComposer.jsx').then((m) => ({ default: m.InvoiceComposer }))
)
const AdminPeoplePage = lazy(() =>
  import('../components/admin-portal/AdminPeoplePage.jsx').then((m) => ({ default: m.AdminPeoplePage }))
)
const AdminIepPage = lazy(() =>
  import('../components/admin-portal/AdminIepPage.jsx').then((m) => ({ default: m.AdminIepPage }))
)
const AdminSupportHubPage = lazy(() =>
  import('../components/admin-portal/AdminSupportHubPage.jsx').then((m) => ({ default: m.AdminSupportHubPage }))
)
const AdminHrReportsPage = lazy(() =>
  import('../components/admin-portal/AdminHrReportsPage.jsx').then((m) => ({ default: m.AdminHrReportsPage }))
)
const AdminTherapistProfilesPage = lazy(() =>
  import('../components/admin-portal/AdminTherapistProfilesPage.jsx').then((m) => ({
    default: m.AdminTherapistProfilesPage,
  }))
)
const AdminServiceCategoriesPage = lazy(() =>
  import('../components/admin-portal/AdminServiceCategoriesPage.jsx').then((m) => ({
    default: m.AdminServiceCategoriesPage,
  }))
)
const AdminStaffProfilePage = lazy(() =>
  import('../components/admin-portal/AdminStaffProfilePage.jsx').then((m) => ({
    default: m.AdminStaffProfilePage,
  }))
)
const AdminClientProfilesPage = lazy(() =>
  import('../components/admin-portal/AdminClientProfilesPage.jsx').then((m) => ({
    default: m.AdminClientProfilesPage,
  }))
)
const CaseManagerMeetingsPage = lazy(() =>
  import('../components/admin-portal/CaseManagerMeetingsPage.jsx').then((m) => ({
    default: m.CaseManagerMeetingsPage,
  }))
)
const AdminWorkbenchPage = lazy(() =>
  import('../components/admin-portal/AdminWorkbenchPage.jsx').then((m) => ({ default: m.AdminWorkbenchPage }))
)
const AdminCaseManagerHomePage = lazy(() =>
  import('../components/admin-portal/AdminCaseManagerHomePage.jsx').then((m) => ({
    default: m.AdminCaseManagerHomePage,
  }))
)
const LeaveManagementPage = lazy(() =>
  import('../components/hr-portal/LeaveManagementPage.jsx').then((m) => ({ default: m.LeaveManagementPage }))
)

function RouteFallback() {
  return <RouteLoading />
}

function Lazy({ children }) {
  return <Suspense fallback={<RouteFallback />}>{children}</Suspense>
}

function PortalRedirect() {
  const { portal, loading } = useAuth()
  const [adminLanding, setAdminLanding] = useState('/admin')

  useEffect(() => {
    if (portal !== 'admin') return
    let cancelled = false
    apiFetch('/api/v1/admin/home')
      .then((home) => {
        if (!cancelled && home?.landing_route) setAdminLanding(home.landing_route)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [portal])

  if (loading) return <RouteLoading />
  if (portal === 'admin') return <Navigate to={adminLanding} replace />
  if (portal === 'parent') return <Navigate to="/parent" replace />
  if (portal === 'therapist') return <Navigate to="/therapist" replace />
  return <Navigate to="/login" replace />
}

function Protected({ portal, children }) {
  const { user, portal: current, loading } = useAuth()
  if (loading) return <RouteLoading />
  if (!user) return <Navigate to="/login" replace />
  if (current !== portal) return <Navigate to="/" replace />
  return children
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password/:token" element={<ResetPasswordPage />} />
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
        <Route
          path="reports/edit/:reportId"
          element={
            <Lazy>
              <ReportEditPage />
            </Lazy>
          }
        />
        <Route path="invoices" element={<InvoicesPage />} />
        <Route path="support" element={<TherapistSupportHubPage />} />
        <Route path="tickets" element={<Navigate to="/therapist/support?tab=tickets" replace />} />
        <Route path="incidents" element={<Navigate to="/therapist/support?tab=incidents" replace />} />
        <Route path="leave" element={<TherapistLeavePage />} />
        <Route path="slots" element={<TherapistSlotsPage />} />
        <Route
          path="cm-meetings"
          element={
            <Lazy>
              <CaseManagerMeetingsPage portal="therapist" />
            </Lazy>
          }
        />
        <Route path="profile" element={<TherapistProfilePage />} />
        <Route path="notifications" element={<NotificationCenterPage portal="therapist" />} />
      </Route>

      <Route
        path="/parent"
        element={
          <Protected portal="parent">
            <PortalShell portal="parent" />
          </Protected>
        }
        errorElement={<PortalRouteError />}
      >
        <Route
          element={
            <Lazy>
              <ParentPortalLayout />
            </Lazy>
          }
          errorElement={<PortalRouteError />}
        >
          <Route
            index
            element={
              <Lazy>
                <ParentDashboardRoute />
              </Lazy>
            }
          />
          <Route
            path="cases/:caseId"
            element={
              <Lazy>
                <ParentCaseDetailPage />
              </Lazy>
            }
          />
          <Route
            path="reports"
            element={
              <Lazy>
                <ParentReportsPage />
              </Lazy>
            }
          />
          <Route path="iep" element={<Navigate to="/parent/reports?type=iep" replace />} />
          <Route
            path="billing"
            element={
              <Lazy>
                <ParentBillingPage />
              </Lazy>
            }
          />
          <Route path="address" element={<Navigate to="/parent/profile" replace />} />
          <Route
            path="book"
            element={
              <Lazy>
                <ClientBookAppointmentPage />
              </Lazy>
            }
          />
          <Route
            path="session-logs"
            element={
              <Lazy>
                <ClientSessionLogsPage />
              </Lazy>
            }
          />
          <Route
            path="profile"
            element={
              <Lazy>
                <ParentProfilePage />
              </Lazy>
            }
          />
          <Route path="notifications" element={<NotificationCenterPage portal="parent" />} />
          <Route
            path="support"
            element={
              <Lazy>
                <ClientSupportHubPage />
              </Lazy>
            }
          />
          <Route path="incidents" element={<Navigate to="/parent/support?tab=incidents" replace />} />
        </Route>
      </Route>

      <Route
        path="/admin/*"
        element={
          <Protected portal="admin">
            <PortalShell portal="admin" />
          </Protected>
        }
      >
        <Route
          index
          element={
            <Lazy>
              <AdminIndexPage />
            </Lazy>
          }
        />
        <Route
          path="cm"
          element={
            <Lazy>
              <AdminCaseManagerHomePage />
            </Lazy>
          }
        />
        <Route
          path="workbench"
          element={
            <Lazy>
              <AdminWorkbenchPage />
            </Lazy>
          }
        />
        <Route
          path="cases"
          element={
            <Lazy>
              <AdminCasesPage />
            </Lazy>
          }
        />
        <Route
          path="cases/:caseId"
          element={
            <Lazy>
              <AdminCaseDetailPage />
            </Lazy>
          }
        />
        <Route
          path="logs"
          element={
            <Lazy>
              <AdminSessionLogsPage />
            </Lazy>
          }
        />
        <Route
          path="reports"
          element={
            <Lazy>
              <AdminReportsPage />
            </Lazy>
          }
        />
        <Route
          path="reports/view/:reportId"
          element={
            <Lazy>
              <AdminReportViewPage />
            </Lazy>
          }
        />
        <Route
          path="reports/edit/:reportId"
          element={
            <Lazy>
              <ReportEditPage />
            </Lazy>
          }
        />
        <Route
          path="invoices"
          element={
            <Lazy>
              <AdminInvoicesPage />
            </Lazy>
          }
        />
        <Route
          path="therapist-payouts"
          element={
            <Lazy>
              <AdminTherapistPayoutsPage />
            </Lazy>
          }
        />
        <Route
          path="invoices/compose"
          element={
            <Lazy>
              <InvoiceComposer />
            </Lazy>
          }
        />
        <Route
          path="invoices/client/:invoiceId"
          element={
            <Lazy>
              <AdminClientInvoicePage />
            </Lazy>
          }
        />
        <Route
          path="iep"
          element={
            <Lazy>
              <AdminIepPage />
            </Lazy>
          }
        />
        <Route
          path="support"
          element={
            <Lazy>
              <AdminSupportHubPage />
            </Lazy>
          }
        />
        <Route path="tickets" element={<Navigate to="/admin/support?tab=tickets" replace />} />
        <Route path="incidents" element={<Navigate to="/admin/support?tab=incidents" replace />} />
        <Route
          path="people"
          element={
            <Lazy>
              <AdminPeoplePage />
            </Lazy>
          }
        />
        <Route
          path="profile"
          element={
            <Lazy>
              <AdminStaffProfilePage />
            </Lazy>
          }
        />
        <Route
          path="client-profiles"
          element={
            <Lazy>
              <AdminClientProfilesPage />
            </Lazy>
          }
        />
        <Route path="users" element={<Navigate to="/admin/people?tab=staff" replace />} />
        <Route
          path="therapist-profiles"
          element={
            <Lazy>
              <AdminTherapistProfilesPage />
            </Lazy>
          }
        />
        <Route
          path="settings/services"
          element={
            <Lazy>
              <AdminServiceCategoriesPage />
            </Lazy>
          }
        />
        <Route
          path="cm-meetings"
          element={
            <Lazy>
              <CaseManagerMeetingsPage />
            </Lazy>
          }
        />
        <Route
          path="leave"
          element={
            <Lazy>
              <LeaveManagementPage portal="admin" />
            </Lazy>
          }
        />
        <Route
          path="memos"
          element={
            <Lazy>
              <HRMemosPage />
            </Lazy>
          }
        />
        <Route
          path="hr-cases"
          element={
            <Lazy>
              <HRCasesPage />
            </Lazy>
          }
        />
        <Route
          path="hr-reports"
          element={
            <Lazy>
              <AdminHrReportsPage />
            </Lazy>
          }
        />
        <Route path="notifications" element={<NotificationCenterPage portal="admin" />} />
      </Route>

      <Route path="/hr" element={<Navigate to="/admin/people" replace />} />
      <Route path="/hr/people" element={<Navigate to="/admin/people" replace />} />
      <Route path="/hr/therapists" element={<Navigate to="/admin/therapist-profiles" replace />} />
      <Route path="/hr/cases" element={<Navigate to="/admin/hr-cases" replace />} />
      <Route path="/hr/leave" element={<Navigate to="/admin/leave" replace />} />
      <Route path="/hr/memos" element={<Navigate to="/admin/memos" replace />} />
      <Route path="/hr/tickets" element={<Navigate to="/admin/support?tab=tickets" replace />} />
      <Route path="/hr/*" element={<Navigate to="/admin/people" replace />} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
