function formatAmount(amount) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(amount)
}

export function ClientBillingPage({ billingItems }) {
  return (
    <section className="card">
      <div className="card-head">
        <h3>Family billing</h3>
      </div>
      {billingItems.length === 0 ? (
        <p style={{ padding: 16, color: '#9ca3af' }}>No billing statements yet.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Month</th>
                <th>Case</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              {billingItems.map((item) => (
                <tr key={item.id}>
                  <td>{item.month}</td>
                  <td>{item.caseId || '—'}</td>
                  <td>{formatAmount(item.amountInr ?? item.amountINR ?? 0)}</td>
                  <td>
                    <span className={`status ${item.status === 'paid' ? 'completed' : 'in-progress'}`}>
                      {item.status}
                    </span>
                  </td>
                  <td>{item.detail || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
