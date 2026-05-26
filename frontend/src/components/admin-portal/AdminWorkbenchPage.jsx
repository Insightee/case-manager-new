import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'
import { AdminPageHeader, AdminPanel } from './ui/index.js'
import { AdminObservationChecklistsPanel } from './AdminObservationChecklistsPanel.jsx'
import './admin-reports.css'

const SECTION_META = {
  observations: { title: 'Observation checklists', empty: 'No checklists awaiting review.' },
  status_requests: { title: 'Case status requests', empty: 'No pending status change requests.' },
  client_claims: { title: 'Client payment claims', empty: 'No payment claims awaiting review.' },
  reports: { title: 'Reports to review', empty: 'No reports awaiting review.' },
  logs: { title: 'Session logs pending', empty: 'No logs pending approval.' },
  tickets: { title: 'Open support tickets', empty: 'No open tickets on your caseload.' },
  incidents: { title: 'Active incidents', empty: 'No active incidents.' },
  iep: { title: 'IEP attention', empty: 'All IEP documents up to date.' },
  meetings: { title: 'Upcoming CM meetings', empty: 'No scheduled meetings.' },
  reschedules: { title: 'Pending reschedules', empty: 'No reschedule requests awaiting confirmation.' },
}

function WorkbenchSection({ id, section }) {
  const meta = SECTION_META[id] || { title: id, empty: 'Nothing here.' }
  const items = section?.items || []
  return (
    <AdminPanel title={`${meta.title} (${section?.count ?? items.length})`} padded={false}>
      <div className="admin-panel__body">
        {items.length === 0 ? (
          <p className="admin-muted" style={{ padding: '12px 16px' }}>{meta.empty}</p>
        ) : (
          <ul className="admin-queue">
            {items.map((item) => (
              <li key={`${id}-${item.id}`} className="admin-queue__item">
                <div>
                  <p className="admin-queue__title">
                    {item.label || item.subject || item.title || `#${item.id}`}
                  </p>
                  <p className="admin-queue__meta">
                    {item.case_code ? `${item.case_code} · ` : ''}
                    {item.child_name || ''}
                    {item.status ? ` · ${item.status}` : ''}
                    {item.iep_status ? ` · ${item.iep_status}` : ''}
                    {item.scheduled_date ? ` · ${item.scheduled_date}` : ''}
                  </p>
                </div>
                <Link to={item.href} className="admin-btn admin-btn--ghost admin-btn--sm">
                  Open →
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </AdminPanel>
  )
}

function StatusRequestsPanel() {
  const { canEditProductCase } = useModuleWrite()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [acting, setActing] = useState(null)
  const [rejectId, setRejectId] = useState(null)
  const [rejectNote, setRejectNote] = useState('')

  function load() {
    setLoading(true)
    apiFetch('/api/v1/admin/status-requests')
      .then(setRows)
      .catch(() => setRows([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

  async function approve(id) {
    setActing(id)
    try {
      await apiFetch(`/api/v1/admin/status-requests/${id}/approve`, {
        method: 'POST',
        body: JSON.stringify({ note: '' }),
      })
      load()
    } finally {
      setActing(null)
    }
  }

  async function reject(id) {
    if (!rejectNote.trim()) return
    setActing(id)
    try {
      await apiFetch(`/api/v1/admin/status-requests/${id}/reject`, {
        method: 'POST',
        body: JSON.stringify({ note: rejectNote.trim() }),
      })
      setRejectId(null)
      setRejectNote('')
      load()
    } finally {
      setActing(null)
    }
  }

  return (
    <AdminPanel title={`Case status requests (${rows.length})`} padded={false}>
      <div className="admin-panel__body">
        {loading ? (
          <p className="admin-muted" style={{ padding: 12 }}>Loading…</p>
        ) : rows.length === 0 ? (
          <p className="admin-muted" style={{ padding: 12 }}>No pending status change requests.</p>
        ) : (
          <ul className="admin-queue">
            {rows.map((r) => {
              const canAct = canEditProductCase(r.productModule || 'homecare')
              return (
              <li key={r.id} className="admin-queue__item" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
                <p className="admin-queue__title">
                  {r.caseId} · {r.childName}: {r.fromStatus} → {r.toStatus}
                </p>
                <p className="admin-queue__meta">{r.requestedBy} · {r.reason}</p>
                {rejectId === r.id ? (
                  <textarea
                    className="client-inv__filter-input"
                    style={{ width: '100%', marginTop: 8, minHeight: 48 }}
                    placeholder="Reason if rejecting"
                    value={rejectNote}
                    onChange={(e) => setRejectNote(e.target.value)}
                  />
                ) : null}
                {canAct ? (
                <div className="admin-btn-group" style={{ marginTop: 8 }}>
                  <button
                    type="button"
                    className="admin-btn admin-btn--primary admin-btn--sm"
                    disabled={acting === r.id}
                    onClick={() => approve(r.id)}
                  >
                    Approve
                  </button>
                  {rejectId === r.id ? (
                    <button
                      type="button"
                      className="admin-btn admin-btn--sm"
                      disabled={acting === r.id || !rejectNote.trim()}
                      onClick={() => reject(r.id)}
                    >
                      Confirm reject
                    </button>
                  ) : (
                    <button type="button" className="admin-btn admin-btn--sm" onClick={() => setRejectId(r.id)}>
                      Reject…
                    </button>
                  )}
                  {r.caseDbId ? (
                    <Link to={`/admin/cases/${r.caseDbId}`} className="admin-btn admin-btn--ghost admin-btn--sm">
                      Case
                    </Link>
                  ) : null}
                </div>
                ) : (
                  <p className="admin-muted" style={{ marginTop: 8, fontSize: '0.8rem' }}>
                    View-only for this programme module.
                  </p>
                )}
              </li>
            )})}
          </ul>
        )}
      </div>
    </AdminPanel>
  )
}

export function AdminWorkbenchPage() {
  const { can } = useAuth()
  const { canReviewReports, canWriteBilling } = useModuleWrite()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiFetch('/api/v1/admin/workbench/summary')
      .then(setData)
      .catch(() => setData({ sections: {} }))
      .finally(() => setLoading(false))
  }, [])

  const sections = data?.sections || {}
  const baseOrder = [
    'observations',
    'status_requests',
    'client_claims',
    'reports',
    'logs',
    'reschedules',
    'tickets',
    'incidents',
    'iep',
    'meetings',
  ]
  const order = baseOrder.filter((id) => {
    if (id === 'observations' && !canReviewReports('homecare') && !canReviewReports('shadow_support')) return false
    if (id === 'status_requests' && !can('case.update')) return false
    if (id === 'client_claims' && !canWriteBilling) return false
    if (id === 'tickets' && !can('ticket.manage')) return false
    if (id === 'incidents' && !can('incident.read_sensitive')) return false
    if (id === 'reports' && !canReviewReports('homecare') && !canReviewReports('shadow_support')) return false
    if (id === 'logs' && !can('daily_log.review')) return false
    if (id === 'iep' && !can('iep.read')) return false
    return sections[id]
  })
  const hasStatusSection = Boolean(sections.status_requests?.count)

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="Operations"
        title="Workbench"
        subtitle="Observation checklists, status requests, reports, logs, billing claims, and meetings for your caseload."
      />

      <p className="admin-muted" style={{ marginBottom: 16, fontSize: '0.875rem' }}>
        Scheduled CM supervision sessions are on{' '}
        <Link to="/admin/cm-meetings?queue=supervision" style={{ color: '#4f46e5', fontWeight: 600 }}>
          CM meetings (supervision filter)
        </Link>
        — not a separate supervisor request inbox.
      </p>

      {can('case.update') && !hasStatusSection ? <StatusRequestsPanel /> : null}
      {(canReviewReports('homecare') || canReviewReports('shadow_support')) ? (
        <AdminObservationChecklistsPanel />
      ) : null}

      {loading ? (
        <p className="admin-muted">Loading workbench…</p>
      ) : order.length === 0 ? (
        <p className="admin-muted">No work items right now.</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {order.map((id) => (
            <WorkbenchSection key={id} id={id} section={sections[id]} />
          ))}
        </div>
      )}
    </div>
  )
}
