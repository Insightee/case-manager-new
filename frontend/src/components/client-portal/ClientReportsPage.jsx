import { useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

export function ClientReportsPage({ reports }) {
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function viewReport(item) {
    setLoading(true)
    setError('')
    try {
      const detail = await apiFetch(`/api/v1/parent/reports/${item.id}`)
      setSelected(detail)
    } catch (err) {
      setError(err.message || 'Could not load report')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      {error ? <p style={{ color: '#b91c1c' }}>{error}</p> : null}
      <section className="card">
        <div className="card-head">
          <h3>Published Reports</h3>
        </div>
        {reports.length === 0 ? (
          <p style={{ padding: 16, color: '#9ca3af' }}>No approved reports yet.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Month</th>
                  <th>Child</th>
                  <th>Case ID</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {reports.map((item) => (
                  <tr key={item.id}>
                    <td>{item.month}</td>
                    <td>{item.childName || '—'}</td>
                    <td>{item.caseId}</td>
                    <td>
                      <button type="button" onClick={() => viewReport(item)} disabled={loading}>
                        View report
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {selected ? (
        <div
          role="dialog"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15,23,42,0.4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 16,
            zIndex: 50,
          }}
        >
          <div style={{ background: '#fff', borderRadius: 16, padding: 24, maxWidth: 560, width: '100%' }}>
            <h2 style={{ marginTop: 0 }}>{selected.month}</h2>
            <p style={{ color: '#6b7280' }}>
              {selected.childName} · {selected.caseId}
            </p>
            <p style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{selected.summary}</p>
            <button type="button" onClick={() => setSelected(null)} style={{ marginTop: 16 }}>
              Close
            </button>
          </div>
        </div>
      ) : null}
    </>
  )
}
