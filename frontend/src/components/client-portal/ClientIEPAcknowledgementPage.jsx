import { ClientPortalLayout } from './ClientPortalLayout'

function formatTimestamp(value) {
  if (!value) {
    return 'Not acknowledged yet'
  }

  return new Date(value).toLocaleString()
}

export function ClientIEPAcknowledgementPage({ iepItems, onAcknowledge }) {
  return (
    <ClientPortalLayout
      title="IEP Acknowledgement"
      subtitle="Review the issued IEP versions and acknowledge pending items."
      actionLabel="View latest IEP PDF"
    >
      <section className="card">
        <div className="card-head">
          <h3>IEP Status</h3>
        </div>
        <ul className="log-list">
          {iepItems.map((item) => {
            const isPending = item.status === 'pending'
            return (
              <li key={item.id}>
                <div>
                  <p>
                    {item.childName} ({item.caseId})
                  </p>
                  <span>
                    Version {item.version} · Issued {new Date(item.issuedAt).toLocaleDateString()}
                  </span>
                </div>
                <div>
                  <p>{formatTimestamp(item.acknowledgedAt)}</p>
                  {isPending ? (
                    <button type="button" onClick={() => onAcknowledge(item.id)}>
                      Acknowledge now
                    </button>
                  ) : (
                    <span className="status completed">Acknowledged</span>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      </section>
    </ClientPortalLayout>
  )
}
