import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { AdminPageHeader, AdminPanel, AdminEmptyState, AdminToolbar, AdminSearchInput, StatusBadge } from './ui/index.js'

export function AdminTicketsPage() {
  const [cases, setCases] = useState([])
  const [tickets, setTickets] = useState([])
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('OPEN')
  const [loading, setLoading] = useState(true)

  async function load() {
    setLoading(true)
    try {
      setTickets(await apiFetch('/api/v1/tickets'))
    } catch {
      setTickets([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    apiFetch('/api/v1/cases')
      .then(setCases)
      .catch(() => setCases([]))
  }, [])

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

  async function resolve(id) {
    await apiFetch(`/api/v1/tickets/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ status: 'RESOLVED' }),
    })
    load()
  }

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="Support"
        title="Support tickets"
        subtitle="Therapist tickets route to case managers; admins see all statuses."
        actions={
          <span className="admin-chip" style={{ background: openCount ? '#fef3c7' : '#d1fae5', color: openCount ? '#b45309' : '#047857' }}>
            {openCount} open
          </span>
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
          </AdminToolbar>

          {loading ? (
            <div className="admin-skeleton" />
          ) : filtered.length === 0 ? (
            <AdminEmptyState title="No tickets" description="Support requests will appear here." />
          ) : (
            <ul className="admin-queue">
              {filtered.map((t) => (
                <li key={t.id} className="admin-queue__item">
                  <div>
                    <p className="admin-queue__title">{t.subject}</p>
                    <p className="admin-queue__meta">
                      #{t.id}
                      {t.case_id && caseById[t.case_id]
                        ? ` · ${caseById[t.case_id].case_code} (${caseById[t.case_id].child_name})`
                        : ''}
                      {t.product_module ? ` · ${t.product_module}` : ''}
                    </p>
                  </div>
                  <div className="admin-btn-group">
                    <StatusBadge status={t.status} />
                    {t.status !== 'RESOLVED' && t.status !== 'CLOSED' ? (
                      <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={() => resolve(t.id)}>
                        Resolve
                      </button>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </AdminPanel>
    </div>
  )
}
