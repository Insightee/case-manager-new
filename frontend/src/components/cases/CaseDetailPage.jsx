import { useCallback, useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { CaseSessionsPanel } from './CaseSessionsPanel.jsx'
import { CaseReportsPanel } from './CaseReportsPanel.jsx'
import { CaseBookingsPanel } from './CaseBookingsPanel.jsx'
import './my-cases.css'

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'sessions', label: 'Sessions & logs' },
  { id: 'reports', label: 'Reports' },
  { id: 'bookings', label: 'Bookings' },
]

export function CaseDetailPage() {
  const { caseId } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'overview'
  const [caseRow, setCaseRow] = useState(null)
  const [assignments, setAssignments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [c, a] = await Promise.all([
        apiFetch(`/api/v1/cases/${caseId}`),
        apiFetch(`/api/v1/cases/${caseId}/assignments`),
      ])
      setCaseRow(c)
      setAssignments(a || [])
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

  if (loading) return <p className="ic-my-cases" style={{ padding: 24 }}>Loading case…</p>
  if (error || !caseRow) {
    return (
      <div className="ic-my-cases" style={{ padding: 24 }}>
        <p style={{ color: '#b91c1c' }}>{error || 'Case not found'}</p>
        <Link to="/therapist/cases">Back to My Cases</Link>
      </div>
    )
  }

  const addr = caseRow.service_address?.formatted

  return (
    <div className="ic-my-cases">
      <p style={{ marginBottom: 8 }}>
        <Link to="/therapist/cases" style={{ fontSize: '0.875rem', color: '#6366f1', fontWeight: 600 }}>
          ← My Cases
        </Link>
      </p>
      <header style={{ marginBottom: 20 }}>
        <p style={{ fontSize: '0.75rem', fontWeight: 600, color: '#6366f1', textTransform: 'uppercase', margin: 0 }}>
          {caseRow.case_code}
        </p>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: '4px 0' }}>{caseRow.child_name}</h1>
        <p style={{ color: '#6b7280', margin: 0 }}>
          {caseRow.service_type} · {caseRow.product_module} · {caseRow.status}
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
              fontWeight: 600,
              fontSize: '0.875rem',
              cursor: 'pointer',
              background: tab === t.id ? '#6366f1' : '#f3f4f6',
              color: tab === t.id ? '#fff' : '#374151',
            }}
          >
            {t.label}
          </button>
        ))}
        <Link
          to={`/therapist/tickets`}
          style={{ marginLeft: 'auto', alignSelf: 'center', fontSize: '0.875rem', color: '#6366f1', fontWeight: 600 }}
        >
          Contact support
        </Link>
      </nav>

      {tab === 'overview' ? (
        <div style={{ display: 'grid', gap: 16, maxWidth: 640 }}>
          <section style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 20 }}>
            <h3 style={{ marginTop: 0, fontSize: '1rem' }}>Case details</h3>
            <dl style={{ margin: 0, fontSize: '0.875rem', display: 'grid', gap: 8 }}>
              <div>
                <dt style={{ color: '#6b7280' }}>Operational stage</dt>
                <dd style={{ margin: 0, fontWeight: 600 }}>{caseRow.operational_stage || '—'}</dd>
              </div>
              <div>
                <dt style={{ color: '#6b7280' }}>Region</dt>
                <dd style={{ margin: 0 }}>{caseRow.region || '—'}</dd>
              </div>
              {addr ? (
                <div>
                  <dt style={{ color: '#6b7280' }}>Service address</dt>
                  <dd style={{ margin: 0 }}>{addr}</dd>
                  {caseRow.maps_url ? (
                    <a href={caseRow.maps_url} target="_blank" rel="noreferrer" style={{ fontSize: '0.8rem' }}>
                      Open in Maps
                    </a>
                  ) : null}
                </div>
              ) : null}
            </dl>
          </section>
          {assignments.length ? (
            <section style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 20 }}>
              <h3 style={{ marginTop: 0, fontSize: '1rem' }}>Assignment</h3>
              {assignments.map((a) => (
                <p key={a.id} style={{ margin: 0, fontSize: '0.875rem' }}>
                  Therapist #{a.therapist_user_id} · {a.status} · from {a.start_date}
                </p>
              ))}
            </section>
          ) : null}
          <p style={{ fontSize: '0.8rem', color: '#9ca3af' }}>
            Prior therapist reports and escalation matrix — coming in a later update.
          </p>
        </div>
      ) : null}

      {tab === 'sessions' ? (
        <CaseSessionsPanel caseId={Number(caseId)} caseCode={caseRow.case_code} childName={caseRow.child_name} />
      ) : null}

      {tab === 'reports' ? (
        <CaseReportsPanel caseId={Number(caseId)} caseCode={caseRow.case_code} childName={caseRow.child_name} />
      ) : null}

      {tab === 'bookings' ? (
        <CaseBookingsPanel caseId={Number(caseId)} />
      ) : null}
    </div>
  )
}
