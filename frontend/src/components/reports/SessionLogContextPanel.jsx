import { useEffect, useState } from 'react'
import { apiFetch, apiDownload } from '../../lib/apiClient.js'

export function SessionLogContextPanel({ reportId, caseId, month, collapsed: initialCollapsed = false }) {
  const [open, setOpen] = useState(!initialCollapsed)
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open || !reportId) return
    setLoading(true)
    setError('')
    apiFetch(`/api/v1/reports/monthly/${reportId}/session-context`)
      .then((rows) => setLogs(rows || []))
      .catch((err) => {
        setError(err.message || 'Could not load session logs')
        setLogs([])
      })
      .finally(() => setLoading(false))
  }, [open, reportId])

  async function exportCsv() {
    if (!caseId) return
    const p = new URLSearchParams({ case_id: String(caseId) })
    if (month) p.set('month', month)
    await apiDownload(`/api/v1/reports/therapist/session-logs/export?${p}`, 'session_logs.csv')
  }

  return (
    <aside className="rounded-xl border border-slate-200 bg-slate-50">
      <button
        type="button"
        className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-semibold text-slate-800"
        onClick={() => setOpen((v) => !v)}
      >
        Session log reference
        <span className="text-slate-400">{open ? '−' : '+'}</span>
      </button>
      {open ? (
        <div className="border-t border-slate-200 px-4 pb-4">
          <p className="mt-2 text-xs text-slate-500">
            Approved sessions for this report month. Use these notes while writing your report.
          </p>
          {caseId ? (
            <button
              type="button"
              className="mt-2 text-xs font-semibold text-indigo-600 hover:underline"
              onClick={exportCsv}
            >
              Export CSV for this case
            </button>
          ) : null}
          {loading ? <p className="mt-3 text-sm text-slate-500">Loading…</p> : null}
          {error ? <p className="mt-3 text-sm text-red-600">{error}</p> : null}
          {!loading && !error && logs.length === 0 ? (
            <p className="mt-3 text-sm text-slate-500">No approved session logs for this month.</p>
          ) : null}
          <ul className="mt-3 max-h-80 space-y-3 overflow-y-auto">
            {logs.map((log) => (
              <li key={log.log_id} className="rounded-lg border border-slate-200 bg-white p-3 text-xs">
                <p className="font-semibold text-slate-800">
                  {log.scheduled_date}
                  {log.attendance_status ? ` · ${log.attendance_status}` : ''}
                </p>
                {log.activities_done ? (
                  <p className="mt-1 text-slate-600">
                    <strong>Activities:</strong> {log.activities_done}
                  </p>
                ) : null}
                {log.goals_addressed ? (
                  <p className="mt-1 text-slate-600">
                    <strong>Goals:</strong> {log.goals_addressed}
                  </p>
                ) : null}
                {log.parent_notes ? (
                  <p className="mt-1 text-slate-600">
                    <strong>Notes:</strong> {log.parent_notes}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </aside>
  )
}
