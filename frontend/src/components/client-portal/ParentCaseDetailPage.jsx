import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { apiFetch, apiDownload } from '../../lib/apiClient.js'
import { formatDisplayDate } from '../../lib/datetime.js'
import { useParentDocumentsList } from '../../hooks/useCaseDocuments.js'
import { categoryLabel } from '../../lib/caseDocumentCategories.js'
import { ReportHtmlView } from '../reports/ReportHtmlView.jsx'
import { buildSessionDisputeState, SessionCard } from './SessionCard.jsx'
import '../cases/my-cases.css'
import '../documents/case-documents.css'
import '../reports/report-editor.css'
import './parent-case-hub.css'
import { IepReportRoute } from '../reports-engine/iep/IepReportRoute.jsx'
import { ObservationReportRoute } from '../reports-engine/observation/ObservationReportRoute.jsx'
import { isReportsRevampActive } from '../../lib/reportsRevampFlags.js'

const TABS = [
  { id: 'overview', label: 'Profile', shortLabel: 'Profile' },
  { id: 'sessions', label: 'Session updates', shortLabel: 'Sessions' },
  { id: 'observation', label: 'Observation', shortLabel: 'Observe' },
  { id: 'iep', label: 'IEP', shortLabel: 'IEP' },
  { id: 'goals', label: 'Goals', shortLabel: 'Goals' },
  { id: 'documents', label: 'Documents', shortLabel: 'Docs' },
  { id: 'bookings', label: 'Bookings', shortLabel: 'Book' },
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
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'overview'
  const clinicalRevamp = isReportsRevampActive('parent')
  const numericCaseId = Number(caseId)
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

  function handleSessionDispute(log) {
    navigate('/parent/support?tab=support', { state: buildSessionDisputeState(log) })
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
      <Link to="/parent/reports" className="parent-portal-link parent-case-hub__back">
        ← Reports & documents
      </Link>
      <header className="parent-case-hub__header">
        <div className="parent-case-hub__title-row">
          <p className="parent-case-hub__eyebrow">Case {caseRow.caseId}</p>
          <h1 className="parent-case-hub__title">{caseRow.childName}</h1>
        </div>
        {caseRow.serviceType ? (
          <span className="parent-case-hub__service-pill">{caseRow.serviceType}</span>
        ) : null}
        <dl className="parent-case-hub__care-team">
          <div className="parent-case-hub__care-item">
            <dt>Therapist</dt>
            <dd>{caseRow.therapistName || '—'}</dd>
          </div>
          <div className="parent-case-hub__care-item">
            <dt>Case manager</dt>
            <dd>{caseRow.caseManagerName || '—'}</dd>
          </div>
        </dl>
      </header>

      {message ? (
        <p className="parent-case-hub__flash parent-case-hub__flash--success" role="status">
          {message}
        </p>
      ) : null}
      {error ? (
        <p className="parent-case-hub__flash parent-case-hub__flash--error" role="alert">
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
            <span className="ic-case-tabs__label-full">
              {t.label}
              {summary && t.id === 'observation' && summary.observationCount > 0 ? ` (${summary.observationCount})` : ''}
              {summary && t.id === 'documents' && summary.documentsCount > 0 ? ` (${summary.documentsCount})` : ''}
            </span>
            <span className="ic-case-tabs__label-short">
              {t.shortLabel || t.label}
              {summary && t.id === 'observation' && summary.observationCount > 0 ? ` (${summary.observationCount})` : ''}
            </span>
          </button>
        ))}
      </nav>

      {tab === 'overview' && (
        <section className="parent-case-hub__profile card">
          <p className="parent-case-hub__profile-lead">
            Your child&apos;s care record in one place. Open the tabs above for session notes, reports, IEP, goals, and
            shared documents.
          </p>
          <dl className="parent-case-hub__facts">
            <div className="parent-case-hub__fact">
              <dt>Case number</dt>
              <dd>{caseRow.caseId}</dd>
            </div>
            <div className="parent-case-hub__fact">
              <dt>Service</dt>
              <dd>{caseRow.serviceType || '—'}</dd>
            </div>
            <div className="parent-case-hub__fact">
              <dt>Latest monthly report</dt>
              <dd>{caseRow.latestApprovedReportMonth || '—'}</dd>
            </div>
            <div className="parent-case-hub__fact">
              <dt>IEP status</dt>
              <dd>{caseRow.iepStatus || '—'}</dd>
            </div>
          </dl>
          <div className="parent-case-hub__profile-actions">
            <Link to="/parent/book" className="admin-btn admin-btn--primary">
              Book session
            </Link>
            {caseRow.isHomecare ? (
              <Link to="/parent/profile" className="admin-btn admin-btn--secondary">
                Service address
              </Link>
            ) : null}
          </div>
        </section>
      )}

      {tab === 'sessions' && (
        <>
          {logs.length === 0 ? (
            <p style={{ color: '#9ca3af' }}>No approved session updates yet.</p>
          ) : (
            logs.map((log, index) => (
              <SessionCard
                key={log.id}
                log={log}
                defaultExpanded={index === 0}
                onSaved={load}
                onDispute={handleSessionDispute}
              />
            ))
          )}
        </>
      )}

      {tab === 'observation' && (
        clinicalRevamp && Number.isFinite(numericCaseId) ? (
          <ObservationReportRoute
            caseId={numericCaseId}
            caseCode={caseRow.caseId || caseRow.case_code}
            childName={caseRow.childName}
            variant="parent"
          />
        ) : (
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
        )
      )}

      {tab === 'iep' && (
        clinicalRevamp && Number.isFinite(numericCaseId) ? (
          <IepReportRoute
            caseId={numericCaseId}
            caseCode={caseRow.caseId || caseRow.case_code}
            childName={caseRow.childName}
            variant="parent"
          />
        ) : (
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
        )
      )}

      {tab === 'goals' && (
        <section className="card" style={{ padding: 16 }}>
          {goalsFromLogs.length === 0 ? (
            <p style={{ color: '#9ca3af' }}>Goals from approved sessions will appear here.</p>
          ) : (
            <ul className="log-list">
              {goalsFromLogs.map((g) => (
                <li key={g.id}>
                  <p style={{ margin: 0, fontWeight: 600 }}>{formatDisplayDate(g.date)}</p>
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

    </div>
  )
}
