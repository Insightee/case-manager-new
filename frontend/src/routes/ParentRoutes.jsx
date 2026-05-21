import { useCallback } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../lib/apiClient.js'
import { ErrorBanner } from '../components/shared/ErrorBanner.jsx'
import { ClientPortalLayout } from '../components/client-portal/ClientPortalLayout.jsx'
import { ClientDashboardPage } from '../components/client-portal/ClientDashboardPage.jsx'
import { ParentReportsPage } from '../components/client-portal/ParentReportsPage.jsx'
import { ParentBillingPage } from '../components/client-portal/ParentBillingPage.jsx'
import { ClientSupportHubPage } from '../components/client-portal/ClientSupportHubPage.jsx'
import { ClientBookAppointmentPage } from '../components/client-portal/ClientBookAppointmentPage.jsx'
import { ParentProfilePage } from '../components/client-portal/ParentProfilePage.jsx'
import { ClientSessionLogsPage } from '../components/client-portal/ClientSessionLogsPage.jsx'
import { ParentCaseDetailPage } from '../components/client-portal/ParentCaseDetailPage.jsx'

function mapParentCases(cases) {
  return (cases || []).map((c) => ({
    id: c.id,
    caseId: c.caseId,
    childName: c.childName,
    serviceType: c.serviceType,
    productModule: c.productModule,
    isHomecare: c.isHomecare,
    serviceAddress: c.serviceAddress,
    serviceAddressSummary: c.serviceAddressSummary,
    therapist: c.therapistName || '—',
    caseManager: c.caseManagerName || '—',
    status: c.status,
    latestApprovedReportMonth: c.latestApprovedReportMonth || '—',
    iepAcknowledgementStatus: c.iepStatus === 'acknowledged' ? 'acknowledged' : c.iepStatus === 'pending' ? 'pending' : 'none',
    upcomingBooking: c.upcomingBooking,
  }))
}

function mapParentAppointments(slots, meetings) {
  const slotItems = (slots || []).map((a) => ({
    id: `slot-${a.id}`,
    rawId: a.id,
    isCmMeeting: false,
    caseId: a.caseId,
    caseDbId: a.caseDbId,
    childName: a.childName,
    therapistName: a.therapistName,
    slotDate: a.slotDate,
    startTime: a.startTime,
    endTime: a.endTime,
    approvalStatus: a.approval_status || a.approvalStatus || 'CONFIRMED',
    canCancel: a.can_cancel,
    canReschedule: a.can_reschedule,
    rescheduleReason: a.reschedule_reason,
    cancelReason: a.cancel_reason,
  }))
  const meetingItems = (meetings || []).map((m) => ({
    id: `cm-${m.id}`,
    rawId: m.id,
    isCmMeeting: true,
    caseId: m.case_code,
    caseDbId: m.case_id,
    caseMgrName: m.case_manager_name,
    childName: m.child_name,
    therapistName: null,
    slotDate: m.scheduled_date,
    startTime: m.scheduled_time,
    endTime: null,
    approvalStatus: 'CONFIRMED',
    canCancel: false,
    canReschedule: false,
  }))
  return [...slotItems, ...meetingItems].sort((a, b) => {
    const da = (a.slotDate || '') + 'T' + (a.startTime || '00:00')
    const db = (b.slotDate || '') + 'T' + (b.startTime || '00:00')
    return da < db ? -1 : da > db ? 1 : 0
  })
}

async function fetchParentBootstrap() {
  const [cases, hubOrReports, billingDash, notifications, appointments, cmMeetings] = await Promise.all([
    apiFetch('/api/v1/parent/cases'),
    apiFetch('/api/v1/parent/reports/hub').catch(() => apiFetch('/api/v1/parent/reports')),
    apiFetch('/api/v1/parent/billing/dashboard').catch(() => ({ invoices: [], packages: [], summary: null })),
    apiFetch('/api/v1/parent/notifications'),
    apiFetch('/api/v1/parent/appointments').catch(() => []),
    apiFetch('/api/v1/parent/cm-meetings').catch(() => []),
  ])
  const hub = hubOrReports?.monthly ? hubOrReports : { monthly: hubOrReports || [], iep: [] }
  return {
    cases: mapParentCases(cases),
    reports: hub.monthly || [],
    iep: hub.iep || [],
    billing: billingDash?.invoices || [],
    billingSummary: billingDash?.summary || null,
    appointments: mapParentAppointments(appointments, cmMeetings),
    notifications: (notifications || []).map((n) => ({
      id: n.id,
      title: n.title,
      detail: n.body,
      createdAt: n.created_at ? new Date(n.created_at).toLocaleString() : '',
      isRead: n.is_read,
    })),
  }
}

export function ParentRoutes() {
  const queryClient = useQueryClient()
  const { data, error, isLoading, refetch } = useQuery({
    queryKey: ['parent', 'bootstrap'],
    queryFn: fetchParentBootstrap,
  })

  const bootstrap = data || { cases: [], reports: [], iep: [], billing: [], billingSummary: null, appointments: [], notifications: [] }

  const reload = useCallback(() => {
    return queryClient.invalidateQueries({ queryKey: ['parent', 'bootstrap'] })
  }, [queryClient])

  async function markNotificationRead(id) {
    await apiFetch(`/api/v1/parent/notifications/${id}/read`, { method: 'PATCH' })
    await reload()
  }

  const errorBanner = (
    <>
      <ErrorBanner message={error?.message} onRetry={() => refetch()} />
      {isLoading && !data ? <p className="muted">Loading your family dashboard…</p> : null}
    </>
  )

  return (
    <Routes>
      <Route
        index
        element={
          <ClientPortalLayout title="Family dashboard" subtitle="Approved updates for your children.">
            {errorBanner}
            <ClientDashboardPage
              cases={bootstrap.cases}
              reports={bootstrap.reports}
              iepItems={bootstrap.iep}
              billing={bootstrap.billing}
              billingSummary={bootstrap.billingSummary}
              appointments={bootstrap.appointments}
              notifications={bootstrap.notifications}
              onMarkRead={markNotificationRead}
            />
          </ClientPortalLayout>
        }
      />
      <Route path="cases/:caseId" element={<ParentCaseDetailPage cases={bootstrap.cases} />} />
      <Route path="reports" element={<ParentReportsPage />} />
      <Route path="iep" element={<Navigate to="/parent/reports?type=iep" replace />} />
      <Route path="billing" element={<ParentBillingPage />} />
      <Route path="address" element={<Navigate to="/parent/profile" replace />} />
      <Route path="book" element={<ClientBookAppointmentPage cases={bootstrap.cases} />} />
      <Route path="session-logs" element={<ClientSessionLogsPage cases={bootstrap.cases} />} />
      <Route path="profile" element={<ParentProfilePage onProfileUpdated={reload} />} />
      <Route path="support" element={<ClientSupportHubPage cases={bootstrap.cases} />} />
      <Route path="incidents" element={<Navigate to="/parent/support?tab=incidents" replace />} />
    </Routes>
  )
}
