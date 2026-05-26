import { useEffect, useState } from 'react'
import { apiFetch, apiDownload } from '../../lib/apiClient.js'

export function SessionLogContextPanel({
  reportId,
  caseId,
  month,
  collapsed: initialCollapsed = false,
  onInsertIepGoals,
}) {
  const [open, setOpen] = useState(!initialCollapsed)
  const [logs, setLogs] = useState([])
  const [iepContext, setIepContext] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open || !reportId) return
    setLoading(true)
    setError('')
    const tasks = [
      apiFetch(`/api/v1/reports/monthly/${reportId}/session-context`).then((rows) => setLogs(rows || [])),
    ]
    if (caseId) {
      tasks.push(
        apiFetch(`/api/v1/reports/monthly/iep-context?case_id=${caseId}`)
          .then((ctx) => setIepContext(ctx))
          .catch(() => setIepContext(null)),
      )
    }
    Promise.all(tasks)
      .catch((err) => {
        setError(err.message || 'Could not load session logs')
        setLogs([])
      })
      .finally(() => setLoading(false))
  }, [open, reportId, caseId])

  function buildIepGoalsHtml() {
    const rows = iepContext?.learningEnvironments || []
    if (!rows.length) return ''
    const body = rows
      .map(
        (r) =>
          `<tr><td>${r.environment || ''}</td><td>${r.goals || ''}</td><td>${r.strategies || ''}</td><td>${r.supportsNeeded || ''}</td></tr>`,
      )
      .join('')
    return `<h3>IEP goals reference</h3><table class="iep-doc-table"><thead><tr><th>Environment</th><th>Goals</th><th>Strategies</th><th>Supports</th></tr></thead><tbody>${body}</tbody></table>`
  }

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
          {iepContext?.hasPlan && iepContext.learningEnvironments?.length > 0 ? (
            <div className="mt-4 rounded-lg border border-indigo-100 bg-white p-3">
              <p className="text-xs font-semibold text-indigo-900">IEP goals reference</p>
              <div className="mt-2 max-h-48 overflow-auto text-xs">
                <table className="w-full border-collapse text-left">
                  <thead>
                    <tr className="text-slate-500">
                      <th className="pr-2 pb-1">Env</th>
                      <th className="pr-2 pb-1">Goals</th>
                    </tr>
                  </thead>
                  <tbody>
                    {iepContext.learningEnvironments.map((r, i) => (
                      <tr key={i} className="border-t border-slate-100">
                        <td className="py-1 pr-2 align-top font-medium">{r.environment}</td>
                        <td className="py-1 align-top text-slate-600">{r.goals}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {onInsertIepGoals ? (
                <button
                  type="button"
                  className="mt-2 text-xs font-semibold text-indigo-600 hover:underline"
                  onClick={() => onInsertIepGoals(buildIepGoalsHtml())}
                >
                  Insert IEP goals into report
                </button>
              ) : null}
            </div>
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
