import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { apiFetch, apiDownload } from '../../lib/apiClient.js'
import { useParentDocumentsList } from '../../hooks/useCaseDocuments.js'
import { categoryLabel } from '../../lib/caseDocumentCategories.js'
import { ReportHtmlView } from '../reports/ReportHtmlView.jsx'
import '../cases/my-cases.css'
import '../documents/case-documents.css'
import '../reports/report-editor.css'

const TABS = [
  { id: 'overview', label: 'Profile' },
  { id: 'sessions', label: 'Session updates' },
  { id: 'observation', label: 'Observation' },
  { id: 'iep', label: 'IEP' },
  { id: 'goals', label: 'Goals' },
  { id: 'documents', label: 'Documents' },
  { id: 'bookings', label: 'Bookings' },
]

function StatusChip({ status }) {
  const tone =
    status === 'approved' || status === 'acknowledged'
      ? 'completed'
      : status === 'changes_sent'
        ? 'warning'
        : 'pending'
  return <span className={`status ${tone}`}>{status === 'pending_review' ? 'Pending your review' : status}</span>
}

export function ParentCaseDetailPage() {
  const { caseId } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'overview'
  const [caseRow, setCaseRow] = useState(null)
  const [summary, setSummary] = useState(null)
  const [logs, setLogs] = useState([])
  const [hub, setHub] = useState({ monthly: [], iep: [] })
  const [observations, setObservations] = useState([])
  const [appointments, setAppointments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [acting, setActing] = useState(false)

  const { data: allParentDocs = [], isLoading: docsLoading } = useParentDocumentsList({
    enabled: tab === 'documents',
  })
  const caseDocs = useMemo(
    () => allParentDocs.filter((d) => String(d.caseDbId ?? d.case_id) === String(caseId)),
    [allParentDocs, caseId],
  )

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [c, hubData, obs, allLogs, allAppts, sum] = await Promise.all([
        apiFetch(`/api/v1/parent/cases/${caseId}`),
        apiFetch('/api/v1/parent/reports/hub'),
        apiFetch(`/api/v1/parent/cases/${caseId}/observation-reports`).catch(() => []),
        apiFetch(`/api/v1/parent/session-logs?case_id=${caseId}`),
        apiFetch('/api/v1/parent/appointments'),
        apiFetch(`/api/v1/parent/cases/${caseId}/reports-summary`).catch(() => null),
      ])
      setCaseRow(c)
      setHub({
        monthly: (hubData?.monthly || []).filter((r) => String(r.caseDbId) === String(caseId)),
        iep: (hubData?.iep || []).filter((r) => String(r.caseDbId) === String(caseId)),
      })
      setObservations(obs || [])
      setLogs(allLogs || [])
      setAppointments((allAppts || []).filter((a) => String(a.caseDbId) === String(caseId)))
      setSummary(sum)
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
    setDetail(null)
  }

  const goalsFromLogs = useMemo(() => {
    const items = []
    for (const log of logs) {
      if (log.goals_addressed) {
        items.push({
          id: log.id,
          date: log.scheduled_date,
          text: log.goals_addressed,
          therapist: log.therapist_name,
        })
      }
    }
    return items
  }, [logs])

  async function openMonthly(report) {
    setDetailLoading(true)
    try {
      const d = await apiFetch(`/api/v1/parent/reports/monthly/${report.id}`)
      setDetail(d)
    } catch (err) {
      setError(err.message || 'Could not load report')
    } finally {
      setDetailLoading(false)
    }
  }

  async function openObservation(report) {
    setDetailLoading(true)
    try {
      const d = await apiFetch(`/api/v1/parent/reports/observation/${report.id}`)
      setDetail(d)
    } catch (err) {
      setError(err.message || 'Could not load report')
    } finally {
      setDetailLoading(false)
    }
  }

  async function openIep(item) {
    setDetailLoading(true)
    try {
      const d = await apiFetch(`/api/v1/parent/reports/iep/${item.id}`)
      setDetail(d)
    } catch (err) {
      setError(err.message || 'Could not load IEP')
    } finally {
      setDetailLoading(false)
    }
  }

  async function openDocument(doc) {
    setDetailLoading(true)
    try {
      const d = await apiFetch(`/api/v1/parent/documents/${doc.id}`)
      setDetail({ ...d, kind: 'case_document' })
    } catch (err) {
      setError(err.message || 'Could not load document')
    } finally {
      setDetailLoading(false)
    }
  }

  async function cancelAppointment(slotId) {
    try {
      await apiFetch(`/api/v1/parent/appointments/${slotId}/cancel`, { method: 'POST' })
      setMessage('Session cancelled.')
      await load()
    } catch (err) {
      setError(err.message || 'Could not cancel')
    }
  }

  async function acknowledgeIep() {
    if (!detail || detail.kind !== 'iep') return
    setActing(true)
    try {
      await apiFetch(`/api/v1/parent/reports/iep/${detail.id}/acknowledge`, { method: 'POST' })
      setMessage('IEP acknowledged.')
      setDetail(null)
      await load()
    } catch (err) {
      setError(err.message || 'Could not acknowledge')
    } finally {
      setActing(false)
    }
  }

  if (loading) return <p style={{ color: '#6b7280' }}>Loading case…</p>
  if (error || !caseRow) {
    return (
      <div>
        <p style={{ color: '#b91c1c' }}>{error || 'Case not found'}</p>
        <Link to="/parent/reports">Back to reports</Link>
      </div>
    )
  }

  return (
    <div className="parent-case-hub">
      <p style={{ marginBottom: 8 }}>
        <Link to="/parent/reports" style={{ fontSize: '0.875rem', color: '#6366f1', fontWeight: 600 }}>
          ← Reports & documents
        </Link>
      </p>
      <header style={{ marginBottom: 16 }}>
        <p style={{ fontSize: '0.75rem', fontWeight: 600, color: '#6366f1', textTransform: 'uppercase', margin: 0 }}>
          Case {caseRow.caseId}
        </p>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: '4px 0' }}>{caseRow.childName}</h1>
        <p style={{ color: '#6b7280', margin: 0 }}>
          {caseRow.serviceType} · Therapist: {caseRow.therapistName || '—'} · Case manager:{' '}
          {caseRow.caseManagerName || '—'}
        </p>
      </header>

      {message ? (
        <p style={{ padding: '8px 12px', background: '#ecfdf5', borderRadius: 8, color: '#047857', marginBottom: 12 }}>
          {message}
        </p>
      ) : null}
      {error ? (
        <p role="alert" style={{ color: '#b91c1c', marginBottom: 12 }}>
          {error}
        </p>
      ) : null}

      <nav className="ic-case-tabs" aria-label="Child case sections">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`ic-case-tabs__btn${tab === t.id ? ' is-active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
            {summary && t.id === 'observation' && summary.observationCount > 0 ? ` (${summary.observationCount})` : ''}
            {summary && t.id === 'documents' && summary.documentsCount > 0 ? ` (${summary.documentsCount})` : ''}
          </button>
        ))}
      </nav>

      {tab === 'overview' && (
        <section className="card" style={{ padding: 16 }}>
          <p style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: 12, lineHeight: 1.45 }}>
            This is your child&apos;s care record with Insighte. Use the tabs above for session notes, clinical reports,
            IEP, goals, and shared documents.
          </p>
          <dl style={{ display: 'grid', gap: 8, margin: 0 }}>
            <div>
              <dt style={{ fontSize: '0.7rem', color: '#94a3b8', textTransform: 'uppercase' }}>Case number</dt>
              <dd style={{ margin: 0, fontWeight: 600 }}>{caseRow.caseId}</dd>
            </div>
            <div>
              <dt style={{ fontSize: '0.7rem', color: '#94a3b8', textTransform: 'uppercase' }}>Service</dt>
              <dd style={{ margin: 0 }}>{caseRow.serviceType}</dd>
            </div>
            <div>
              <dt style={{ fontSize: '0.7rem', color: '#94a3b8', textTransform: 'uppercase' }}>Latest monthly report</dt>
              <dd style={{ margin: 0 }}>{caseRow.latestApprovedReportMonth || '—'}</dd>
            </div>
            <div>
              <dt style={{ fontSize: '0.7rem', color: '#94a3b8', textTransform: 'uppercase' }}>IEP status</dt>
              <dd style={{ margin: 0 }}>{caseRow.iepStatus || '—'}</dd>
            </div>
          </dl>
          <div style={{ display: 'flex', gap: 8, marginTop: 16, flexWrap: 'wrap' }}>
            <Link to="/parent/book" className="admin-btn admin-btn--primary" style={{ textDecoration: 'none' }}>
              Book session
            </Link>
            {caseRow.isHomecare ? (
              <Link to="/parent/profile" className="admin-btn admin-btn--secondary" style={{ textDecoration: 'none' }}>
                Service address
              </Link>
            ) : null}
          </div>
        </section>
      )}

      {tab === 'sessions' && (
        <section className="card" style={{ padding: 16 }}>
          {logs.length === 0 ? (
            <p style={{ color: '#9ca3af' }}>No approved session updates yet.</p>
          ) : (
            <ul className="log-list">
              {logs.map((log) => (
                <li key={log.id}>
                  <div>
                    <p style={{ margin: 0, fontWeight: 600 }}>{log.scheduled_date}</p>
                    <span>
                      {log.attendance_status} · {log.therapist_name}
                    </span>
                  </div>
                  {log.parent_notes ? <p style={{ marginTop: 8 }}>{log.parent_notes}</p> : null}
                  {log.activities_done ? (
                    <p style={{ marginTop: 8, fontSize: '0.875rem', color: '#475569' }}>{log.activities_done}</p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {tab === 'observation' && (
        <section className="card" style={{ padding: 16 }}>
          {observations.length === 0 ? (
            <p style={{ color: '#9ca3af' }}>No observation reports shared yet.</p>
          ) : (
            <ul className="log-list">
              {observations.map((r) => (
                <li key={r.id}>
                  <button type="button" onClick={() => openObservation(r)} style={{ width: '100%', textAlign: 'left' }}>
                    <p style={{ margin: 0, fontWeight: 600 }}>{r.title}</p>
                    <span style={{ fontSize: 13, color: '#6b7280' }}>{r.reportDate || 'Observation report'}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {tab === 'iep' && (
        <section className="card" style={{ padding: 16 }}>
          {hub.iep.length === 0 ? (
            <p style={{ color: '#9ca3af' }}>No IEP documents shared yet.</p>
          ) : (
            <ul className="log-list">
              {hub.iep.map((r) => (
                <li key={r.id}>
                  <button type="button" onClick={() => openIep(r)} style={{ width: '100%', textAlign: 'left' }}>
                    <p style={{ margin: 0, fontWeight: 600 }}>
                      {r.label} · {r.fileName}
                    </p>
                    <StatusChip status={r.status === 'acknowledged' ? 'acknowledged' : 'pending'} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {tab === 'goals' && (
        <section className="card" style={{ padding: 16 }}>
          {goalsFromLogs.length === 0 ? (
            <p style={{ color: '#9ca3af' }}>Goals from approved sessions will appear here.</p>
          ) : (
            <ul className="log-list">
              {goalsFromLogs.map((g) => (
                <li key={g.id}>
                  <p style={{ margin: 0, fontWeight: 600 }}>{g.date}</p>
                  <span style={{ fontSize: 13, color: '#6b7280' }}>{g.therapist}</span>
                  <p style={{ marginTop: 8, whiteSpace: 'pre-wrap' }}>{g.text}</p>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {tab === 'documents' && (
        <section className="card" style={{ padding: 16 }}>
          {docsLoading ? (
            <p style={{ color: '#9ca3af' }}>Loading…</p>
          ) : caseDocs.length === 0 ? (
            <p style={{ color: '#9ca3af' }}>No documents shared for this case yet.</p>
          ) : (
            <ul className="log-list">
              {caseDocs.map((doc) => (
                <li key={doc.id}>
                  <button type="button" onClick={() => openDocument(doc)} style={{ width: '100%', textAlign: 'left' }}>
                    <p style={{ margin: 0, fontWeight: 600 }}>{doc.title}</p>
                    <span style={{ fontSize: 13, color: '#6b7280' }}>{categoryLabel(doc.category)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {tab === 'bookings' && (
        <section className="card" style={{ padding: 16 }}>
          {appointments.length === 0 ? (
            <p style={{ color: '#9ca3af' }}>
              No upcoming bookings. <Link to="/parent/book">Book a session</Link>
            </p>
          ) : (
            <ul className="log-list">
              {appointments.map((a) => (
                <li key={a.id}>
                  <div>
                    <p style={{ margin: 0, fontWeight: 600 }}>
                      {a.slotDate} · {String(a.startTime).slice(0, 5)}
                      {a.endTime ? `–${String(a.endTime).slice(0, 5)}` : ''}
                    </p>
                    <span>{a.therapistName}</span>
                  </div>
                  {a.can_cancel ? (
                    <button type="button" onClick={() => cancelAppointment(a.id)}>
                      Cancel
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {tab === 'reports' || (hub.monthly.length > 0 && tab === 'overview') ? null : null}

      {hub.monthly.length > 0 && tab === 'overview' ? (
        <section className="card" style={{ padding: 16, marginTop: 12 }}>
          <h3 style={{ marginTop: 0, fontSize: '1rem' }}>Monthly reports</h3>
          <ul className="log-list">
            {hub.monthly.map((r) => (
              <li key={r.id}>
                <button type="button" onClick={() => openMonthly(r)}>
                  {r.month} · <StatusChip status={r.status} />
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {(detail || detailLoading) && (
        <div className="parent-case-hub__modal" role="dialog" aria-modal="true">
          <div className="parent-case-hub__modal-panel">
            {detailLoading ? (
              <p>Loading…</p>
            ) : (
              <>
                <h2 style={{ marginTop: 0 }}>
                  {detail.title || detail.month || detail.fileName || 'Report'}
                </h2>
                <p style={{ color: '#6b7280' }}>{detail.childName}</p>
                {detail.bodyHtml ? <ReportHtmlView html={detail.bodyHtml} /> : null}
                {detail.summary && !detail.bodyHtml ? (
                  <p style={{ whiteSpace: 'pre-wrap' }}>{detail.summary}</p>
                ) : null}
                {detail.content && !detail.bodyHtml ? (
                  <p style={{ whiteSpace: 'pre-wrap' }}>{detail.content}</p>
                ) : null}
                {detail.downloadPath ? (
                  <button
                    type="button"
                    className="admin-btn admin-btn--secondary"
                    style={{ marginTop: 12 }}
                    onClick={() =>
                      apiDownload(detail.downloadPath, `report_${detail.id}.pdf`).catch((e) =>
                        setError(e.message),
                      )
                    }
                  >
                    Download PDF
                  </button>
                ) : null}
                {detail.kind === 'iep' && detail.status !== 'acknowledged' ? (
                  <button
                    type="button"
                    className="admin-btn admin-btn--primary"
                    style={{ marginTop: 12 }}
                    disabled={acting}
                    onClick={acknowledgeIep}
                  >
                    Acknowledge IEP
                  </button>
                ) : null}
                <button type="button" className="admin-btn admin-btn--ghost" style={{ marginTop: 12 }} onClick={() => setDetail(null)}>
                  Close
                </button>
              </>
            )}
          </div>
        </div>
      )}

      <style>{`
        .parent-case-hub__modal { position: fixed; inset: 0; z-index: 50; background: rgba(15,23,42,0.45); display: flex; align-items: center; justify-content: center; padding: 16px; }
        .parent-case-hub__modal-panel { background: #fff; border-radius: 16px; padding: 24px; max-width: 640px; width: 100%; max-height: 90vh; overflow: auto; }
      `}</style>
    </div>
  )
}
