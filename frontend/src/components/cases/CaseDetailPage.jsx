import { useCallback, useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { mergeUpcomingSchedule } from '../../lib/therapistSchedule.js'
import { therapistTicketsUrl } from '../../lib/therapistTicketOptions.js'
import { moduleLabel } from '../../lib/moduleLabels.js'
import { CaseSessionsPanel } from './CaseSessionsPanel.jsx'
import { CaseDocumentsPanel } from '../documents/CaseDocumentsPanel.jsx'
import { CaseManagerPanel } from './CaseManagerPanel.jsx'
import { CaseOperationalTimeline } from './CaseOperationalTimeline.jsx'
import { ObservationChecklistPanel } from './ObservationChecklistPanel.jsx'
import './my-cases.css'

const TABS = [
  { id: 'overview', label: 'Overview', shortLabel: 'Overview' },
  { id: 'observation', label: 'Observation', shortLabel: 'Observe' },
  { id: 'sessions', label: 'Sessions & logs', shortLabel: 'Sessions' },
  { id: 'documents', label: 'Documents', shortLabel: 'Docs' },
]

const CLINICAL_SECTIONS = [
  { id: 'diagnosis', title: 'Diagnosis', key: 'diagnosis' },
  { id: 'strengths', title: 'Strengths', key: 'strengths' },
  { id: 'interests', title: 'Interests', key: 'interests' },
  { id: 'goals', title: 'Goals', key: 'goals_summary' },
]

export function CaseDetailPage() {
  const { caseId } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'overview'
  const [caseRow, setCaseRow] = useState(null)
  const [scheduleItems, setScheduleItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [clinicalProfile, setClinicalProfile] = useState(null)
  const [statusPending, setStatusPending] = useState(null)
  const [statusHistory, setStatusHistory] = useState([])

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const today = new Date()
      const from = today.toISOString().slice(0, 10)
      const toDate = new Date(today)
      toDate.setDate(toDate.getDate() + 90)
      const to = toDate.toISOString().slice(0, 10)

      const [c, upcoming, slots, profile, statusReqs] = await Promise.all([
        apiFetch(`/api/v1/cases/${caseId}`),
        apiFetch('/api/v1/sessions/upcoming?days=90').catch(() => []),
        apiFetch(`/api/v1/slots?from_date=${from}&to_date=${to}`).catch(() => []),
        apiFetch(`/api/v1/cases/${caseId}/clinical-profile`).catch(() => null),
        apiFetch(`/api/v1/cases/${caseId}/status-requests`).catch(() => ({ pending: null, history: [] })),
      ])
      setCaseRow(c)
      setClinicalProfile(profile)
      setStatusPending(statusReqs?.pending || null)
      setStatusHistory(statusReqs?.history || [])
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
  const modLabel = moduleLabel(caseRow.product_module)
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
          {caseRow.service_type ? (
            <span className="ic-case-service-chip">{caseRow.service_type}</span>
          ) : null}
          {modLabel ? <span className="ic-case-module-badge">{modLabel}</span> : null}
        </p>
        {statusPending ? (
          <p className="ic-case-detail__pending-banner" role="status">
            {statusPending.toStatus === 'SUSPENDED'
              ? 'Pause'
              : statusPending.toStatus === 'CLOSED'
                ? 'Close'
                : 'Status'}{' '}
            requested — waiting for admin approval. Case stays {statusLabel} until reviewed.
          </p>
        ) : null}
      </header>

      <nav className="ic-case-tabs" aria-label="Case sections">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`ic-case-tabs__btn${tab === t.id ? ' is-active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            <span className="ic-case-tabs__label-full">{t.label}</span>
            <span className="ic-case-tabs__label-short">{t.shortLabel || t.label}</span>
          </button>
        ))}
        <Link
          to={therapistTicketsUrl({ topic: 'CASE_MANAGER', caseId, openForm: true })}
          className="ic-case-tabs__support"
        >
          Contact support
        </Link>
      </nav>

      {tab === 'overview' ? (
        <div className="ic-case-detail__grid">
          <section className="ic-case-highlight">
            <p className="ic-case-highlight__eyebrow">Client history</p>
            {clinicalProfile?.history ? (
              <p className="ic-case-highlight__body">{clinicalProfile.history}</p>
            ) : (
              <>
                <p className="ic-case-highlight__sub">
                  Clinical history will appear here after your case manager reviews the observation checklist.
                </p>
                <Link to={`/therapist/cases/${caseId}?tab=observation`} className="ic-btn ic-btn--ghost">
                  Open observation tab
                </Link>
              </>
            )}
          </section>

          <CaseOperationalTimeline history={statusHistory} />

          <CaseManagerPanel caseRow={caseRow} />

          <section className="ic-case-panel">
            <h3>Client snapshot</h3>
            <dl className="ic-case-stat-grid">
              <div>
                <dt>Child</dt>
                <dd>{caseRow.child_name}</dd>
              </div>
              <div>
                <dt>Service</dt>
                <dd>{caseRow.service_type || '—'}</dd>
              </div>
              <div>
                <dt>Programme</dt>
                <dd>{modLabel || '—'}</dd>
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
                <div className="ic-case-stat-grid__wide">
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

          {CLINICAL_SECTIONS.map((section) => {
            const value = clinicalProfile?.[section.key]
            return (
              <section
                key={section.id}
                className={`ic-case-panel${value ? '' : ' ic-case-panel--placeholder'}`}
              >
                <h3>{section.title}</h3>
                {value ? (
                  <p className="ic-case-clinical-body">{value}</p>
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
