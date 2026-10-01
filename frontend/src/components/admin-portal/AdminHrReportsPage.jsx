import { AdminReportLibrary } from './AdminReportLibrary.jsx'

export function AdminHrReportsPage() {
  return (
    <AdminReportLibrary
      defaultCategory="hr_attendance"
      defaultReportKey="bulk-attendance"
      eyebrow="People & HR"
      title="Reports"
      subtitle="One library for attendance, session ops, finance, and support exports. Set month, case type, period, and status, then generate or download."
    />
  )
}
