import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { IncidentDetailPanel } from '../support/IncidentDetailPanel.jsx'
import { AdminPageHeader, AdminPanel, AdminEmptyState, AdminToolbar, AdminSearchInput, StatusBadge } from './ui/index.js'
import '../support/support-tickets.css'

const STATUS_FILTERS = ['ALL', 'REPORTED', 'IN_REVIEW', 'ACTION_TAKEN', 'ESCALATED', 'CLOSED']

export function AdminIncidentsPage() {
  const [incidents, setIncidents] = useState([])
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('REPORTED')
  const [moduleFilter, setModuleFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState(null)
  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const qs = new URLSearchParams({ page_size: '100' })
      if (moduleFilter) qs.set('product_module', moduleFilter)
      setIncidents(unwrapList(await apiFetch(`/api/v1/incidents?${qs.toString()}`)))
    } catch {
      setIncidents([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return incidents.filter((i) => {
      if (statusFilter !== 'ALL' && i.status !== statusFilter) return false
      if (!q) return true
      return i.title?.toLowerCase().includes(q) || String(i.id).includes(q) || i.reporter_name?.toLowerCase().includes(q)
    })
  }, [incidents, search, statusFilter])

  const openCount = incidents.filter((i) => i.status !== 'CLOSED').length

  async function toggleExpand(inc) {
    if (expandedId === inc.id) {
      setExpandedId(null)
      setDetail(null)
      return
    }
    setExpandedId(inc.id)
    setDetailLoading(true)
    try {
      setDetail(await apiFetch(`/api/v1/incidents/${inc.id}`))
    } catch {
      setDetail(null)
    } finally {
      setDetailLoading(false)
    }
  }

  function onDetailUpdated(updated) {
    setDetail(updated)
    load()
  }

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="Risk & safety"
        title="Incidents"
        subtitle="Incident reports from therapists and clients. Review, investigate, and close each report here."
        actions={
          <span
            className="admin-chip"
            style={{
              background: openCount ? '#fef3c7' : '#d1fae5',
              color: openCount ? '#b45309' : '#047857',
            }}
          >
            {openCount} active
          </span>
        }
      />

      <AdminPanel title={`${filtered.length} incidents`} padded={false}>
        <div className="admin-panel__body">
          <AdminToolbar>
            <AdminSearchInput
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search title, reporter…"
            />
            <select
              className="admin-search__input"
              style={{ flex: '0 0 auto', width: 'auto', minWidth: 140, paddingLeft: 12, backgroundImage: 'none' }}
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              {STATUS_FILTERS.map((s) => (
                <option key={s} value={s}>
                  {s === 'ALL' ? 'All statuses' : s}
                </option>
              ))}
            </select>
            <select
              className="admin-search__input"
              style={{ flex: '0 0 auto', width: 'auto', minWidth: 150, paddingLeft: 12, backgroundImage: 'none' }}
              value={moduleFilter}
              onChange={(e) => setModuleFilter(e.target.value)}
            >
              <option value="">All modules</option>
              <option value="homecare">Homecare</option>
              <option value="shadow_support">Shadow support</option>
              <option value="billing">Billing</option>
            </select>
          </AdminToolbar>

          {loading ? (
            <div className="admin-skeleton" />
          ) : filtered.length === 0 ? (
            <AdminEmptyState
              title="No incidents"
              description="Incident reports filed by therapists and clients will appear here."
            />
          ) : (
            <ul className="admin-queue">
              {filtered.map((inc) => (
                <li
                  key={inc.id}
                  className="admin-queue__item"
                  style={{ flexDirection: 'column', alignItems: 'stretch' }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, width: '100%' }}>
                    <button
                      type="button"
                      onClick={() => toggleExpand(inc)}
                      style={{ flex: 1, textAlign: 'left', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                    >
                      <p className="admin-queue__title">
                        {inc.title}
                        {inc.is_sensitive ? (
                          <span className="admin-badge admin-badge--danger" style={{ marginLeft: 6 }}>
                            Sensitive
                          </span>
                        ) : null}
                      </p>
                      <p className="admin-queue__meta">
                        #{inc.id}
                        {inc.reporter_name ? ` · ${inc.reporter_name}` : ''}
                        {inc.case_code ? ` · ${inc.case_code}` : ''}
                        {inc.child_name ? ` · ${inc.child_name}` : ''}
                        {inc.case_id ? (
                          <>
                            {' '}·{' '}
                            <Link
                              to={`/admin/cases/${inc.case_id}`}
                              onClick={(e) => e.stopPropagation()}
                              style={{ color: '#6366f1' }}
                            >
                              View case
                            </Link>
                          </>
                        ) : null}
                      </p>
                    </button>
                    <div className="admin-btn-group">
                      <StatusBadge status={inc.status} />
                      <button
                        type="button"
                        className="admin-btn admin-btn--sm"
                        style={expandedId === inc.id ? { background: '#eef2ff', color: '#4338ca', borderColor: '#c7d2fe' } : {}}
                        onClick={() => toggleExpand(inc)}
                      >
                        {expandedId === inc.id ? 'Close' : 'Open →'}
                      </button>
                    </div>
                  </div>

                  {expandedId === inc.id ? (
                    <div style={{ marginTop: 12, width: '100%' }}>
                      {detailLoading ? (
                        <p className="admin-queue__meta">Loading thread…</p>
                      ) : detail ? (
                        <IncidentDetailPanel
                          incident={detail}
                          onUpdated={onDetailUpdated}
                          apiBase="/api/v1/incidents"
                          canManage
                        />
                      ) : null}
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </div>
      </AdminPanel>
    </div>
  )
}
