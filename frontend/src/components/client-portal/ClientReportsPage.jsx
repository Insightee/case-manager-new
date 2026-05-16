import { ClientPortalLayout } from './ClientPortalLayout'

export function ClientReportsPage({ reports, onViewReport }) {
  return (
    <ClientPortalLayout
      title="Approved Monthly Reports"
      subtitle="Only reports approved by your case manager are published here."
      actionLabel="Download all"
    >
      <section className="card">
        <div className="card-head">
          <h3>Published Reports</h3>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Month</th>
                <th>Child</th>
                <th>Case ID</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {reports.map((item) => (
                <tr key={item.id}>
                  <td>{item.month}</td>
                  <td>{item.childName}</td>
                  <td>{item.caseId}</td>
                  <td>
                    <span className="status completed">Approved</span>
                  </td>
                  <td>
                    <button type="button" onClick={() => onViewReport(item)}>
                      View report
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </ClientPortalLayout>
  )
}
