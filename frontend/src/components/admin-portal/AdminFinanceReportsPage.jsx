import { AdminPageHeader } from './ui/index.js'
import { AdminFinanceReportsTab } from './AdminFinanceReportsTab.jsx'

export function AdminFinanceReportsPage() {
  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="Finance"
        title="Reports"
        subtitle="Case-level payout previews and finance exports for therapist compensation."
      />
      <AdminFinanceReportsTab defaultReportKey="therapist-payout-preview" />
    </div>
  )
}
