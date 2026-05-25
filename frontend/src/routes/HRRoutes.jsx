import { Route, Routes } from 'react-router-dom'
import { HRDashboardPage } from '../components/hr-portal/HRDashboardPage.jsx'
import { HRTherapistsPage } from '../components/hr-portal/HRTherapistsPage.jsx'
import { HRCasesPage } from '../components/hr-portal/HRCasesPage.jsx'
import { HRLeavePage } from '../components/hr-portal/HRLeavePage.jsx'
import { HRMemosPage } from '../components/hr-portal/HRMemosPage.jsx'
import { HRTicketsPage } from '../components/hr-portal/HRTicketsPage.jsx'
import { AdminPeoplePage } from '../components/admin-portal/AdminPeoplePage.jsx'

export function HRRoutes() {
  return (
    <Routes>
      <Route index element={<HRDashboardPage />} />
      <Route path="people" element={<AdminPeoplePage />} />
      <Route path="therapists" element={<HRTherapistsPage />} />
      <Route path="cases" element={<HRCasesPage />} />
      <Route path="leave" element={<HRLeavePage />} />
      <Route path="memos" element={<HRMemosPage />} />
      <Route path="tickets" element={<HRTicketsPage />} />
    </Routes>
  )
}
