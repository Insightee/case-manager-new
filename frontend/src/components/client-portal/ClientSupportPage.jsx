import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

export function ClientSupportPage({ cases, onSubmit }) {
  const [subject, setSubject] = useState('')
  const [message, setMessage] = useState('')
  const [caseId, setCaseId] = useState('')
  const [success, setSuccess] = useState('')
  const [error, setError] = useState('')
  const [tickets, setTickets] = useState([])

  const loadTickets = useCallback(async () => {
    try {
      const rows = await apiFetch('/api/v1/tickets')
      setTickets(rows || [])
    } catch {
      setTickets([])
    }
  }, [])

  useEffect(() => {
    loadTickets()
  }, [loadTickets])

  async function handleSubmit(event) {
    event.preventDefault()
    if (!subject.trim() || !message.trim()) return
    setError('')
    setSuccess('')
    try {
      await onSubmit({
        subject: subject.trim(),
        message: message.trim(),
        case_id: caseId ? Number(caseId) : undefined,
      })
      setSuccess('Request submitted successfully.')
      setSubject('')
      setMessage('')
      setCaseId('')
      await loadTickets()
    } catch (err) {
      setError(err.message || 'Could not submit request')
    }
  }

  return (
    <>
      <section className="card client-support">
        <div className="card-head">
          <h3>Submit request</h3>
        </div>
        <form onSubmit={handleSubmit}>
          {cases?.length > 0 ? (
            <label style={{ display: 'block', marginBottom: 8 }}>
              Related case (optional)
              <select value={caseId} onChange={(e) => setCaseId(e.target.value)} style={{ display: 'block', width: '100%', marginTop: 4 }}>
                <option value="">—</option>
                {cases.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.caseId} — {c.childName}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Subject" required />
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Describe your concern"
            rows={5}
            required
          />
          <button type="submit">Submit request</button>
        </form>
        {error ? <p style={{ color: '#b91c1c' }}>{error}</p> : null}
        {success ? <p className="client-support__success">{success}</p> : null}
      </section>

      <section className="card" style={{ marginTop: 20 }}>
        <div className="card-head">
          <h3>Your requests</h3>
        </div>
        {tickets.length === 0 ? (
          <p style={{ padding: 16, color: '#9ca3af' }}>No support requests yet.</p>
        ) : (
          <ul className="log-list">
            {tickets.map((t) => (
              <li key={t.id}>
                <div>
                  <p>{t.subject}</p>
                  <span>
                    {t.status} · {t.created_at ? new Date(t.created_at).toLocaleString() : ''}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  )
}
