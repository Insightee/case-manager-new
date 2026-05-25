import { useCallback, useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { mergeUpcomingSchedule } from '../../lib/therapistSchedule.js'
import { CaseSessionsPanel } from './CaseSessionsPanel.jsx'
import { CaseDocumentsPanel } from '../documents/CaseDocumentsPanel.jsx'
import { CaseManagerPanel } from './CaseManagerPanel.jsx'
import { ObservationChecklistPanel } from './ObservationChecklistPanel.jsx'
import './my-cases.css'

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'observation', label: 'Observation' },
  { id: 'sessions', label: 'Sessions & logs' },
  { id: 'documents', label: 'Documents' },
]

const CLINICAL_PLACEHOLDERS = [
  { id: 'history', title: 'Client history' },
  { id: 'diagnosis', title: 'Diagnosis' },
  { id: 'strengths', title: 'Strengths' },
  { id: 'interests', title: 'Interests' },
  { id: 'goals', title: 'Goals' },
]

export function CaseDetailPage() {
  const { caseId } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'overview'
  const [caseRow, setCaseRow] = useState(null)
  const [scheduleItems, setScheduleItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [statusTo, setStatusTo] = useState('SUSPENDED')
  const [statusReason, setStatusReason] = useState('')
  const [statusMsg, setStatusMsg] = useState('')
  const [statusBusy, setStatusBusy] = useState(false)
  const [clinicalProfile, setClinicalProfile] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const today = new Date()
      const from = today.toISOString().slice(0, 10)
      const toDate = new Date(today)
      toDate.setDate(toDate.getDate() + 90)
      const to = toDate.toISOString().slice(0, 10)

      const [c, upcoming, slots, profile] = await Promise.all([
        apiFetch(`/api/v1/cases/${caseId}`),
        apiFetch('/api/v1/sessions/upcoming?days=90').catch(() => []),
        apiFetch(`/api/v1/slots?from_date=${from}&to_date=${to}`).catch(() => []),
        apiFetch(`/api/v1/cases/${caseId}/clinical-profile`).catch(() => null),
      ])
      setCaseRow(c)
      setClinicalProfile(profile)
      const upcomingList = Array.isArray(upcoming) ? upcoming : unwrapList(upcoming)
      const slotList = unwrapList(slots)
      const merged = mergeUpcomingSchedule({ sessions: upcomingList, slots: slotList }).filter(
        (i) => i.caseId === Number(caseId),
      )
      setScheduleItems(merged)
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

  if (loading) return <p className="ic-my-cases ic-case-detail__loading">Loading case…</p>
  if (error || !caseRow) {
    return (
      <div className="ic-my-cases ic-case-detail">
        <p className="ic-case-detail__error">{error || 'Case not found'}</p>
        <Link to="/therapist/cases" className="ic-case-detail__back">
          ← My Cases
        </Link>
      </div>
    )
  }

  const addr = caseRow.service_address?.formatted
  const childLabel = `${caseRow.child_name} (${caseRow.case_code})`
  const statusLabel =
    caseRow.status === 'ACTIVE'
      ? 'Active'
      : caseRow.status === 'SUSPENDED'
        ? 'Suspended'
        : caseRow.status === 'CLOSED'
          ? 'Closed'
          : caseRow.status === 'PENDING_ALLOTMENT'
            ? 'Pending allotment'
            : caseRow.status

  return (
    <div className="ic-my-cases ic-case-detail">
      <Link to="/therapist/cases" className="ic-case-detail__back">
        ← My Cases
      </Link>

      <header className="ic-case-detail__header">
        <p className="ic-case-detail__code">{caseRow.case_code}</p>
        <div className="ic-case-detail__title-row">
          <h1 className="ic-case-detail__name">{caseRow.child_name}</h1>
          <span className={`ic-case-status-pill ic-case-status-pill--${String(caseRow.status).toLowerCase()}`}>
            {statusLabel}
          </span>
        </div>
        <p className="ic-case-detail__meta">
          {caseRow.service_type} · {caseRow.product_module}
        </p>
      </header>

      <nav className="ic-case-tabs" aria-label="Case sections">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`ic-case-tabs__btn${tab === t.id ? ' is-active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
        <Link to="/therapist/tickets" className="ic-case-tabs__support">
          Contact support
        </Link>
      </nav>

      {tab === 'overview' ? (
        <div className="ic-case-detail__grid">
          <CaseManagerPanel caseRow={caseRow} />

          <section className="ic-case-panel">
            <h3>Request status change</h3>
            <p className="ic-case-panel__hint">
              Current status: <strong>{caseRow.status || '—'}</strong>. Submit a request for admin approval.
            </p>
            {statusMsg ? <p style={{ color: '#15803d', fontSize: '0.85rem' }}>{statusMsg}</p> : null}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 360 }}>
              <select
                value={statusTo}
                onChange={(e) => setStatusTo(e.target.value)}
                className="ic-case-panel__select"
                style={{ padding: 8, borderRadius: 8, border: '1px solid #e2e8f0' }}
              >
                <option value="SUSPENDED">Suspend case</option>
                <option value="CLOSED">Close case</option>
                <option value="ACTIVE">Reactivate case</option>
              </select>
              <textarea
                value={statusReason}
                onChange={(e) => setStatusReason(e.target.value)}
                rows={3}
                placeholder="Reason for this change (required)"
                style={{ padding: 8, borderRadius: 8, border: '1px solid #e2e8f0' }}
              />
              <button
                type="button"
                className="ic-btn ic-btn--ghost"
                disabled={statusBusy || statusReason.trim().length < 5}
                onClick={async () => {
                  setStatusBusy(true)
                  setStatusMsg('')
                  try {
                    await apiFetch(`/api/v1/cases/${caseId}/status-requests`, {
                      method: 'POST',
                      body: JSON.stringify({ to_status: statusTo, reason: statusReason.trim() }),
                    })
                    setStatusMsg('Request submitted. Your case manager will review it.')
                    setStatusReason('')
                  } catch (err) {
                    setStatusMsg(err.message || 'Could not submit request')
                  } finally {
                    setStatusBusy(false)
                  }
                }}
              >
                {statusBusy ? 'Submitting…' : 'Submit request'}
              </button>
            </div>
          </section>

          <section className="ic-case-panel">
            <h3>Quick actions</h3>
            <div className="ic-case-quick">
              <Link to={`/therapist/cases/${caseId}?tab=sessions`} className="ic-case-quick__item">
                <strong>Sessions & logs</strong>
                <span>Upcoming visits, start session, submit logs</span>
              </Link>
              <Link to={`/therapist/reports?case_id=${caseId}`} className="ic-case-quick__item">
                <strong>Monthly report</strong>
                <span>Draft and submit in Monthly Reports</span>
              </Link>
              <Link to="/therapist/logs" className="ic-case-quick__item">
                <strong>All session logs</strong>
                <span>Timer and logs across every client</span>
              </Link>
            </div>
          </section>

          <section className="ic-case-panel">
            <h3>Client snapshot</h3>
            <dl className="ic-case-dl">
              <div>
                <dt>Child</dt>
                <dd>{caseRow.child_name}</dd>
              </div>
              <div>
                <dt>Service</dt>
                <dd>
                  {caseRow.service_type} ({caseRow.product_module})
                </dd>
              </div>
              <div>
                <dt>Operational stage</dt>
                <dd>{caseRow.operational_stage || '—'}</dd>
              </div>
              <div>
                <dt>Region</dt>
                <dd>{caseRow.region || '—'}</dd>
              </div>
              {addr ? (
                <div>
                  <dt>Service address</dt>
                  <dd>
                    {addr}
                    {caseRow.maps_url ? (
                      <>
                        {' '}
                        <a href={caseRow.maps_url} target="_blank" rel="noreferrer">
                          Maps
                        </a>
                      </>
                    ) : null}
                  </dd>
                </div>
              ) : null}
            </dl>
            {caseRow.notes ? (
              <div className="ic-case-panel__notes">
                <p className="ic-case-panel__notes-label">Notes from operations</p>
                <p>{caseRow.notes}</p>
              </div>
            ) : null}
          </section>

          {CLINICAL_PLACEHOLDERS.map((section) => {
            const value =
              section.id === 'history'
                ? clinicalProfile?.history
                : section.id === 'diagnosis'
                  ? clinicalProfile?.diagnosis
                  : section.id === 'strengths'
                    ? clinicalProfile?.strengths
                    : section.id === 'interests'
                      ? clinicalProfile?.interests
                      : section.id === 'goals'
                        ? clinicalProfile?.goals_summary
                        : null
            return (
              <section
                key={section.id}
                className={`ic-case-panel${value ? '' : ' ic-case-panel--placeholder'}`}
              >
                <h3>{section.title}</h3>
                {value ? (
                  <p style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: '0.9rem' }}>{value}</p>
                ) : (
                  <p className="ic-case-panel__hint">
                    Complete the observation checklist; your case manager will populate this after review.
                  </p>
                )}
              </section>
            )
          })}
        </div>
      ) : null}

      {tab === 'observation' ? <ObservationChecklistPanel caseId={caseId} /> : null}

      {tab === 'sessions' ? (
        <CaseSessionsPanel
          caseId={Number(caseId)}
          caseCode={caseRow.case_code}
          childName={caseRow.child_name}
          childLabel={childLabel}
          scheduleItems={scheduleItems}
          bookedSlots={scheduleItems.filter((i) => i.kind === 'booking').map((i) => ({
            id: i.slotId,
            case_id: i.caseId,
            slot_date: i.date,
            start_time: i.startTime,
            end_time: i.endTime,
            status: 'BOOKED',
            booking_source: i.bookingSource,
          }))}
          onScheduleChange={load}
        />
      ) : null}

      {tab === 'documents' ? (
        <CaseDocumentsPanel
          caseId={Number(caseId)}
          variant="therapist"
          monthlyReportsPath={`/therapist/reports?case_id=${caseId}`}
        />
      ) : null}
    </div>
  )
}
