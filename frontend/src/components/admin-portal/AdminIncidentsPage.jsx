import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch, apiUpload } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { IncidentReportForm } from '../support/IncidentReportForm.jsx'
import { IncidentDetailPanel } from '../support/IncidentDetailPanel.jsx'
import {
  AdminCollapsibleFilters,
  AdminPageHeader,
  AdminPanel,
  AdminEmptyState,
  AdminToolbar,
  AdminSearchInput,
  StatusBadge,
  ServiceFilterSelect,
} from './ui/index.js'
import '../support/support-tickets.css'

const STATUS_FILTERS = ['ALL', 'REPORTED', 'IN_REVIEW', 'ACTION_TAKEN', 'ESCALATED', 'CLOSED']

export function AdminIncidentsPage({ embedded = false }) {
  const [searchParams] = useSearchParams()
  const deepLinkIncidentId = searchParams.get('incident')
  const handledDeepLink = useRef(null)
  const [cases, setCases] = useState([])
  const [incidents, setIncidents] = useState([])
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [createBusy, setCreateBusy] = useState(false)
  const [createError, setCreateError] = useState('')
  const [createSuccess, setCreateSuccess] = useState('')
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
    apiFetch('/api/v1/cases?page_size=100')
      .then((d) => setCases(unwrapList(d)))
      .catch(() => setCases([]))
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

  async function openIncident(inc) {
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

  const toggleExpand = openIncident

  useEffect(() => {
    if (!deepLinkIncidentId || loading) return
    const id = Number(deepLinkIncidentId)
    if (!Number.isFinite(id) || handledDeepLink.current === id) return
    const inc = incidents.find((i) => i.id === id)
    if (!inc) return
    handledDeepLink.current = id
    openIncident(inc)
  }, [deepLinkIncidentId, loading, incidents])

  function onDetailUpdated(updated) {
    setDetail(updated)
    load()
  }

  async function submitIncident(payload) {
    setCreateBusy(true)
    setCreateError('')
    setCreateSuccess('')
    try {
      const { files, attachment_note, ...body } = payload
      const created = await apiFetch('/api/v1/incidents', {
        method: 'POST',
        body: JSON.stringify(body),
      })
      if (files?.length) {
        const fd = new FormData()
        files.forEach((f) => fd.append('files', f))
        if (attachment_note) fd.append('note', attachment_note)
        await apiUpload(`/api/v1/incidents/${created.id}/attachments`, fd)
      }
      setShowCreateForm(false)
      setCreateSuccess(created.confirmation || 'Incident created successfully.')
      await load()
    } catch (err) {
      setCreateError(err.message || 'Could not create incident')
    } finally {
      setCreateBusy(false)
    }
  }

  const filterControls = (
    <>
      <AdminSearchInput value={search} onChange={setSearch} placeholder="Search title, reporter…" />
      <select
        className="admin-search__input"
        style={{ flex: '0 0 auto', width: 'auto', minWidth: 140, paddingLeft: 12, backgroundImage: 'none' }}
        value={statusFilter}
        onChange={(e) => setStatusFilter(e.target.value)}
        aria-label="Incident status"
      >
        {STATUS_FILTERS.map((s) => (
          <option key={s} value={s}>
            {s === 'ALL' ? 'All statuses' : s}
          </option>
        ))}
      </select>
      <ServiceFilterSelect
        className="admin-search__input"
        style={{ flex: '0 0 auto', minWidth: 150, paddingLeft: 12, backgroundImage: 'none' }}
        value={moduleFilter}
        onChange={setModuleFilter}
        extraOptions={[{ value: 'billing', label: 'Billing' }]}
      />
    </>
  )

  return (
    <div className={embedded ? 'admin-hub-embedded' : 'admin-page'}>
      {!embedded ? (
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
      ) : null}

      <AdminPanel
        title={`${filtered.length} incidents`}
        padded={false}
        actions={
          embedded ? (
            <span
              className="admin-chip"
              style={{
                background: openCount ? '#fef3c7' : '#d1fae5',
                color: openCount ? '#b45309' : '#047857',
              }}
            >
              {openCount} active
            </span>
          ) : null
        }
      >
        <div className="admin-panel__body">
          <AdminCollapsibleFilters
            quickSearch={
              <AdminSearchInput value={search} onChange={setSearch} placeholder="Search title, reporter…" />
            }
            activeChips={[statusFilter !== 'ALL' ? statusFilter : null, moduleFilter || null].filter(Boolean)}
            activeCount={[statusFilter !== 'ALL', moduleFilter].filter(Boolean).length}
          >
            <AdminToolbar className="admin-toolbar--mobile-compact admin-collapsible-filters__grid">
              {filterControls}
            </AdminToolbar>
          </AdminCollapsibleFilters>
          <div style={{ marginBottom: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button
                type="button"
                className={`admin-btn admin-btn--sm ${showCreateForm ? 'admin-btn--ghost' : 'admin-btn--primary'}`}
                onClick={() => {
                  setShowCreateForm((v) => !v)
                  setCreateError('')
                  setCreateSuccess('')
                }}
              >
                {showCreateForm ? 'Cancel' : '+ New incident'}
              </button>
            </div>
            {showCreateForm ? (
              <div style={{ marginTop: 10 }}>
                <IncidentReportForm
                  cases={cases}
                  onSubmit={submitIncident}
                  submitting={createBusy}
                  error={createError}
                />
              </div>
            ) : null}
            {createSuccess ? <p className="admin-alert admin-alert--success">{createSuccess}</p> : null}
          </div>

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
                      aria-expanded={expandedId === inc.id}
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
                              to={`/admin/cases/${inc.case_id}?tab=incidents`}
                              onClick={(e) => e.stopPropagation()}
                              style={{ color: '#6366f1' }}
                            >
                              View case
                            </Link>
                            {' '}·{' '}
                            <Link
                              to={`/admin/support?tab=incidents&incident=${inc.id}`}
                              onClick={(e) => e.stopPropagation()}
                              style={{ color: '#6366f1' }}
                            >
                              View report
                            </Link>
                          </>
                        ) : (
                          <>
                            {' '}·{' '}
                            <Link
                              to={`/admin/support?tab=incidents&incident=${inc.id}`}
                              onClick={(e) => e.stopPropagation()}
                              style={{ color: '#6366f1' }}
                            >
                              View report
                            </Link>
                          </>
                        )}
                      </p>
                    </button>
                    <StatusBadge status={inc.status} />
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
