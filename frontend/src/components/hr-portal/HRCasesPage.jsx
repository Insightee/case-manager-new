import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { ErrorBanner } from '../shared/ErrorBanner.jsx'
import {
  AdminCollapsibleFilters,
  AdminDataList,
  AdminEmptyState,
  AdminPageHeader,
  AdminPanel,
  AdminSearchInput,
  AdminTaskCard,
  FilterSelect,
  StatusBadge,
} from '../admin-portal/ui/index.js'
import '../admin-portal/admin-reports.css'

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'ACTIVE', label: 'Active' },
  { value: 'PENDING_ALLOTMENT', label: 'Pending allotment' },
  { value: 'PENDING_REPLACEMENT', label: 'Pending replacement' },
  { value: 'SUSPENDED', label: 'Suspended' },
  { value: 'CLOSED', label: 'Closed' },
  { value: 'DEACTIVATED', label: 'Deactivated' },
]

const ALLOWED_NEXT = {
  PENDING_ALLOTMENT: ['ACTIVE'],
  ACTIVE: ['SUSPENDED', 'PENDING_REPLACEMENT', 'CLOSED'],
  SUSPENDED: ['ACTIVE', 'CLOSED'],
  PENDING_REPLACEMENT: ['ACTIVE', 'CLOSED'],
  DEACTIVATED: ['PENDING_ALLOTMENT'],
  CLOSED: ['PENDING_ALLOTMENT'],
}

export function HRCasesPage() {
  const { can } = useAuth()
  const canChangeStatus = can('case.status_manage')
  const canSeePay = can('case.billing.update') || can('admin.override')

  const [payload, setPayload] = useState(null)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [therapistFilter, setTherapistFilter] = useState('')
  const [pendingOnly, setPendingOnly] = useState(false)
  const [error, setError] = useState('')
  const [statusBusyId, setStatusBusyId] = useState(null)
  const [statusMsg, setStatusMsg] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await apiFetch('/api/v1/hr/caseload')
      setPayload(data)
    } catch (err) {
      setPayload(null)
      setError(err.message || 'Could not load HR caseload')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const cases = payload?.cases || []
  const therapists = payload?.therapists || []
  const summary = payload?.summary || {}
  const includePay = Boolean(payload?.include_pay && canSeePay)

  const therapistOptions = useMemo(
    () => [
      { value: '', label: 'All therapists' },
      ...therapists.map((t) => ({
        value: String(t.therapist_user_id),
        label: `${t.therapist_name || 'Therapist'} (${t.case_count})`,
      })),
    ],
    [therapists],
  )

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return cases.filter((c) => {
      if (statusFilter && c.status !== statusFilter) return false
      if (therapistFilter && String(c.therapist_user_id || '') !== therapistFilter) return false
      if (pendingOnly && !c.pending_reassignment) return false
      if (!q) return true
      return (
        c.case_code?.toLowerCase().includes(q) ||
        c.child_name?.toLowerCase().includes(q) ||
        c.therapist_name?.toLowerCase().includes(q) ||
        c.product_module?.toLowerCase().includes(q) ||
        String(c.id).includes(q)
      )
    })
  }, [cases, search, statusFilter, therapistFilter, pendingOnly])

  async function changeStatus(caseRow, newStatus) {
    if (!canChangeStatus || !newStatus) return
    const reason = window.prompt(
      `Reason for changing ${caseRow.case_code} to ${newStatus.replace(/_/g, ' ')} (min 5 characters)`,
      'HR caseload status update',
    )
    if (!reason || reason.trim().length < 5) {
      setStatusMsg('Looks like we still need a short reason (at least 5 characters) before we can update status.')
      return
    }
    setStatusBusyId(caseRow.id)
    setStatusMsg('')
    try {
      await apiFetch(`/api/v1/cases/${caseRow.id}/client-status`, {
        method: 'POST',
        body: JSON.stringify({
          new_status: newStatus,
          effective_date: new Date().toISOString().slice(0, 10),
          reason: reason.trim(),
        }),
      })
      setStatusMsg(`Updated ${caseRow.case_code} to ${newStatus.replace(/_/g, ' ')}`)
      await load()
    } catch (err) {
      setStatusMsg(err.message || 'Could not update status')
    } finally {
      setStatusBusyId(null)
    }
  }

  return (
    <div className="admin-page">
      <ErrorBanner message={error} />
      <AdminPageHeader
        eyebrow="People & HR"
        title="HR case view"
        subtitle="Therapist caseload, pending reassignment, slot fill, and remuneration for HR ops."
      />

      <div className="admin-reports__kpis" style={{ marginBottom: 16 }} role="group" aria-label="Caseload summary">
        <div className="admin-reports__kpi">
          <div className="admin-reports__kpi-value">{loading ? '…' : summary.case_count ?? 0}</div>
          <div className="admin-reports__kpi-label">Cases</div>
        </div>
        <div className="admin-reports__kpi">
          <div className="admin-reports__kpi-value">{loading ? '…' : summary.therapist_count ?? 0}</div>
          <div className="admin-reports__kpi-label">Therapists with cases</div>
        </div>
        <button
          type="button"
          className={`admin-reports__kpi${pendingOnly ? ' is-active' : ''}`}
          onClick={() => setPendingOnly((v) => !v)}
          aria-pressed={pendingOnly}
        >
          <div className="admin-reports__kpi-value">{loading ? '…' : summary.pending_reassignment ?? 0}</div>
          <div className="admin-reports__kpi-label">Pending reassignment</div>
        </button>
      </div>

      {statusMsg ? <p className="admin-muted" style={{ marginBottom: 12 }}>{statusMsg}</p> : null}

      <AdminPanel title="Therapist rollup" padded style={{ marginBottom: 16 }}>
        {loading ? (
          <p className="admin-muted">Loading…</p>
        ) : therapists.length === 0 ? (
          <p className="admin-muted">No therapists with active assignments.</p>
        ) : (
          <div className="admin-table-wrap">
            <table className="admin-table" style={{ fontSize: '0.8125rem' }}>
              <thead>
                <tr>
                  <th>Therapist</th>
                  <th>Cases</th>
                  <th>Pending reassign</th>
                  <th>Slots (14d)</th>
                  <th>Fill %</th>
                  <th>Employment</th>
                </tr>
              </thead>
              <tbody>
                {therapists.slice(0, 40).map((t) => (
                  <tr key={t.therapist_user_id}>
                    <td>
                      <button
                        type="button"
                        className="admin-btn admin-btn--ghost admin-btn--sm"
                        onClick={() => setTherapistFilter(String(t.therapist_user_id))}
                      >
                        {t.therapist_name}
                      </button>
                    </td>
                    <td>{t.case_count}</td>
                    <td>{t.pending_reassignment_count || '—'}</td>
                    <td>
                      {t.slots_booked_14d}/{t.slots_total_14d || 0}
                      {t.slots_full ? ' · full' : ''}
                    </td>
                    <td>{t.slot_fill_pct_14d != null ? `${t.slot_fill_pct_14d}%` : '—'}</td>
                    <td>{t.employment_status || (t.is_active ? 'ACTIVE' : 'INACTIVE')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </AdminPanel>

      <AdminCollapsibleFilters
        quickSearch={
          <AdminSearchInput
            value={search}
            onChange={setSearch}
            placeholder="Search case id, code, client, therapist…"
          />
        }
        activeChips={[
          statusFilter || null,
          therapistFilter
            ? therapists.find((t) => String(t.therapist_user_id) === therapistFilter)?.therapist_name
            : null,
          pendingOnly ? 'Pending reassignment' : null,
          search ? `Search: ${search}` : null,
        ].filter(Boolean)}
        activeCount={[statusFilter, therapistFilter, pendingOnly].filter(Boolean).length}
      >
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, padding: '0 16px 12px' }}>
          <FilterSelect
            label="Case status"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            options={STATUS_OPTIONS}
          />
          <FilterSelect
            label="Therapist"
            value={therapistFilter}
            onChange={(e) => setTherapistFilter(e.target.value)}
            options={therapistOptions}
          />
          <button
            type="button"
            className="admin-btn admin-btn--ghost admin-btn--sm"
            onClick={() => {
              setStatusFilter('')
              setTherapistFilter('')
              setPendingOnly(false)
              setSearch('')
            }}
          >
            Clear filters
          </button>
        </div>
      </AdminCollapsibleFilters>

      {loading ? (
        <p className="admin-muted">Loading…</p>
      ) : filtered.length === 0 ? (
        <AdminEmptyState
          title="No cases match these filters"
          hints={['Clear therapist or status filters', 'Try the pending reassignment KPI']}
        />
      ) : (
        <AdminDataList
          desktop={
            <div className="admin-table-wrap">
              <table className="admin-table" style={{ fontSize: '0.8125rem' }}>
                <thead>
                  <tr>
                    <th>Case ID</th>
                    <th>Case code</th>
                    <th>Client</th>
                    <th>Therapist</th>
                    <th>Status</th>
                    <th>Programme</th>
                    {includePay ? <th>Remuneration</th> : null}
                    <th>Flags</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((c) => (
                    <tr key={c.id} className={c.pending_reassignment ? 'sessions-dash__row--highlight' : ''}>
                      <td style={{ fontFamily: 'monospace' }}>{c.id}</td>
                      <td>
                        <span className="admin-table__primary">{c.case_code}</span>
                      </td>
                      <td>{c.child_name || '—'}</td>
                      <td>{c.therapist_name || 'Unassigned'}</td>
                      <td>
                        <StatusBadge status={c.status} />
                      </td>
                      <td>{c.product_module?.replace(/_/g, ' ') || '—'}</td>
                      {includePay ? <td>{c.pay_label || '—'}</td> : null}
                      <td>
                        {c.pending_reassignment ? (
                          <span className="admin-chip" style={{ background: '#fef3c7', color: '#b45309' }}>
                            Reassignment
                          </span>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td style={{ whiteSpace: 'nowrap' }}>
                        {canChangeStatus ? (
                          <select
                            className="admin-search__input"
                            style={{ width: 'auto', minWidth: 120, paddingLeft: 8, marginRight: 6 }}
                            disabled={statusBusyId === c.id}
                            defaultValue=""
                            aria-label={`Change status for ${c.case_code}`}
                            onChange={(e) => {
                              const next = e.target.value
                              e.target.value = ''
                              if (next) changeStatus(c, next)
                            }}
                          >
                            <option value="">Status…</option>
                            {(ALLOWED_NEXT[c.status] || []).map((s) => (
                              <option key={s} value={s}>
                                {s.replace(/_/g, ' ')}
                              </option>
                            ))}
                          </select>
                        ) : null}
                        <Link to={`/admin/cases/${c.id}`} className="admin-btn admin-btn--ghost admin-btn--sm">
                          View →
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          }
          mobile={
            <ul className="admin-data-list__cards">
              {filtered.map((c) => (
                <li key={c.id}>
                  <AdminTaskCard
                    highlight={c.pending_reassignment}
                    title={c.child_name || c.case_code}
                    meta={
                      <>
                        <span style={{ fontFamily: 'monospace' }}>#{c.id}</span>
                        {' · '}
                        {c.case_code}
                        {c.therapist_name ? ` · ${c.therapist_name}` : ' · Unassigned'}
                      </>
                    }
                    badges={
                      <>
                        <StatusBadge status={c.status} />
                        {c.pending_reassignment ? (
                          <span className="admin-chip" style={{ background: '#fef3c7', color: '#b45309' }}>
                            Reassignment
                          </span>
                        ) : null}
                      </>
                    }
                    actions={
                      <Link to={`/admin/cases/${c.id}`} className="admin-btn admin-btn--primary admin-btn--sm">
                        View case →
                      </Link>
                    }
                  >
                    {includePay && c.pay_label ? (
                      <p className="admin-muted" style={{ margin: 0, fontSize: '0.8125rem' }}>
                        Pay: {c.pay_label}
                      </p>
                    ) : null}
                  </AdminTaskCard>
                </li>
              ))}
            </ul>
          }
        />
      )}
    </div>
  )
}
