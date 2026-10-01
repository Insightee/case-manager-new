import { AdminPageHeader } from './ui/index.js'
import { AdminFinanceReportsTab } from './AdminFinanceReportsTab.jsx'

export function AdminFinanceReportsPage() {
  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="Finance"
        title="Reports"
        subtitle="Therapist payout preview for a billing month. Collections and receivables are separate views."
      />
      <AdminFinanceReportsTab />
    </div>
  )
}
