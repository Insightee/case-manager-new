import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { generateReportFromLogs } from '../../lib/reportGenerateFromLogs.js'
import { useAuth } from '../../context/AuthContext.jsx'

function currentMonthLabel() {
  return new Date().toLocaleString('en-US', { month: 'short', year: 'numeric' })
}

const EDITABLE_STATUSES = new Set(['DRAFT', 'REJECTED'])

export function CaseSessionMonthlyReportBar({ caseId }) {
  const { can } = useAuth()
  const [reports, setReports] = useState([])
  const [selectedId, setSelectedId] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const canGenerate = can('monthly_report.create') || can('monthly_report.approve')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await apiFetch(`/api/v1/admin/reports/monthly?case_id=${caseId}&page_size=24`)
      setReports(data.items || [])
    } catch {
      setReports([])
    } finally {
      setLoading(false)
    }
  }, [caseId])

  useEffect(() => {
    load()
  }, [load])

  const editable = useMemo(
    () => reports.filter((r) => EDITABLE_STATUSES.has(String(r.status || '').toUpperCase())),
    [reports],
  )

  useEffect(() => {
    if (editable.length === 0) {
      setSelectedId('')
      return
    }
    const current = editable.find((r) => r.label === currentMonthLabel())
    setSelectedId(String((current || editable[0]).id))
  }, [editable])

  async function handleGenerate(mode = 'replace') {
    if (!selectedId) return
    setBusy(true)
    setError('')
    setMessage('')
    try {
      await generateReportFromLogs(Number(selectedId), mode)
      setMessage('Monthly report draft updated from approved session logs for this case.')
      await load()
    } catch (e) {
      setError(e.message || 'Could not generate report from logs')
    } finally {
      setBusy(false)
    }
  }

  if (!canGenerate) return null

  return (
    <div className="case-sessions-report-bar">
      <div className="case-sessions-report-bar__copy">
        <p className="case-sessions-report-bar__title">Monthly report from session logs</p>
        <p className="case-sessions-report-bar__hint">
          Builds or refreshes a draft using submitted logs for the report month. Open Reports to review or publish.
        </p>
      </div>
      {loading ? (
        <p className="admin-muted" style={{ margin: 0, fontSize: '0.8125rem' }}>
          Loading reports…
        </p>
      ) : editable.length === 0 ? (
        <div className="case-sessions-report-bar__actions">
          <p className="admin-muted" style={{ margin: 0, fontSize: '0.8125rem' }}>
            No draft monthly report for this case yet.
          </p>
          <Link to={`/admin/cases/${caseId}?tab=reports`} className="admin-btn admin-btn--secondary admin-btn--sm">
            Open Reports tab
          </Link>
        </div>
      ) : (
        <div className="case-sessions-report-bar__actions">
          <label className="case-sessions-report-bar__field">
            <span className="case-sessions-report-bar__label">Report month</span>
            <select
              className="admin-input"
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value)}
              disabled={busy}
            >
              {editable.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.label} ({String(r.status).replaceAll('_', ' ')})
                </option>
              ))}
            </select>
          </label>
          <div className="case-sessions-report-bar__buttons">
            <button
              type="button"
              className="admin-btn admin-btn--primary admin-btn--sm"
              disabled={busy || !selectedId}
              onClick={() => handleGenerate('replace')}
            >
              {busy ? 'Building…' : 'Generate from logs'}
            </button>
            <button
              type="button"
              className="admin-btn admin-btn--ghost admin-btn--sm"
              disabled={busy || !selectedId}
              onClick={() => handleGenerate('append')}
            >
              Append logs
            </button>
            <Link to={`/admin/cases/${caseId}?tab=reports`} className="admin-btn admin-btn--ghost admin-btn--sm">
              View reports
            </Link>
          </div>
        </div>
      )}
      {message ? <p className="admin-alert admin-alert--success case-sessions-report-bar__msg">{message}</p> : null}
      {error ? <p className="admin-alert admin-alert--error case-sessions-report-bar__msg">{error}</p> : null}
    </div>
  )
}
