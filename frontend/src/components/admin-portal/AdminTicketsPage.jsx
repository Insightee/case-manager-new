import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { createStaffTicket } from '../../lib/ticketFormUtils.js'
import { PoliciesBotButton } from '../support/PoliciesBotButton.jsx'
import { TicketFileInput } from '../support/TicketFileInput.jsx'
import { TicketDetailPanel, loadStaffTicketDetail } from '../support/TicketDetailPanel.jsx'
import '../support/support-tickets.css'
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

export function AdminTicketsPage({ embedded = false }) {
  const [cases, setCases] = useState([])
  const [tickets, setTickets] = useState([])
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [createForm, setCreateForm] = useState({ subject: '', body: '', category: 'OTHER', case_id: '' })
  const [createFiles, setCreateFiles] = useState([])
  const [createBusy, setCreateBusy] = useState(false)
  const [createError, setCreateError] = useState('')
  const [createSuccess, setCreateSuccess] = useState('')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
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
      setTickets(unwrapList(await apiFetch(`/api/v1/tickets?${qs.toString()}`)))
    } catch {
      setTickets([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    apiFetch('/api/v1/cases?page_size=100')
      .then((d) => setCases(unwrapList(d)))
      .catch(() => setCases([]))
  }, [moduleFilter])

  const caseById = useMemo(() => {
    const map = {}
    for (const c of cases) map[c.id] = c
    return map
  }, [cases])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return tickets.filter((t) => {
      if (statusFilter !== 'ALL' && t.status !== statusFilter) return false
      if (!q) return true
      return t.subject?.toLowerCase().includes(q) || String(t.id).includes(q)
    })
  }, [tickets, search, statusFilter])

  const openCount = tickets.filter((t) => t.status === 'OPEN').length

  async function toggleExpand(t) {
    if (expandedId === t.id) {
      setExpandedId(null)
      setDetail(null)
      return
    }
    setExpandedId(t.id)
    setDetailLoading(true)
    try {
      setDetail(await loadStaffTicketDetail(t.id))
    } catch {
      setDetail(null)
    } finally {
      setDetailLoading(false)
    }
  }

  async function onDetailUpdated(updated) {
    setDetail(updated)
    load()
  }

  async function submitCreateTicket(e) {
    e.preventDefault()
    setCreateBusy(true)
    setCreateError('')
    setCreateSuccess('')
    try {
      await createStaffTicket({
        subject: createForm.subject,
        body: createForm.body,
        category: createForm.category,
        case_id: createForm.case_id ? Number(createForm.case_id) : undefined,
        files: createFiles,
      })
      setCreateForm({ subject: '', body: '', category: 'OTHER', case_id: '' })
      setCreateFiles([])
      setShowCreateForm(false)
      setCreateSuccess('Ticket created successfully.')
      await load()
    } catch (err) {
      setCreateError(err.message || 'Could not create ticket')
    } finally {
      setCreateBusy(false)
    }
  }

  const filterControls = (
    <>
      <AdminSearchInput value={search} onChange={setSearch} placeholder="Search subject or ID…" />
      <select
        className="admin-search__input"
        style={{ flex: '0 0 auto', width: 'auto', minWidth: 140, paddingLeft: 12, backgroundImage: 'none' }}
        value={statusFilter}
        onChange={(e) => setStatusFilter(e.target.value)}
        aria-label="Ticket status"
      >
        <option value="ALL">All</option>
        <option value="OPEN">Open</option>
        <option value="IN_PROGRESS">In progress</option>
        <option value="RESOLVED">Resolved</option>
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
          eyebrow="Support"
          title="Support tickets"
          subtitle="Therapist tickets route to case managers; admins see all statuses."
          actions={
            <>
              <PoliciesBotButton />
              <span className="admin-chip" style={{ background: openCount ? '#fef3c7' : '#d1fae5', color: openCount ? '#b45309' : '#047857' }}>
                {openCount} open
              </span>
            </>
          }
        />
      ) : null}

      <AdminPanel
        title={`${filtered.length} tickets`}
        padded={false}
        actions={
          embedded ? (
            <span className="admin-chip" style={{ background: openCount ? '#fef3c7' : '#d1fae5', color: openCount ? '#b45309' : '#047857' }}>
              {openCount} open
            </span>
          ) : null
        }
      >
        <div className="admin-panel__body">
          <AdminCollapsibleFilters
            quickSearch={
              <AdminSearchInput value={search} onChange={setSearch} placeholder="Search subject or ID…" />
            }
            activeChips={[
              statusFilter !== 'ALL' ? statusFilter.replace('_', ' ') : null,
              moduleFilter || null,
            ].filter(Boolean)}
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
                {showCreateForm ? 'Cancel' : '+ New ticket'}
              </button>
            </div>
            {showCreateForm ? (
              <form onSubmit={submitCreateTicket} className="admin-form-grid" style={{ marginTop: 10 }}>
                <label>
                  Category
                  <select
                    className="admin-input"
                    value={createForm.category}
                    onChange={(e) => setCreateForm((f) => ({ ...f, category: e.target.value }))}
                  >
                    <option value="FINANCE">FINANCE</option>
                    <option value="HR">HR</option>
                    <option value="SERVICE">SERVICE</option>
                    <option value="POSH">POSH</option>
                    <option value="CPP">CPP</option>
                    <option value="OTHER">OTHER</option>
                  </select>
                </label>
                <label>
                  Case (optional)
                  <select
                    className="admin-input"
                    value={createForm.case_id}
                    onChange={(e) => setCreateForm((f) => ({ ...f, case_id: e.target.value }))}
                  >
                    <option value="">Not linked to a case</option>
                    {cases.map((c) => (
                      <option key={c.id} value={c.id}>
                        {[c.case_code, c.child_name].filter(Boolean).join(' · ')}
                      </option>
                    ))}
                  </select>
                </label>
                <label style={{ gridColumn: '1 / -1' }}>
                  Subject
                  <input
                    className="admin-input"
                    value={createForm.subject}
                    onChange={(e) => setCreateForm((f) => ({ ...f, subject: e.target.value }))}
                    required
                  />
                </label>
                <label style={{ gridColumn: '1 / -1' }}>
                  Details
                  <textarea
                    className="admin-input"
                    rows={4}
                    value={createForm.body}
                    onChange={(e) => setCreateForm((f) => ({ ...f, body: e.target.value }))}
                    required
                  />
                </label>
                <div style={{ gridColumn: '1 / -1' }}>
                  <TicketFileInput files={createFiles} onChange={setCreateFiles} disabled={createBusy} />
                </div>
                <div style={{ gridColumn: '1 / -1', display: 'flex', justifyContent: 'flex-end' }}>
                  <button type="submit" className="admin-btn admin-btn--primary admin-btn--sm" disabled={createBusy}>
                    {createBusy ? 'Submitting…' : 'Create ticket'}
                  </button>
                </div>
              </form>
            ) : null}
            {createError ? <p className="admin-alert admin-alert--error">{createError}</p> : null}
            {createSuccess ? <p className="admin-alert admin-alert--success">{createSuccess}</p> : null}
          </div>

          {loading ? (
            <div className="admin-skeleton" />
          ) : filtered.length === 0 ? (
            <AdminEmptyState
              title="No tickets"
              description="No support tickets match this filter. Tickets raised from the therapist or client portals appear here — try All statuses, or create a test ticket as therapist@demo.com."
            />
          ) : (
            <ul className="admin-queue">
              {filtered.map((t) => (
                <li key={t.id} className="admin-queue__item" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, width: '100%' }}>
                    <button
                      type="button"
                      aria-expanded={expandedId === t.id}
                      onClick={() => toggleExpand(t)}
                      style={{ flex: 1, textAlign: 'left', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                    >
                      <p className="admin-queue__title">{t.subject}</p>
                      <p className="admin-queue__meta">
                        #{t.id}
                        {t.raised_by_name
                          ? ` · ${t.raised_by_name}${t.raised_by_portal ? ` (${t.raised_by_portal})` : ''}`
                          : ''}
                        {t.assigned_to_name ? ` → ${t.assigned_to_name}` : ' · Unassigned'}
                        {t.case_id && caseById[t.case_id]
                          ? ` · ${caseById[t.case_id].case_code} (${caseById[t.case_id].child_name})`
                          : ''}
                        {t.product_module ? ` · ${t.product_module}` : ''}
                        {t.attachment_count > 0 ? ` · ${t.attachment_count} attachment(s)` : ''}
                      </p>
                    </button>
                    <StatusBadge status={t.status} />
                  </div>
                  {expandedId === t.id ? (
                    <div style={{ marginTop: 12, width: '100%' }}>
                      {detailLoading ? (
                        <p className="admin-queue__meta">Loading…</p>
                      ) : detail ? (
                        <TicketDetailPanel ticket={detail} showResolve onUpdated={onDetailUpdated} />
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
