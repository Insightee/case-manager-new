import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { useApiQuery } from '../../hooks/useApiQuery.js'
import { useAuth } from '../../context/AuthContext.jsx'
import {
  AdminPageHeader,
  AdminPanel,
  AdminEmptyState,
  AdminToolbar,
  AdminSearchInput,
  StatusBadge,
} from './ui/index.js'
import { CaseBillingForm } from './CaseBillingForm.jsx'
import { AdminCaseAllotmentWizard } from './AdminCaseAllotmentWizard.jsx'
import { AdminScheduleSessionModal } from './AdminScheduleSessionModal.jsx'
import { CaseServiceAddressForm } from './CaseServiceAddressForm.jsx'
import { AdminTherapistPicker } from './AdminTherapistPicker.jsx'
import { AdminCasesKanban } from './AdminCasesKanban.jsx'
import { billingSummary } from '../invoices/invoiceUtils.js'

export function AdminCasesPage() {
  const [searchParams] = useSearchParams()
  const { can } = useAuth()
  const [cases, setCases] = useState([])
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [viewMode, setViewMode] = useState('board')
  const [moduleFilter, setModuleFilter] = useState('all')
  const [selected, setSelected] = useState(null)
  const [assignments, setAssignments] = useState([])
  const [therapistId, setTherapistId] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [scheduleCase, setScheduleCase] = useState(null)
  const [assignError, setAssignError] = useState('')
  const [cmUsers, setCmUsers] = useState([])
  const [caseManagerId, setCaseManagerId] = useState('')
  const [cmSaving, setCmSaving] = useState(false)
  const [cmError, setCmError] = useState('')

  const { data: casesData, isLoading: loading, refetch: refetchCases } = useApiQuery(
    ['admin', 'cases'],
    '/api/v1/cases?page_size=100',
  )

  useEffect(() => {
    if (casesData) setCases(unwrapList(casesData))
  }, [casesData])

  useEffect(() => {
    if (searchParams.get('allot') === '1' && can('case.create')) {
      setShowCreate(true)
    }
    const status = searchParams.get('status')
    if (status) setStatusFilter(status)
  }, [searchParams, can])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return cases.filter((c) => {
      if (statusFilter !== 'ALL' && c.status !== statusFilter) return false
      if (!q) return true
      return (
        c.case_code?.toLowerCase().includes(q) ||
        c.child_name?.toLowerCase().includes(q) ||
        c.service_type?.toLowerCase().includes(q)
      )
    })
  }, [cases, search, statusFilter])

  const statusCounts = useMemo(() => {
    const counts = {}
    for (const c of cases) counts[c.status] = (counts[c.status] || 0) + 1
    return counts
  }, [cases])

  async function loadAssignments(caseId) {
    const rows = await apiFetch(`/api/v1/cases/${caseId}/assignments`)
    setAssignments(rows)
  }

  async function handleAssign(caseId) {
    if (!therapistId) return
    setAssignError('')
    try {
      await apiFetch(`/api/v1/cases/${caseId}/assignments`, {
        method: 'POST',
        body: JSON.stringify({
          therapist_user_id: Number(therapistId),
          start_date: new Date().toISOString().slice(0, 10),
          reason_for_change: 'Admin reassignment',
        }),
      })
      await loadAssignments(caseId)
      refetchCases()
      setTherapistId('')
    } catch (err) {
      setAssignError(err.message || 'Assignment failed')
    }
  }

  async function updateStatus(caseItem, status) {
    await apiFetch(`/api/v1/cases/${caseItem.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    })
    refetchCases()
  }

  useEffect(() => {
    if (!can('case.update')) return
    apiFetch('/api/v1/admin/users')
      .then((rows) => {
        const list = Array.isArray(rows) ? rows : rows?.items || []
        setCmUsers(list.filter((u) => u.roles?.includes('CASE_MANAGER')))
      })
      .catch(() => setCmUsers([]))
  }, [can])

  function openCase(c) {
    setSelected(c)
    setCaseManagerId(c.case_manager_user_id ? String(c.case_manager_user_id) : '')
    setCmError('')
    loadAssignments(c.id)
  }

  async function saveCaseManager(caseId) {
    setCmSaving(true)
    setCmError('')
    try {
      const updated = await apiFetch(`/api/v1/cases/${caseId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          case_manager_user_id: caseManagerId ? Number(caseManagerId) : null,
        }),
      })
      setSelected(updated)
      refetchCases()
    } catch (err) {
      setCmError(err.message || 'Could not update case manager')
    } finally {
      setCmSaving(false)
    }
  }

  async function saveBilling(payload) {
    if (!selected) return
    const updated = await apiFetch(`/api/v1/cases/${selected.id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
    setSelected(updated)
    refetchCases()
  }

  async function saveServiceAddress(payload) {
    if (!selected) return
    const updated = await apiFetch(`/api/v1/cases/${selected.id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
    setSelected(updated)
    refetchCases()
  }

  async function createCase(payload) {
    const created = await apiFetch('/api/v1/cases', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
    refetchCases()
    setShowCreate(false)
    openCase(created)
  }

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="Case management"
        title="Cases"
        subtitle="Pipeline board for allotment, reassignment, reports, IEP, and compliance — or use the list view."
        actions={
          can('case.create') ? (
            <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={() => setShowCreate((v) => !v)}>
              {showCreate ? 'Close form' : '+ New case'}
            </button>
          ) : null
        }
      />

      {showCreate && can('case.create') ? (
        <AdminCaseAllotmentWizard
          onComplete={async (created) => {
            setShowCreate(false)
            const rows = unwrapList(await apiFetch('/api/v1/cases?page_size=100'))
            setCases(rows)
            if (created) openCase(created)
          }}
          onCancel={() => setShowCreate(false)}
        />
      ) : null}

      <div className="admin-btn-group" style={{ marginBottom: 12 }}>
        <button
          type="button"
          className={`admin-btn admin-btn--sm ${viewMode === 'board' ? 'admin-btn--primary' : 'admin-btn--ghost'}`}
          onClick={() => setViewMode('board')}
        >
          Pipeline board
        </button>
        <button
          type="button"
          className={`admin-btn admin-btn--sm ${viewMode === 'list' ? 'admin-btn--primary' : 'admin-btn--ghost'}`}
          onClick={() => setViewMode('list')}
        >
          List
        </button>
        {viewMode === 'board' ? (
          <select
            className="admin-input admin-btn--sm"
            style={{ width: 'auto', marginLeft: 8 }}
            value={moduleFilter}
            onChange={(e) => setModuleFilter(e.target.value)}
          >
            <option value="all">All modules</option>
            <option value="homecare">Homecare</option>
            <option value="shadow_support">Shadow support</option>
          </select>
        ) : null}
      </div>

      {viewMode === 'board' ? (
        <AdminPanel title="Case pipeline" padded={false}>
          <div className="admin-panel__body" style={{ padding: '12px 16px 16px' }}>
            <AdminCasesKanban productFilter={moduleFilter} />
          </div>
        </AdminPanel>
      ) : null}

      {viewMode === 'list' ? (
        <>
      <section className="admin-kpi-grid" aria-label="Case counts">
        {['ACTIVE', 'PENDING_ALLOTMENT', 'SUSPENDED', 'CLOSED'].map((s) => (
          <button
            key={s}
            type="button"
            className={`admin-stat admin-stat--link admin-stat--slate ${statusFilter === s ? 'is-active' : ''}`}
            style={statusFilter === s ? { borderColor: '#a5b4fc', boxShadow: '0 0 0 2px rgba(99,102,241,0.2)' } : undefined}
            onClick={() => setStatusFilter(statusFilter === s ? 'ALL' : s)}
          >
            <p className="admin-stat__label">{s.replaceAll('_', ' ')}</p>
            <p className="admin-stat__value">{statusCounts[s] ?? 0}</p>
          </button>
        ))}
      </section>

      <AdminPanel title={`${filtered.length} case${filtered.length === 1 ? '' : 's'}`} padded={false}>
        <div className="admin-panel__body">
          <AdminToolbar>
            <AdminSearchInput
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by code, child, or service…"
            />
            <select
              className="admin-search__input"
              style={{ flex: '0 0 auto', width: 'auto', minWidth: 160, paddingLeft: 12, backgroundImage: 'none' }}
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="ALL">All statuses</option>
              <option value="ACTIVE">Active</option>
              <option value="PENDING_ALLOTMENT">Pending allotment</option>
              <option value="SUSPENDED">Suspended</option>
              <option value="CLOSED">Closed</option>
            </select>
          </AdminToolbar>

          {loading ? (
            <div className="admin-skeleton" style={{ margin: '0 18px 16px' }} />
          ) : filtered.length === 0 ? (
            <AdminEmptyState title="No cases match" description="Try a different search or filter." />
          ) : (
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Case</th>
                    <th>Child</th>
                    <th>Service</th>
                    <th>Module</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((c) => (
                    <tr key={c.id}>
                      <td>
                        <span className="admin-table__primary">{c.case_code}</span>
                        <span className="admin-table__meta">ID {c.id}</span>
                      </td>
                      <td>{c.child_name ?? '—'}</td>
                      <td>{c.service_type}</td>
                      <td>
                        <span className="admin-chip">{c.product_module}</span>
                      </td>
                      <td>
                        <StatusBadge status={c.status} />
                      </td>
                      <td>
                        <div className="admin-btn-group">
                          <Link to={`/admin/cases/${c.id}`} className="admin-btn admin-btn--primary admin-btn--sm">Open</Link>
                          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => openCase(c)}>
                            History
                          </button>
                          {can('case.update') ? (
                            <>
                              <button
                                type="button"
                                className="admin-btn admin-btn--secondary admin-btn--sm"
                                onClick={() => updateStatus(c, 'SUSPENDED')}
                              >
                                Suspend
                              </button>
                              <button
                                type="button"
                                className="admin-btn admin-btn--danger admin-btn--sm"
                                onClick={() => updateStatus(c, 'CLOSED')}
                              >
                                Close
                              </button>
                            </>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </AdminPanel>
        </>
      ) : null}

      {selected ? (
        <div className="admin-drawer">
          <h3 className="admin-drawer__title">Case — {selected.case_code}</h3>
          {can('case.update') ? (
            <CaseBillingForm caseItem={selected} onSave={saveBilling} />
          ) : (
            <CaseBillingForm caseItem={selected} readOnly />
          )}
          <CaseServiceAddressForm
            caseItem={selected}
            onSave={can('case.update') ? saveServiceAddress : undefined}
            readOnly={!can('case.update')}
          />
          {can('case.update') ? (
            <div className="admin-form-grid" style={{ maxWidth: 420, marginBottom: 16 }}>
              <label>
                Case manager
                <select
                  className="admin-input"
                  value={caseManagerId}
                  onChange={(e) => setCaseManagerId(e.target.value)}
                >
                  <option value="">Not assigned</option>
                  {cmUsers.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.full_name || u.email}
                    </option>
                  ))}
                </select>
              </label>
              <p style={{ fontSize: '0.75rem', color: '#64748b', margin: 0 }}>
                Shown to parents on their dashboard and case hub. Therapists are assigned separately below.
              </p>
              {cmError ? <p style={{ color: '#b91c1c', fontSize: '0.875rem' }}>{cmError}</p> : null}
              <button
                type="button"
                className="admin-btn admin-btn--secondary admin-btn--sm"
                disabled={cmSaving}
                onClick={() => saveCaseManager(selected.id)}
              >
                {cmSaving ? 'Saving…' : 'Save case manager'}
              </button>
            </div>
          ) : selected.case_manager_user_id ? (
            <p style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: 16 }}>
              Case manager ID: {selected.case_manager_user_id}
            </p>
          ) : null}
          <h4 className="admin-drawer__subtitle" style={{ marginTop: 8 }}>
            Assignment history
          </h4>
          {assignments[0]?.case_billing ? (
            <p style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: 12 }}>
              Inherited billing: {billingSummary(assignments[0].case_billing)}
            </p>
          ) : null}
          {can('slot.book_any') ? (
            <button
              type="button"
              className="admin-btn admin-btn--primary admin-btn--sm"
              style={{ marginBottom: 12 }}
              onClick={() => setScheduleCase(selected)}
            >
              Schedule session
            </button>
          ) : null}
          {can('case.assign') ? (
            <div className="admin-form-grid" style={{ maxWidth: 420, marginBottom: 16 }}>
              <label>
                Therapist
                <AdminTherapistPicker
                  mode="allotment"
                  productModule={selected.product_module}
                  caseId={selected.id}
                  value={therapistId}
                  onChange={setTherapistId}
                />
              </label>
              {assignError ? <p style={{ color: '#b91c1c', fontSize: '0.875rem' }}>{assignError}</p> : null}
              <button type="button" className="admin-btn admin-btn--primary" onClick={() => handleAssign(selected.id)}>
                Assign / Reassign
              </button>
            </div>
          ) : null}
          {assignments.length === 0 ? (
            <AdminEmptyState title="No assignments yet" description="Assign a therapist to start sessions." />
          ) : (
            <ul className="admin-queue">
              {assignments.map((a) => (
                <li key={a.id} className="admin-queue__item">
                  <div>
                    <p className="admin-queue__title">{a.therapist_name || `Therapist #${a.therapist_user_id}`}</p>
                    <p className="admin-queue__meta">
                      {a.start_date}
                      {a.end_date ? ` → ${a.end_date}` : ''}
                      {a.reason_for_change ? ` · ${a.reason_for_change}` : ''}
                    </p>
                  </div>
                  <StatusBadge status={a.status} />
                </li>
              ))}
            </ul>
          )}
          <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" style={{ marginTop: 12 }} onClick={() => setSelected(null)}>
            Close
          </button>
        </div>
      ) : null}

      <AdminScheduleSessionModal
        open={!!scheduleCase}
        caseItem={scheduleCase}
        onClose={() => setScheduleCase(null)}
        onDone={() => setScheduleCase(null)}
      />
    </div>
  )
}
