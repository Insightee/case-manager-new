import { apiFetch, getTokens } from '../../lib/apiClient.js'

const API_URL = import.meta.env.VITE_API_URL || ''

export function ClientIEPAcknowledgementPage({ iepItems, onAcknowledged }) {
  async function handleAcknowledge(item) {
    await apiFetch(`/api/v1/parent/iep/${item.id}/acknowledge`, { method: 'POST' })
    onAcknowledged?.()
  }

  function downloadIep(item) {
    const { access } = getTokens()
    const url = `${API_URL}/api/v1/parent/attachments/${item.id}/download`
    fetch(url, { headers: access ? { Authorization: `Bearer ${access}` } : {} })
      .then((res) => {
        if (!res.ok) throw new Error('Download failed')
        return res.blob()
      })
      .then((blob) => {
        const a = document.createElement('a')
        a.href = URL.createObjectURL(blob)
        a.download = item.fileName || 'iep-document'
        a.click()
        URL.revokeObjectURL(a.href)
      })
      .catch(() => alert('Could not download file'))
  }

  return (
    <section className="card">
      <div className="card-head">
        <h3>IEP Status</h3>
      </div>
      {iepItems.length === 0 ? (
        <p style={{ padding: 16, color: '#9ca3af' }}>No IEP documents shared yet.</p>
      ) : (
        <ul className="log-list">
          {iepItems.map((item) => {
            const isPending = item.status === 'pending'
            return (
              <li key={item.id}>
                <div>
                  <p>
                    {item.childName || 'Child'} ({item.caseId})
                  </p>
                  <span>
                    Version {item.version} · Issued {new Date(item.issuedAt).toLocaleDateString()}
                  </span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-end' }}>
                  <button type="button" onClick={() => downloadIep(item)}>
                    Download
                  </button>
                  {isPending ? (
                    <button type="button" onClick={() => handleAcknowledge(item)}>
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
      )}
    </section>
  )
}
