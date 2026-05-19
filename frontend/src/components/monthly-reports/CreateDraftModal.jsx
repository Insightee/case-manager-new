import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

export function CreateDraftModal({ open, onClose, onCreated, defaultMonth }) {
  const [cases, setCases] = useState([])
  const [caseId, setCaseId] = useState('')
  const [month, setMonth] = useState(defaultMonth || '')
  const [summary, setSummary] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    setMonth(defaultMonth || '')
    setError('')
    apiFetch('/api/v1/cases?assigned=true')
      .then((rows) => setCases(rows || []))
      .catch(() => setCases([]))
  }, [open, defaultMonth])

  if (!open) return null

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const created = await apiFetch('/api/v1/reports/monthly', {
        method: 'POST',
        body: JSON.stringify({
          case_id: Number(caseId),
          month,
          summary: summary || undefined,
        }),
      })
      onCreated?.(created)
      onClose()
      setCaseId('')
      setSummary('')
    } catch (err) {
      setError(err.message || 'Could not create draft')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-[90] flex items-center justify-center bg-slate-900/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-draft-title"
    >
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
        <h2 id="create-draft-title" className="text-lg font-semibold text-slate-900">
          New monthly report draft
        </h2>
        <p className="mt-1 text-sm text-slate-500">Choose a case and month. You can submit for admin review when ready.</p>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3">
          <label className="text-sm font-medium text-slate-700">
            Case
            <select
              required
              value={caseId}
              onChange={(e) => setCaseId(e.target.value)}
              className="mt-1 block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            >
              <option value="">Select case…</option>
              {cases.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.case_code} — {c.child_name}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            Month (e.g. May 2026)
            <input
              required
              value={month}
              onChange={(e) => setMonth(e.target.value)}
              className="mt-1 block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Summary
            <textarea
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              rows={4}
              className="mt-1 block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              placeholder="Progress, goals, recommendations…"
            />
          </label>
          {error ? <p className="text-sm text-red-600">{error}</p> : null}
          <div className="flex gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
            >
              {loading ? 'Saving…' : 'Save draft'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
