import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

export function CaseReportsPanel({ caseId, caseCode, childName }) {
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [month, setMonth] = useState('')
  const [summary, setSummary] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const rows = await apiFetch('/api/v1/reports/monthly')
      setReports((rows || []).filter((r) => r.case_id === caseId))
    } catch {
      setReports([])
    } finally {
      setLoading(false)
    }
  }, [caseId])

  useEffect(() => {
    load()
  }, [load])

  async function handleSubmit(reportId) {
    setError('')
    try {
      await apiFetch(`/api/v1/reports/monthly/${reportId}/submit`, { method: 'POST' })
      await load()
    } catch (err) {
      setError(err.message || 'Could not submit report')
    }
  }

  async function handleCreate(e) {
    e.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      await apiFetch('/api/v1/reports/monthly', {
        method: 'POST',
        body: JSON.stringify({ case_id: caseId, month, summary }),
      })
      setShowForm(false)
      setMonth('')
      setSummary('')
      await load()
    } catch (err) {
      setError(err.message || 'Could not create report')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <p style={{ color: '#6b7280' }}>Loading reports…</p>

  return (
    <div>
      <p style={{ fontSize: '0.875rem', color: '#6b7280' }}>
        Monthly reports for {childName} ({caseCode}). Submitted reports go to admin for review before parents see them.
      </p>
      <button
        type="button"
        onClick={() => setShowForm((v) => !v)}
        style={{ marginBottom: 16, padding: '8px 16px', borderRadius: 8, background: '#6366f1', color: '#fff', border: 'none', fontWeight: 600, cursor: 'pointer' }}
      >
        {showForm ? 'Cancel' : 'New monthly report'}
      </button>
      {showForm ? (
        <form onSubmit={handleCreate} style={{ background: '#f9fafb', padding: 16, borderRadius: 12, marginBottom: 16, display: 'grid', gap: 8 }}>
          <label style={{ fontSize: '0.875rem' }}>
            Month label (e.g. May 2026)
            <input required value={month} onChange={(e) => setMonth(e.target.value)} style={{ display: 'block', width: '100%', marginTop: 4, padding: 8, borderRadius: 8, border: '1px solid #d1d5db' }} />
          </label>
          <label style={{ fontSize: '0.875rem' }}>
            Summary
            <textarea required value={summary} onChange={(e) => setSummary(e.target.value)} rows={4} style={{ display: 'block', width: '100%', marginTop: 4, padding: 8, borderRadius: 8, border: '1px solid #d1d5db' }} />
          </label>
          {error ? <p style={{ color: '#b91c1c', margin: 0 }}>{error}</p> : null}
          <button type="submit" disabled={submitting} style={{ padding: 10, borderRadius: 8, background: '#F97316', color: '#fff', border: 'none', fontWeight: 600 }}>
            {submitting ? 'Saving…' : 'Save draft'}
          </button>
        </form>
      ) : null}
      {reports.length === 0 ? (
        <p style={{ color: '#9ca3af' }}>No monthly reports yet.</p>
      ) : (
        <ul style={{ listStyle: 'none', padding: 0 }}>
          {reports.map((r) => (
            <li key={r.id} style={{ padding: 14, marginBottom: 8, border: '1px solid #e5e7eb', borderRadius: 8, background: '#fff' }}>
              <strong>{r.month}</strong>
              <span style={{ marginLeft: 8, fontSize: '0.75rem', color: '#6b7280' }}>{r.status}</span>
              <p style={{ margin: '8px 0 0', fontSize: '0.875rem', color: '#374151' }}>{r.summary}</p>
              {r.reviewer_comment ? (
                <p style={{ margin: '8px 0 0', fontSize: '0.8rem', color: '#b91c1c' }}>Admin: {r.reviewer_comment}</p>
              ) : null}
              {r.status === 'DRAFT' || r.status === 'REJECTED' ? (
                <button
                  type="button"
                  onClick={() => handleSubmit(r.id)}
                  style={{ marginTop: 8, padding: '6px 12px', borderRadius: 8, background: '#F97316', color: '#fff', border: 'none', fontSize: '0.8rem', fontWeight: 600, cursor: 'pointer' }}
                >
                  Submit for review
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
