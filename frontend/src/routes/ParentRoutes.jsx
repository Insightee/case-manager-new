import { useCallback, useEffect, useState } from 'react'
import { Route, Routes } from 'react-router-dom'
import { apiFetch } from '../lib/apiClient.js'
import { ClientPortalLayout } from '../components/client-portal/ClientPortalLayout.jsx'
import { ClientDashboardPage } from '../components/client-portal/ClientDashboardPage.jsx'
import { ClientReportsPage } from '../components/client-portal/ClientReportsPage.jsx'
import { ClientIEPAcknowledgementPage } from '../components/client-portal/ClientIEPAcknowledgementPage.jsx'
import { ClientBillingPage } from '../components/client-portal/ClientBillingPage.jsx'
import { ClientSupportPage } from '../components/client-portal/ClientSupportPage.jsx'
import { ClientBookAppointmentPage } from '../components/client-portal/ClientBookAppointmentPage.jsx'
import { ClientServiceAddressPage } from '../components/client-portal/ClientServiceAddressPage.jsx'
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

export function ParentRoutes() {
  const [data, setData] = useState({ cases: [], reports: [], iep: [], billing: [], notifications: [] })

  const reload = useCallback(() => {
    return Promise.all([
      apiFetch('/api/v1/parent/cases'),
      apiFetch('/api/v1/parent/reports'),
      apiFetch('/api/v1/parent/iep-status'),
      apiFetch('/api/v1/parent/billing-summaries'),
      apiFetch('/api/v1/parent/notifications'),
    ])
      .then(([cases, reports, iep, billing, notifications]) => {
        setData({
          cases: mapParentCases(cases),
          reports: reports || [],
          iep: iep || [],
          billing: billing || [],
          notifications: (notifications || []).map((n) => ({
            id: n.id,
            title: n.title,
            detail: n.body,
            createdAt: n.created_at ? new Date(n.created_at).toLocaleString() : '',
            isRead: n.is_read,
          })),
        })
      })
      .catch(() => setData({ cases: [], reports: [], iep: [], billing: [], notifications: [] }))
  }, [])

  useEffect(() => {
    reload()
  }, [reload])

  async function markNotificationRead(id) {
    await apiFetch(`/api/v1/parent/notifications/${id}/read`, { method: 'PATCH' })
    await reload()
  }

  return (
    <Routes>
      <Route
        index
        element={
          <ClientPortalLayout title="Family dashboard" subtitle="Approved updates for your children.">
            <ClientDashboardPage
              cases={data.cases}
              reports={data.reports}
              iepItems={data.iep}
              notifications={data.notifications}
              onMarkNotificationRead={markNotificationRead}
            />
          </ClientPortalLayout>
        }
      />
      <Route
        path="cases/:caseId"
        element={
          <ClientPortalLayout title="Case details" subtitle="Sessions, reports, and bookings for this child.">
            <ParentCaseDetailPage />
          </ClientPortalLayout>
        }
      />
      <Route
        path="reports"
        element={
          <ClientPortalLayout title="Approved reports" subtitle="Only case-manager approved reports.">
            <ClientReportsPage reports={data.reports} />
          </ClientPortalLayout>
        }
      />
      <Route
        path="iep"
        element={
          <ClientPortalLayout title="IEP" subtitle="Review and acknowledge shared plans.">
            <ClientIEPAcknowledgementPage iepItems={data.iep} onAcknowledged={reload} />
          </ClientPortalLayout>
        }
      />
      <Route
        path="billing"
        element={
          <ClientPortalLayout title="Billing" subtitle="Family billing statements.">
            <ClientBillingPage billingItems={data.billing} />
          </ClientPortalLayout>
        }
      />
      <Route
        path="address"
        element={
          <ClientPortalLayout title="Service address" subtitle="Where homecare visits should take place.">
            <ClientServiceAddressPage cases={data.cases} onSaved={reload} />
          </ClientPortalLayout>
        }
      />
      <Route
        path="book"
        element={
          <ClientPortalLayout title="Book appointment" subtitle="Choose a therapist and available time.">
            <ClientBookAppointmentPage cases={data.cases} />
          </ClientPortalLayout>
        }
      />
      <Route
        path="session-logs"
        element={
          <ClientPortalLayout title="Session updates" subtitle="Activities and progress from your therapist.">
            <ClientSessionLogsPage cases={data.cases} />
          </ClientPortalLayout>
        }
      />
      <Route
        path="profile"
        element={
          <ClientPortalLayout title="My profile" subtitle="Photo and display name.">
            <ParentProfilePage />
          </ClientPortalLayout>
        }
      />
      <Route
        path="support"
        element={
          <ClientPortalLayout
            title="Support"
            subtitle="Contact the care team."
            actionLabel="New request"
            onAction={() => document.getElementById('parent-support-form')?.scrollIntoView({ behavior: 'smooth' })}
          >
            <div id="parent-support-form">
              <ClientSupportPage
                cases={data.cases}
                onSubmit={async (payload) => {
                  await apiFetch('/api/v1/parent/support-requests', {
                    method: 'POST',
                    body: JSON.stringify({
                      subject: payload.subject,
                      message: payload.message,
                      case_id: payload.case_id,
                    }),
                  })
                }}
              />
            </div>
          </ClientPortalLayout>
        }
      />
    </Routes>
  )
}
