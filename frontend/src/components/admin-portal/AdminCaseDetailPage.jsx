import { useCallback, useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { AdminTherapistPicker } from './AdminTherapistPicker.jsx'
import { AdminScheduleSessionModal } from './AdminScheduleSessionModal.jsx'
import { AdminAssignSchedulePanel } from './AdminAssignSchedulePage.jsx'
import { CaseBillingForm } from './CaseBillingForm.jsx'
import { CaseServiceAddressForm } from './CaseServiceAddressForm.jsx'
import { StatusBadge } from './ui/index.js'

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'assignments', label: 'Assignments' },
  { id: 'logs', label: 'Session logs' },
  { id: 'reports', label: 'Reports' },
  { id: 'billing', label: 'Billing', perm: 'case.update' },
  { id: 'schedule', label: 'Schedule', perm: 'slot.book_any' },
  { id: 'schedule-assign', label: 'Assign schedule', perm: 'slot.book_any' },
]

export function AdminCaseDetailPage() {
  const { caseId } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'overview'
  const { can } = useAuth()
  const [caseRow, setCaseRow] = useState(null)
  const [assignments, setAssignments] = useState([])
  const [logs, setLogs] = useState([])
  const [reports, setReports] = useState([])
  const [therapistId, setTherapistId] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [scheduleOpen, setScheduleOpen] = useState(false)
  const [actingLogId, setActingLogId] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [c, asg, allLogs, allReports] = await Promise.all([
        apiFetch(`/api/v1/cases/${caseId}`),
        apiFetch(`/api/v1/cases/${caseId}/assignments`),
        apiFetch(`/api/v1/daily-logs?case_id=${caseId}`),
        apiFetch('/api/v1/reports/monthly?page_size=100'),
      ])
      setCaseRow(c)
      setAssignments(asg || [])
      setLogs(Array.isArray(allLogs) ? allLogs : unwrapList(allLogs))
      setReports(unwrapList(allReports).filter((r) => String(r.case_id) === String(caseId)))
    } catch (err) {
      setError(err.message || 'Case not found')
      setCaseRow(null)
    } finally {
      setLoading(false)
    }
  }, [caseId])

  useEffect(() => {
    load()
  }, [load])

  function setTab(id) {
    setSearchParams({ tab: id }, { replace: true })
  }

  async function handleAssign() {
    if (!therapistId || !caseRow) return
    await apiFetch(`/api/v1/cases/${caseRow.id}/assignments`, {
      method: 'POST',
      body: JSON.stringify({
        therapist_user_id: Number(therapistId),
        start_date: new Date().toISOString().slice(0, 10),
        reason_for_change: 'Assigned from case hub',
      }),
    })
    setTherapistId('')
    await load()
  }

  async function saveBilling(payload) {
    const updated = await apiFetch(`/api/v1/cases/${caseId}`, { method: 'PATCH', body: JSON.stringify(payload) })
    setCaseRow(updated)
  }

  async function saveServiceAddress(payload) {
    const updated = await apiFetch(`/api/v1/cases/${caseId}`, { method: 'PATCH', body: JSON.stringify(payload) })
    setCaseRow(updated)
  }

  async function reviewLog(logId, action) {
    setActingLogId(logId)
    try {
      await apiFetch(`/api/v1/daily-logs/${logId}/${action}`, { method: 'POST' })
      await load()
    } finally {
      setActingLogId(null)
    }
  }

  const visibleTabs = TABS.filter((t) => !t.perm || can(t.perm))

  if (loading) return <p className="admin-muted">Loading case…</p>
  if (error || !caseRow) {
    return (
      <div className="admin-page">
        <p style={{ color: '#b91c1c' }}>{error || 'Case not found'}</p>
        <Link to="/admin/cases">← Back to cases</Link>
      </div>
    )
  }

  const addr = caseRow.service_address

  return (
    <div className="admin-page">
      <p style={{ marginBottom: 8 }}>
        <Link to="/admin/cases" className="admin-btn admin-btn--ghost admin-btn--sm">
          ← Cases
        </Link>
      </p>
      <header style={{ marginBottom: 20 }}>
        <p className="admin-page__eyebrow">{caseRow.case_code}</p>
        <h1 className="admin-page__title">{caseRow.child_name}</h1>
        <p className="admin-page__subtitle">
          {caseRow.service_type} · <span className="admin-chip">{caseRow.product_module}</span>{' '}
          <StatusBadge status={caseRow.status} />
        </p>
      </header>

      <nav style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 20 }}>
        {visibleTabs.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`admin-btn admin-btn--sm ${tab === t.id ? 'admin-btn--primary' : 'admin-btn--ghost'}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {tab === 'overview' && (
        <section className="admin-layout admin-layout--stack">
          {addr ? (
            <div className="admin-panel" style={{ padding: 16 }}>
              <h3 style={{ marginTop: 0 }}>Service address</h3>
              <p style={{ margin: 0, fontSize: '0.875rem' }}>
                {[addr.address_line1, addr.address_line2, addr.city, addr.pincode].filter(Boolean).join(', ')}
              </p>
              {caseRow.maps_url ? (
                <a href={caseRow.maps_url} target="_blank" rel="noreferrer" className="admin-btn admin-btn--ghost admin-btn--sm" style={{ marginTop: 8 }}>
                  Open in Maps
                </a>
              ) : null}
            </div>
          ) : null}
          {can('case.update') ? (
            <>
              <CaseBillingForm caseItem={caseRow} onSave={saveBilling} />
              <CaseServiceAddressForm caseItem={caseRow} onSave={saveServiceAddress} />
            </>
          ) : (
            <CaseBillingForm caseItem={caseRow} readOnly />
          )}
        </section>
      )}

      {tab === 'assignments' && (
        <section>
          {can('case.assign') ? (
            <div className="admin-form-grid" style={{ maxWidth: 420, marginBottom: 16 }}>
              <label>
                Assign therapist
                <AdminTherapistPicker
                  mode="allotment"
                  productModule={caseRow.product_module}
                  caseId={caseRow.id}
                  value={therapistId}
                  onChange={setTherapistId}
                />
              </label>
              <button type="button" className="admin-btn admin-btn--primary" onClick={handleAssign} disabled={!therapistId}>
                Assign / Reassign
              </button>
            </div>
          ) : null}
          <ul className="admin-queue">
            {assignments.length === 0 ? (
              <li className="admin-queue__item">No assignments yet.</li>
            ) : (
              assignments.map((a) => (
                <li key={a.id} className="admin-queue__item">
                  <div>
                    <p className="admin-queue__title">{a.therapist_name || `Therapist #${a.therapist_user_id}`}</p>
                    <p className="admin-queue__meta">
                      {a.start_date}
                      {a.end_date ? ` → ${a.end_date}` : ''}
                    </p>
                  </div>
                  <StatusBadge status={a.status} />
                </li>
              ))
            )}
          </ul>
        </section>
      )}

      {tab === 'logs' && (
        <section>
          <p style={{ marginBottom: 12 }}>
            <Link to="/admin/logs" className="admin-btn admin-btn--ghost admin-btn--sm">
              Open full review queue
            </Link>
          </p>
          <ul className="admin-queue">
            {logs.length === 0 ? (
              <li className="admin-queue__item">No session logs for this case.</li>
            ) : (
              logs.map((log) => (
                <li key={log.id} className="admin-queue__item" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                    <div>
                      <p className="admin-queue__title">Log #{log.id}</p>
                      <p className="admin-queue__meta">{log.attendance_status}</p>
                    </div>
                    <StatusBadge status={log.approval_status} />
                  </div>
                  {log.session_notes ? (
                    <p style={{ fontSize: '0.8rem', margin: '8px 0 0' }}>
                      <strong>Internal:</strong> {log.session_notes}
                    </p>
                  ) : null}
                  {log.parent_notes ? (
                    <p style={{ fontSize: '0.8rem', margin: '4px 0 0' }}>
                      <strong>For family:</strong> {log.parent_notes}
                    </p>
                  ) : null}
                  {log.approval_status === 'PENDING' ? (
                    <div className="admin-btn-group" style={{ marginTop: 8 }}>
                      <button
                        type="button"
                        className="admin-btn admin-btn--sm admin-btn--primary"
                        disabled={actingLogId === log.id}
                        onClick={() => reviewLog(log.id, 'approve')}
                      >
                        Approve
                      </button>
                      <button
                        type="button"
                        className="admin-btn admin-btn--sm"
                        disabled={actingLogId === log.id}
                        onClick={() => reviewLog(log.id, 'reject')}
                      >
                        Reject
                      </button>
                    </div>
                  ) : null}
                </li>
              ))
            )}
          </ul>
        </section>
      )}

      {tab === 'reports' && (
        <section>
          <p style={{ marginBottom: 12 }}>
            <Link to="/admin/reports" className="admin-btn admin-btn--ghost admin-btn--sm">
              Open report review queue
            </Link>
          </p>
          <ul className="admin-queue">
            {reports.length === 0 ? (
              <li className="admin-queue__item">No reports for this case.</li>
            ) : (
              reports.map((r) => (
                <li key={r.id} className="admin-queue__item">
                  <div>
                    <p className="admin-queue__title">{r.month}</p>
                    <p className="admin-queue__meta">{r.summary?.slice(0, 120) || 'No summary'}</p>
                  </div>
                  <StatusBadge status={r.status} />
                </li>
              ))
            )}
          </ul>
        </section>
      )}

      {tab === 'billing' && can('case.update') && <CaseBillingForm caseItem={caseRow} onSave={saveBilling} />}

      {tab === 'schedule' && can('slot.book_any') && (
        <section>
          <button type="button" className="admin-btn admin-btn--primary" onClick={() => setScheduleOpen(true)}>
            Schedule session
          </button>
        </section>
      )}

      {tab === 'schedule-assign' && can('slot.book_any') && (
        <AdminAssignSchedulePanel caseItem={caseRow} assignments={assignments} onDone={load} />
      )}

      <AdminScheduleSessionModal
        open={scheduleOpen}
        caseItem={caseRow}
        onClose={() => setScheduleOpen(false)}
        onDone={() => {
          setScheduleOpen(false)
          load()
        }}
      />
    </div>
  )
}
