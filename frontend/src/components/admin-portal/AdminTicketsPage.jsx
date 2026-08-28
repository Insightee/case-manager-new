import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { createStaffTicket } from '../../lib/ticketFormUtils.js'
import { formatTimestampDateIN } from '../../lib/datetime.js'
import { useDebouncedValue } from '../../hooks/useDebouncedValue.js'
import { PoliciesBotButton } from '../support/PoliciesBotButton.jsx'
import { TicketFileInput } from '../support/TicketFileInput.jsx'
import { TicketDetailPanel, loadStaffTicketDetail } from '../support/TicketDetailPanel.jsx'
import { CaseCombobox } from '../shared/CaseCombobox.jsx'
import '../support/support-tickets.css'
import { CANONICAL_STATUS_OPTIONS, canonicalLabel, rowCanonicalStatus } from '../../lib/supportStatus.js'
import {
  AdminCollapsibleFilters,
  AdminPageHeader,
  AdminPanel,
  AdminEmptyState,
  AdminToolbar,
  AdminSearchInput,
  StatusBadge,
  ServiceFilterSelect,
  PeopleListPagination,
} from './ui/index.js'

const PAGE_SIZE = 25

const TICKET_STATUS_FILTERS = [
  { value: 'ALL', label: 'All statuses' },
  ...CANONICAL_STATUS_OPTIONS.filter((o) => o.value),
]

export function AdminTicketsPage({ embedded = false }) {
  const [searchParams] = useSearchParams()
  const deepLinkTicketId = searchParams.get('ticket')
  const handledDeepLink = useRef(null)
  const [tickets, setTickets] = useState([])
  const [listMeta, setListMeta] = useState({ total: 0, pages: 1 })
  const [openCount, setOpenCount] = useState(0)
  const [page, setPage] = useState(1)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [createForm, setCreateForm] = useState({ subject: '', body: '', category: 'OTHER', case_id: '' })
  const [createFiles, setCreateFiles] = useState([])
  const [createBusy, setCreateBusy] = useState(false)
  const [createError, setCreateError] = useState('')
  const [createSuccess, setCreateSuccess] = useState('')
  const [search, setSearch] = useState('')
  const searchDebounced = useDebouncedValue(search)
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [moduleFilter, setModuleFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState(null)
  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)

  useEffect(() => {
    setPage(1)
  }, [searchDebounced, statusFilter, moduleFilter])

  const loadOpenCount = useCallback(async () => {
    try {
      const qs = new URLSearchParams({ canonical_status: 'open', page_size: '1' })
      if (moduleFilter) qs.set('product_module', moduleFilter)
      const data = await apiFetch(`/api/v1/tickets?${qs.toString()}`)
      setOpenCount(data.total ?? 0)
    } catch {
      setOpenCount(0)
    }
  }, [moduleFilter])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const qs = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) })
      if (moduleFilter) qs.set('product_module', moduleFilter)
      if (statusFilter !== 'ALL') qs.set('canonical_status', statusFilter)
      if (searchDebounced.trim()) qs.set('search', searchDebounced.trim())
      const data = await apiFetch(`/api/v1/tickets?${qs.toString()}`)
      setTickets(data.items || [])
      setListMeta({ total: data.total ?? 0, pages: data.pages ?? 1 })
    } catch {
      setTickets([])
      setListMeta({ total: 0, pages: 1 })
    } finally {
      setLoading(false)
    }
  }, [page, moduleFilter, statusFilter, searchDebounced])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    loadOpenCount()
  }, [loadOpenCount])

  async function openTicket(t) {
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

  const toggleExpand = openTicket

  useEffect(() => {
    if (!deepLinkTicketId || loading) return
    const id = Number(deepLinkTicketId)
    if (!Number.isFinite(id) || handledDeepLink.current === id) return

    const ticket = tickets.find((t) => t.id === id)
    if (ticket) {
      handledDeepLink.current = id
      openTicket(ticket)
      return
    }

    handledDeepLink.current = id
    setExpandedId(id)
    setDetailLoading(true)
    loadStaffTicketDetail(id)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setDetailLoading(false))
  }, [deepLinkTicketId, loading, tickets])

  async function onDetailUpdated(updated) {
    setDetail(updated)
    await load()
    await loadOpenCount()
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
      setPage(1)
      await load()
      await loadOpenCount()
    } catch (err) {
      setCreateError(err.message || 'Could not create ticket')
    } finally {
      setCreateBusy(false)
    }
  }

  const rangeStart = listMeta.total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1
  const rangeEnd = Math.min(page * PAGE_SIZE, listMeta.total)

  const filterControls = (
    <>
      <AdminSearchInput
        value={search}
        onChange={setSearch}
        placeholder="Search therapist, client, subject, or ID…"
      />
      <select
        className="admin-search__input"
        style={{ flex: '0 0 auto', width: 'auto', minWidth: 140, paddingLeft: 12, backgroundImage: 'none' }}
        value={statusFilter}
        onChange={(e) => setStatusFilter(e.target.value)}
        aria-label="Ticket status"
      >
        {TICKET_STATUS_FILTERS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
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
        title={`${listMeta.total} tickets`}
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
              <AdminSearchInput
                value={search}
                onChange={setSearch}
                placeholder="Search therapist, client, subject, or ID…"
              />
            }
            activeChips={[
              statusFilter !== 'ALL' ? canonicalLabel(statusFilter) : null,
              moduleFilter || null,
              searchDebounced.trim() ? `Search: ${searchDebounced.trim()}` : null,
            ].filter(Boolean)}
            activeCount={[statusFilter !== 'ALL', moduleFilter, searchDebounced.trim()].filter(Boolean).length}
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
                    <option value="TECH">TECH</option>
                    <option value="SERVICE">SERVICE</option>
                    <option value="POSH">POSH</option>
                    <option value="CPP">CPP</option>
                    <option value="OTHER">OTHER</option>
                  </select>
                </label>
                <label>
                  Case (optional)
                  <CaseCombobox
                    value={createForm.case_id}
                    onChange={(caseId) => setCreateForm((f) => ({ ...f, case_id: caseId }))}
                    disabled={createBusy}
                    noneLabel="Not linked to a case"
                    placeholder="Search client, therapist, or case code…"
                  />
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
          ) : tickets.length === 0 ? (
            <AdminEmptyState
              title="No tickets"
              description="No support tickets match this filter. Tickets raised from the therapist or client portals appear here — try All statuses, or create a test ticket as therapist@demo.com."
            />
          ) : (
            <>
              <ul className="admin-queue">
                {tickets.map((t) => (
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
                          {t.created_at ? ` · ${formatTimestampDateIN(t.created_at)}` : ''}
                          {t.raised_by_name
                            ? ` · ${t.raised_by_name}${t.raised_by_portal ? ` (${t.raised_by_portal})` : ''}`
                            : ''}
                          {t.assigned_to_name ? ` → ${t.assigned_to_name}` : ' · Unassigned'}
                          {t.case_code
                            ? ` · ${t.case_code}${t.child_name ? ` (${t.child_name})` : ''}`
                            : ''}
                          {t.therapist_name ? ` · ${t.therapist_name}` : ''}
                          {t.product_module ? ` · ${t.product_module}` : ''}
                          {t.attachment_count > 0 ? ` · ${t.attachment_count} attachment(s)` : ''}
                        </p>
                      </button>
                      <StatusBadge status={rowCanonicalStatus({ ...t, record_type: 'ticket' })} />
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
              <PeopleListPagination
                page={page}
                totalPages={listMeta.pages}
                total={listMeta.total}
                rangeStart={rangeStart}
                rangeEnd={rangeEnd}
                onPageChange={setPage}
              />
            </>
          )}
        </div>
      </AdminPanel>
    </div>
  )
}
