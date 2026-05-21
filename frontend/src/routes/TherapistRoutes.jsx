import { Route, Routes } from 'react-router-dom'
import { MyCasesPage } from '../components/cases/MyCasesPage.jsx'
import { CaseDetailPage } from '../components/cases/CaseDetailPage.jsx'
import { DailyLogsPage } from '../components/daily-logs/DailyLogsPage.jsx'
import { MonthlyReportsPage } from '../components/monthly-reports/MonthlyReportsPage.jsx'
import { InvoicesPage } from '../components/invoices/InvoicesPage.jsx'
import { TherapistDashboardPage } from '../pages/TherapistDashboardPage.jsx'
import { TherapistProfilePage } from '../components/therapist/TherapistProfilePage.jsx'
import { TherapistTicketsPage } from '../components/therapist/TherapistTicketsPage.jsx'
import { TherapistIncidentsPage } from '../components/therapist/TherapistIncidentsPage.jsx'
import { TherapistLeavePage } from '../components/therapist/TherapistLeavePage.jsx'
import { TherapistSlotsPage } from '../components/therapist/TherapistSlotsPage.jsx'

export function TherapistRoutes() {
  return (
    <Routes>
      <Route index element={<TherapistDashboardPage />} />
      <Route path="cases" element={<MyCasesPage />} />
      <Route path="cases/:caseId" element={<CaseDetailPage />} />
      <Route path="logs" element={<DailyLogsPage />} />
      <Route path="reports" element={<MonthlyReportsPage />} />
      <Route path="invoices" element={<InvoicesPage />} />
      <Route path="tickets" element={<TherapistTicketsPage />} />
      <Route path="incidents" element={<TherapistIncidentsPage />} />
      <Route path="leave" element={<TherapistLeavePage />} />
      <Route path="slots" element={<TherapistSlotsPage />} />
      <Route path="profile" element={<TherapistProfilePage />} />
    </Routes>
  )
}
