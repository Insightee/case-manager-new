import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../lib/apiClient.js'
import { ErrorBanner } from '../components/shared/ErrorBanner.jsx'
import { ClientPortalLayout } from '../components/client-portal/ClientPortalLayout.jsx'
import { ClientDashboardPage } from '../components/client-portal/ClientDashboardPage.jsx'
import { queryKeys } from '../lib/queryClient.js'
import { mapParentAppointments, mapParentCases } from '../lib/parentCases.js'

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

export function ParentDashboardRoute() {
  const queryClient = useQueryClient()
  const { data, error, isLoading, refetch } = useQuery({
    queryKey: queryKeys.parentBootstrap,
    queryFn: fetchParentBootstrap,
  })

  const bootstrap = data || {
    cases: [],
    reports: [],
    iep: [],
    billing: [],
    billingSummary: null,
    appointments: [],
    notifications: [],
  }

  async function markNotificationRead(id) {
    await apiFetch(`/api/v1/parent/notifications/${id}/read`, { method: 'PATCH' })
    await queryClient.invalidateQueries({ queryKey: queryKeys.parentBootstrap })
    await queryClient.invalidateQueries({ queryKey: queryKeys.parentCases })
  }

  return (
    <ClientPortalLayout title="Family dashboard" subtitle="">
      <ErrorBanner message={error?.message} onRetry={() => refetch()} />
      {isLoading && !data ? <p className="muted">Loading your family dashboard…</p> : null}
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
  )
}
