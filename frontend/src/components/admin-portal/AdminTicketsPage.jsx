import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { PoliciesBotButton } from '../support/PoliciesBotButton.jsx'
import { TicketDetailPanel, loadStaffTicketDetail } from '../support/TicketDetailPanel.jsx'
import '../support/support-tickets.css'
import { AdminPageHeader, AdminPanel, AdminEmptyState, AdminToolbar, AdminSearchInput, StatusBadge } from './ui/index.js'

export function AdminTicketsPage() {
  const [cases, setCases] = useState([])
  const [tickets, setTickets] = useState([])
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('OPEN')
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

  return (
    <div className="admin-page">
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

      <AdminPanel title={`${filtered.length} tickets`} padded={false}>
        <div className="admin-panel__body">
          <AdminToolbar>
            <AdminSearchInput value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search subject or ID…" />
            <select
              className="admin-search__input"
              style={{ flex: '0 0 auto', width: 'auto', minWidth: 140, paddingLeft: 12, backgroundImage: 'none' }}
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="ALL">All</option>
              <option value="OPEN">Open</option>
              <option value="IN_PROGRESS">In progress</option>
              <option value="RESOLVED">Resolved</option>
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
            <AdminEmptyState title="No tickets" description="Support requests will appear here." />
          ) : (
            <ul className="admin-queue">
              {filtered.map((t) => (
                <li key={t.id} className="admin-queue__item" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, width: '100%' }}>
                    <button
                      type="button"
                      onClick={() => toggleExpand(t)}
                      style={{ flex: 1, textAlign: 'left', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                    >
                      <p className="admin-queue__title">{t.subject}</p>
                      <p className="admin-queue__meta">
                        #{t.id}
                        {t.case_id && caseById[t.case_id]
                          ? ` · ${caseById[t.case_id].case_code} (${caseById[t.case_id].child_name})`
                          : ''}
                        {t.product_module ? ` · ${t.product_module}` : ''}
                        {t.attachment_count > 0 ? ` · ${t.attachment_count} attachment(s)` : ''}
                      </p>
                    </button>
                    <div className="admin-btn-group">
                      <StatusBadge status={t.status} />
                      <button
                        type="button"
                        className="admin-btn admin-btn--sm"
                        style={expandedId === t.id ? { background: '#eef2ff', color: '#4338ca', borderColor: '#c7d2fe' } : {}}
                        onClick={() => toggleExpand(t)}
                      >
                        {expandedId === t.id ? 'Close' : 'Open →'}
                      </button>
                    </div>
                  </div>
                  {expandedId === t.id ? (
                    <div style={{ marginTop: 12, width: '100%' }}>
                      {detailLoading ? (
                        <p className="admin-queue__meta">Loading…</p>
                      ) : detail ? (
                        <TicketDetailPanel
                          ticket={detail}
                          showResolve={detail.status !== 'RESOLVED' && detail.status !== 'CLOSED'}
                          onUpdated={onDetailUpdated}
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
