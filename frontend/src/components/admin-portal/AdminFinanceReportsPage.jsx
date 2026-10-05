import { AdminReportLibrary } from './AdminReportLibrary.jsx'

export function AdminFinanceReportsPage() {
  return (
    <AdminReportLibrary
      defaultCategory="finance"
      defaultReportKey="therapist-payout-preview"
      eyebrow="Finance"
      title="Reports"
      subtitle="One library for payouts, collections, outstanding, and billing. Set month, case type, period, and status, then generate or download."
    />
  )
}
