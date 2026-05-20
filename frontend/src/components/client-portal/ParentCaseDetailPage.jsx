import { useCallback, useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'sessions', label: 'Session updates' },
  { id: 'reports', label: 'Reports' },
  { id: 'bookings', label: 'Bookings' },
]

export function ParentCaseDetailPage() {
  const { caseId } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'overview'
  const [caseRow, setCaseRow] = useState(null)
  const [logs, setLogs] = useState([])
  const [reports, setReports] = useState([])
  const [appointments, setAppointments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedReport, setSelectedReport] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [c, allLogs, allReports, allAppts] = await Promise.all([
        apiFetch(`/api/v1/parent/cases/${caseId}`),
        apiFetch(`/api/v1/parent/session-logs?case_id=${caseId}`),
        apiFetch('/api/v1/parent/reports'),
        apiFetch('/api/v1/parent/appointments'),
      ])
      setCaseRow(c)
      setLogs(allLogs || [])
      setReports((allReports || []).filter((r) => String(r.caseDbId) === String(caseId)))
      setAppointments((allAppts || []).filter((a) => String(a.caseDbId) === String(caseId)))
    } catch (err) {
      setError(err.message || 'Case not found')
      setCaseRow(null)
    } finally {
      setLoading(false)
    }
  }, [caseId])

  useEffect(() => {
    load()
  }, [load])

  function setTab(id) {
    setSearchParams({ tab: id }, { replace: true })
  }

  async function openReport(report) {
    try {
      const detail = await apiFetch(`/api/v1/parent/reports/${report.id}`)
      setSelectedReport(detail)
    } catch (err) {
      setError(err.message || 'Could not load report')
    }
  }

  async function cancelAppointment(slotId) {
    try {
      await apiFetch(`/api/v1/parent/appointments/${slotId}/cancel`, { method: 'POST' })
      await load()
    } catch (err) {
      setError(err.message || 'Could not cancel appointment')
    }
  }

  if (loading) return <p style={{ color: '#6b7280' }}>Loading case…</p>
  if (error || !caseRow) {
    return (
      <div>
        <p style={{ color: '#b91c1c' }}>{error || 'Case not found'}</p>
        <Link to="/parent">Back to dashboard</Link>
      </div>
    )
  }

  return (
    <div>
      <p style={{ marginBottom: 8 }}>
        <Link to="/parent" style={{ fontSize: '0.875rem', color: '#6366f1', fontWeight: 600 }}>
          ← Family dashboard
        </Link>
      </p>
      <header style={{ marginBottom: 20 }}>
        <p style={{ fontSize: '0.75rem', fontWeight: 600, color: '#6366f1', textTransform: 'uppercase', margin: 0 }}>
          {caseRow.caseId}
        </p>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: '4px 0' }}>{caseRow.childName}</h1>
        <p style={{ color: '#6b7280', margin: 0 }}>
          {caseRow.serviceType} · Therapist: {caseRow.therapistName || '—'}
        </p>
      </header>

      <nav style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 24, borderBottom: '1px solid #e5e7eb', paddingBottom: 12 }}>
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            style={{
              padding: '8px 14px',
              borderRadius: 8,
              border: 'none',
              cursor: 'pointer',
              fontWeight: 600,
              background: tab === t.id ? '#6366f1' : '#f3f4f6',
              color: tab === t.id ? '#fff' : '#374151',
            }}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {tab === 'overview' && (
        <section className="card" style={{ padding: 16 }}>
          <p>
            <strong>Case manager:</strong> {caseRow.caseManagerName || '—'}
          </p>
          <p>
            <strong>Latest report:</strong> {caseRow.latestApprovedReportMonth || '—'}
          </p>
          <p>
            <strong>IEP:</strong> {caseRow.iepStatus || '—'}
          </p>
          {caseRow.isHomecare && caseRow.serviceAddressSummary ? (
            <p>
              <strong>Service address:</strong> {caseRow.serviceAddressSummary}
            </p>
          ) : null}
          {caseRow.upcomingBooking ? (
            <p>
              <strong>Next booking:</strong> {caseRow.upcomingBooking}
            </p>
          ) : null}
          <div style={{ display: 'flex', gap: 8, marginTop: 16, flexWrap: 'wrap' }}>
            <Link to="/parent/book" style={{ padding: '8px 16px', borderRadius: 8, background: '#6366f1', color: '#fff', textDecoration: 'none', fontWeight: 600 }}>
              Book appointment
            </Link>
            {caseRow.isHomecare ? (
              <Link to="/parent/profile" style={{ padding: '8px 16px', borderRadius: 8, border: '1px solid #d1d5db', textDecoration: 'none' }}>
                Update service address
              </Link>
            ) : null}
          </div>
        </section>
      )}

      {tab === 'sessions' && (
        <section>
          {logs.length === 0 ? (
            <p style={{ color: '#9ca3af' }}>No approved session updates yet.</p>
          ) : (
            <ul className="log-list">
              {logs.map((log) => (
                <li key={log.id}>
                  <div>
                    <p>{log.scheduled_date}</p>
                    <span>
                      {log.attendance_status} · {log.therapist_name}
                    </span>
                  </div>
                  {log.parent_notes ? <p style={{ marginTop: 8 }}>{log.parent_notes}</p> : null}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {tab === 'reports' && (
        <section>
          {reports.length === 0 ? (
            <p style={{ color: '#9ca3af' }}>No published reports for this case yet.</p>
          ) : (
            <ul className="log-list">
              {reports.map((r) => (
                <li key={r.id}>
                  <div>
                    <p>{r.month}</p>
                    <span>{r.summary?.slice(0, 80)}…</span>
                  </div>
                  <button type="button" onClick={() => openReport(r)}>
                    View
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {tab === 'bookings' && (
        <section>
          {appointments.length === 0 ? (
            <p style={{ color: '#9ca3af' }}>
              No upcoming bookings. <Link to="/parent/book">Book a session</Link>
            </p>
          ) : (
            <ul className="log-list">
              {appointments.map((a) => (
                <li key={a.id}>
                  <div>
                    <p>
                      {a.slotDate} · {String(a.startTime).slice(0, 5)}–{String(a.endTime).slice(0, 5)}
                    </p>
                    <span>{a.therapistName}</span>
                  </div>
                  <button type="button" onClick={() => cancelAppointment(a.id)}>
                    Cancel
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {selectedReport ? (
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
          <div style={{ background: '#fff', borderRadius: 16, padding: 24, maxWidth: 520, width: '100%' }}>
            <h2 style={{ marginTop: 0 }}>{selectedReport.month}</h2>
            <p style={{ color: '#6b7280' }}>{selectedReport.childName}</p>
            <p style={{ whiteSpace: 'pre-wrap' }}>{selectedReport.summary}</p>
            <button type="button" onClick={() => setSelectedReport(null)} style={{ marginTop: 16 }}>
              Close
            </button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
