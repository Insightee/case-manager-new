import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { formatScheduleWhen, mergeUpcomingSchedule } from '../../lib/therapistSchedule.js'
import { CaseSessionsPanel } from './CaseSessionsPanel.jsx'
import './my-cases.css'

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'sessions', label: 'Sessions & logs' },
]

export function CaseDetailPage() {
  const { caseId } = useParams()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'overview'
  const [caseRow, setCaseRow] = useState(null)
  const [assignments, setAssignments] = useState([])
  const [scheduleItems, setScheduleItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const today = new Date()
      const from = today.toISOString().slice(0, 10)
      const toDate = new Date(today)
      toDate.setDate(toDate.getDate() + 90)
      const to = toDate.toISOString().slice(0, 10)

      const [c, a, upcoming, slots] = await Promise.all([
        apiFetch(`/api/v1/cases/${caseId}`),
        apiFetch(`/api/v1/cases/${caseId}/assignments`),
        apiFetch('/api/v1/sessions/upcoming?days=90').catch(() => []),
        apiFetch(`/api/v1/slots?from_date=${from}&to_date=${to}`).catch(() => []),
      ])
      setCaseRow(c)
      setAssignments(Array.isArray(a) ? a : [])
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

  useEffect(() => {
    if (tab === 'reports') {
      navigate(`/therapist/reports?case_id=${caseId}`, { replace: true })
    }
  }, [tab, caseId, navigate])

  const nextVisit = scheduleItems[0] || null

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

  return (
    <div className="ic-my-cases ic-case-detail">
      <Link to="/therapist/cases" className="ic-case-detail__back">
        ← My Cases
      </Link>

      <header className="ic-case-detail__header">
        <p className="ic-case-detail__code">{caseRow.case_code}</p>
        <h1 className="ic-case-detail__name">{caseRow.child_name}</h1>
        <p className="ic-case-detail__meta">
          {caseRow.service_type} · {caseRow.product_module} · {caseRow.status}
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
          {nextVisit ? (
            <section className="ic-case-highlight ic-case-highlight--visit">
              <p className="ic-case-highlight__eyebrow">Next visit</p>
              <p className="ic-case-highlight__title">{formatScheduleWhen(nextVisit)}</p>
              <p className="ic-case-highlight__sub">{nextVisit.subtitle}</p>
              <div className="ic-case-highlight__actions">
                <Link to={`/therapist/cases/${caseId}?tab=sessions`} className="ic-btn ic-btn--primary">
                  Start or log session
                </Link>
                <Link to="/therapist/slots" className="ic-btn ic-btn--ghost">
                  Calendar
                </Link>
              </div>
            </section>
          ) : (
            <section className="ic-case-highlight ic-case-highlight--muted">
              <p className="ic-case-highlight__eyebrow">Schedule</p>
              <p className="ic-case-highlight__title">No upcoming booking</p>
              <p className="ic-case-highlight__sub">Open your calendar to add availability or book this client.</p>
              <Link to="/therapist/slots" className="ic-btn ic-btn--primary">
                Open slots
              </Link>
            </section>
          )}

          <section className="ic-case-panel">
            <h3>Quick actions</h3>
            <div className="ic-case-quick">
              <Link to={`/therapist/cases/${caseId}?tab=sessions`} className="ic-case-quick__item">
                <strong>Session log</strong>
                <span>Start, end, or backfill a visit</span>
              </Link>
              <Link to={`/therapist/reports?case_id=${caseId}`} className="ic-case-quick__item">
                <strong>Monthly report</strong>
                <span>Draft and submit in Monthly Reports</span>
              </Link>
              <Link to="/therapist/logs" className="ic-case-quick__item">
                <strong>All session logs</strong>
                <span>Timer across every client</span>
              </Link>
            </div>
          </section>

          <section className="ic-case-panel">
            <h3>Case details</h3>
            <dl className="ic-case-dl">
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
          </section>

          {assignments.length ? (
            <section className="ic-case-panel">
              <h3>Assignment</h3>
              {assignments.map((a) => (
                <p key={a.id} className="ic-case-panel__line">
                  Therapist #{a.therapist_user_id} · {a.status} · from {a.start_date}
                </p>
              ))}
            </section>
          ) : null}

          {scheduleItems.length > 1 ? (
            <section className="ic-case-panel">
              <h3>All upcoming</h3>
              <ul className="ic-case-schedule-list">
                {scheduleItems.map((item) => (
                  <li key={item.key}>
                    <span>{formatScheduleWhen(item)}</span>
                    <span className="ic-case-schedule-list__sub">{item.subtitle}</span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>
      ) : null}

      {tab === 'sessions' ? (
        <CaseSessionsPanel
          caseId={Number(caseId)}
          caseCode={caseRow.case_code}
          childName={caseRow.child_name}
          childLabel={childLabel}
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

    </div>
  )
}
