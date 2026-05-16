import { ClientPortalLayout } from './ClientPortalLayout'

function formatAmount(amount) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(amount)
}

export function ClientBillingPage({ billingItems }) {
  return (
    <ClientPortalLayout
      title="Billing Snapshot"
      subtitle="Read-only invoice and payment status for your mapped case records."
      actionLabel="Download statement"
    >
      <section className="card">
        <div className="card-head">
          <h3>Invoice / Payment Status</h3>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Month</th>
                <th>Case ID</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Last Updated</th>
              </tr>
            </thead>
            <tbody>
              {billingItems.map((item) => (
                <tr key={item.id}>
                  <td>{item.month}</td>
                  <td>{item.caseId}</td>
                  <td>{formatAmount(item.amountINR)}</td>
                  <td>
                    <span className={`status ${item.status === 'paid' ? 'completed' : 'in-progress'}`}>
                      {item.status}
                    </span>
                  </td>
                  <td>{new Date(item.updatedAt).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </ClientPortalLayout>
  )
}
