import { useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext.jsx'
import { useAdminCmHome } from '../../hooks/useAdminCmHome.js'
import { AdminPageHeader, AdminPanel, AdminEmptyState, AdminSearchInput, AdminStatCard, StatusBadge } from './ui/index.js'
import './admin-cm-home.css'

const COLUMN_LABELS = {
  pending_allotment: 'Pending allotment',
  needs_therapist: 'Needs therapist',
  reassignment: 'Reassignment',
  reports_logs: 'Reports & logs',
  iep: 'IEP',
  compliance: 'Compliance',
  active: 'Active',
  closed: 'Closed',
}

const SECTION_META = {
  observations: { title: 'Observation checklists', empty: 'No checklists awaiting review.' },
  status_requests: { title: 'Status change requests', empty: 'No pending requests.' },
  reports: { title: 'Reports to review', empty: 'No reports in queue.' },
  logs: { title: 'Session logs', empty: 'No logs pending approval.' },
  reschedules: { title: 'Reschedules', empty: 'No reschedule requests.' },
  tickets: { title: 'Support tickets', empty: 'No open tickets.' },
  incidents: { title: 'Incidents', empty: 'No active incidents.' },
  iep: { title: 'IEP attention', empty: 'IEP up to date on caseload.' },
  meetings: { title: 'Upcoming CM meetings', empty: 'No meetings scheduled.' },
}

const SECTION_ORDER = [
  'observations',
  'status_requests',
  'reports',
  'logs',
  'reschedules',
  'tickets',
  'incidents',
  'iep',
  'meetings',
]

function caseHrefWithTab(href, tab) {
  if (!href) return href
  const [path, query = ''] = href.split('?')
  const params = new URLSearchParams(query)
  params.set('tab', tab)
  const qs = params.toString()
  return qs ? `${path}?${qs}` : path
}

function CaseloadTable({ rows, filter }) {
  const q = filter.trim().toLowerCase()
  const filtered = useMemo(() => {
    let list = rows || []
    if (q) {
      list = list.filter((r) => {
        const hay = `${r.case_code} ${r.child_name} ${r.service_type} ${r.therapist_name || ''} ${r.next_action || ''}`.toLowerCase()
        return hay.includes(q)
      })
    }
    return list
  }, [rows, q])

  if (!filtered.length) {
    return <AdminEmptyState title="No cases match" description="Try another search or allot a new case." />
  }

  return (
    <div className="admin-table-wrap">
      <table className="admin-table admin-cm-caseload-table">
        <thead>
          <tr>
            <th>Case</th>
            <th>Child</th>
            <th>Service</th>
            <th>Therapist</th>
            <th>Status</th>
            <th>Next action</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {filtered.map((row) => (
            <tr key={row.id} className={row.pipeline_column && row.pipeline_column !== 'active' ? 'admin-cm-caseload-table__row--attention' : ''}>
              <td>
                <span className="admin-table__primary">{row.case_code}</span>
              </td>
              <td>{row.child_name || '—'}</td>
              <td>{row.service_type}</td>
              <td>{row.therapist_name || '—'}</td>
              <td>
                <StatusBadge status={row.status} />
                {row.pipeline_column && row.pipeline_column !== 'active' ? (
                  <span className="admin-cm-pipeline-pill">{COLUMN_LABELS[row.pipeline_column] || row.pipeline_column}</span>
                ) : null}
              </td>
              <td className="admin-cm-next-action">{row.next_action || '—'}</td>
              <td>
                <div className="admin-btn-group">
                  <Link to={row.href} className="admin-btn admin-btn--primary admin-btn--sm">
                    Open
                  </Link>
                  {row.open_reports > 0 ? (
                    <Link
                      to={caseHrefWithTab(row.href, 'reports')}
                      className="admin-btn admin-btn--ghost admin-btn--sm"
                    >
                      Reports
                    </Link>
                  ) : null}
                  {row.missing_logs > 0 ? (
                    <Link to={caseHrefWithTab(row.href, 'logs')} className="admin-btn admin-btn--ghost admin-btn--sm">
                      Logs
                    </Link>
                  ) : null}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function QueueSection({ id, section }) {
  const meta = SECTION_META[id] || { title: id, empty: 'Nothing here.' }
  const items = section?.items || []
  if (!items.length) return null

  return (
    <AdminPanel title={`${meta.title} (${section.count ?? items.length})`} padded={false}>
      <div className="admin-panel__body">
        <ul className="admin-queue">
          {items.map((item) => (
            <li key={`${id}-${item.id}`} className="admin-queue__item">
              <div>
                <p className="admin-queue__title">
                  {item.label || item.subject || item.title || item.child_name || `#${item.id}`}
                </p>
                <p className="admin-queue__meta">
                  {item.case_code ? `${item.case_code} · ` : ''}
                  {item.child_name || ''}
                  {item.status ? ` · ${String(item.status).replace(/_/g, ' ')}` : ''}
                </p>
              </div>
              <Link to={item.href || '/admin/workbench'} className="admin-btn admin-btn--ghost admin-btn--sm">
                Open →
              </Link>
            </li>
          ))}
        </ul>
        {(section.count ?? 0) > items.length ? (
          <p className="admin-muted" style={{ padding: '8px 16px 12px', fontSize: '0.8rem' }}>
            +{(section.count ?? 0) - items.length} more in full queue
          </p>
        ) : null}
      </div>
    </AdminPanel>
  )
}

export function AdminCaseManagerHomePage() {
  const { user, can, isViewOnly } = useAuth()
  const { data, isLoading, error, refetch } = useAdminCmHome()
  const [caseloadFilter, setCaseloadFilter] = useState('needs_action')
  const [search, setSearch] = useState('')
  const caseloadPanelRef = useRef(null)

  function selectCaseloadFilter(next) {
    setCaseloadFilter(next)
    window.requestAnimationFrame(() => {
      caseloadPanelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    })
  }

  const summary = data?.caseload_summary
  const allCaseload = data?.caseload || []

  const caseloadRows = useMemo(() => {
    if (caseloadFilter === 'all') return allCaseload
    if (caseloadFilter === 'needs_action') {
      return allCaseload.filter(
        (r) =>
          r.pipeline_column !== 'active' &&
          r.pipeline_column !== 'closed' &&
          r.status !== 'CLOSED',
      )
    }
    if (caseloadFilter === 'pending_allotment') {
      return allCaseload.filter((r) => r.status === 'PENDING_ALLOTMENT' || r.pipeline_column === 'pending_allotment')
    }
    return allCaseload.filter((r) => r.status === 'ACTIVE')
  }, [allCaseload, caseloadFilter])

  const sections = data?.sections || {}
  const sectionIds = SECTION_ORDER.filter((id) => sections[id]?.items?.length)

  return (
    <div className="admin-page admin-cm-home">
      <AdminPageHeader
        eyebrow="Case management"
        title={`Good day${user?.full_name ? `, ${user.full_name.split(' ')[0]}` : ''}`}
        subtitle="Your assigned caseload and clinical queues — cases needing review or allotment appear first."
        actions={
          <div className="admin-btn-group">
            {can('case.create') && !isViewOnly ? (
              <Link to="/admin/cases?allot=1" className="admin-btn admin-btn--primary admin-btn--sm">
                Allot case
              </Link>
            ) : null}
            <Link to="/admin/workbench" className="admin-btn admin-btn--secondary admin-btn--sm">
              All queues
            </Link>
            <Link to="/admin/cases" className="admin-btn admin-btn--ghost admin-btn--sm">
              Case list
            </Link>
          </div>
        }
      />

      {error ? (
        <p className="admin-alert admin-alert--error">
          {error.message || 'Could not load CM home'}
          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" style={{ marginLeft: 8 }} onClick={() => refetch()}>
            Retry
          </button>
        </p>
      ) : null}

      {isLoading ? (
        <p className="admin-muted">Loading your caseload…</p>
      ) : (
        <>
          <section className="admin-cm-stats" aria-label="Caseload summary" role="tablist">
            <AdminStatCard
              title="Needs action"
              value={summary?.needs_action ?? 0}
              tone="yellow"
              active={caseloadFilter === 'needs_action'}
              onClick={() => selectCaseloadFilter('needs_action')}
            />
            <AdminStatCard
              title="Pending allotment"
              value={summary?.pending_allotment ?? 0}
              tone="slate"
              active={caseloadFilter === 'pending_allotment'}
              onClick={() => selectCaseloadFilter('pending_allotment')}
            />
            <AdminStatCard
              title="Active"
              value={summary?.active ?? 0}
              tone="indigo"
              active={caseloadFilter === 'active'}
              onClick={() => selectCaseloadFilter('active')}
            />
            <AdminStatCard
              title="Total caseload"
              value={summary?.total ?? 0}
              tone="slate"
              active={caseloadFilter === 'all'}
              onClick={() => selectCaseloadFilter('all')}
            />
          </section>

          <div ref={caseloadPanelRef} className="admin-cm-caseload-panel">
            <AdminPanel title="My caseload" subtitle="Sorted by urgency — allotment and reviews first" padded={false}>
            <div className="admin-panel__body">
              <div style={{ padding: '12px 16px 0' }}>
                <AdminSearchInput value={search} onChange={setSearch} placeholder="Search caseload…" />
              </div>
              <div style={{ padding: '0 16px 16px' }}>
                <CaseloadTable rows={caseloadRows} filter={search} />
              </div>
            </div>
            </AdminPanel>
          </div>

          <section className="admin-cm-reports-hub" aria-label="Report management">
            <div className="admin-cm-reports-hub__head">
              <div>
                <h2 className="admin-cm-reports-hub__title">Report management</h2>
                <p className="admin-muted admin-cm-reports-hub__subtitle">
                  Review monthly, observation, CM meeting, and progress reports for your assigned cases.
                </p>
              </div>
              <div className="admin-btn-group">
                <Link to="/admin/reports?tab=queue" className="admin-btn admin-btn--primary admin-btn--sm">
                  Open review queue
                </Link>
                <Link to="/admin/reports?tab=all" className="admin-btn admin-btn--ghost admin-btn--sm">
                  All reports
                </Link>
              </div>
            </div>
            <div className="admin-cm-reports-hub__links">
              <Link to="/admin/reports?tab=queue" className="admin-cm-reports-hub__stat">
                <span className="admin-cm-reports-hub__stat-value">{sections.reports?.count ?? 0}</span>
                <span className="admin-cm-reports-hub__stat-label">In review queue</span>
              </Link>
              <Link to="/admin/reports?tab=iep" className="admin-cm-reports-hub__stat">
                <span className="admin-cm-reports-hub__stat-value">{sections.iep?.count ?? 0}</span>
                <span className="admin-cm-reports-hub__stat-label">IEP attention</span>
              </Link>
              <Link to="/admin/reports?tab=missing" className="admin-cm-reports-hub__stat">
                <span className="admin-cm-reports-hub__stat-label">Missing monthly →</span>
              </Link>
            </div>
          </section>

          {sectionIds.length > 0 ? (
            <div className="admin-cm-queues">
              <h2 className="admin-cm-queues__title">Action queues</h2>
              {sectionIds.map((id) => (
                <QueueSection key={id} id={id} section={sections[id]} />
              ))}
            </div>
          ) : (
            <AdminPanel title="Action queues">
              <p className="admin-muted">No pending reviews right now. Check back after therapists submit logs or reports.</p>
            </AdminPanel>
          )}
        </>
      )}
    </div>
  )
}
