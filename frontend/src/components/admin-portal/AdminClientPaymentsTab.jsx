import { AdminClientInvoicesTab } from './AdminClientInvoicesTab.jsx'

/** Client payments and claim verification (split from duplicate claims tab). */
export function AdminClientPaymentsTab({ openInvoiceId = null }) {
  return (
    <AdminClientInvoicesTab
      highlightClaimsPending
      claimsOnly
      openInvoiceId={openInvoiceId}
      paymentsMode
    />
  )
}
