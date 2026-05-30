import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'
import { AdminTherapistPicker } from './AdminTherapistPicker.jsx'
import { CaseBillingForm } from './CaseBillingForm.jsx'
import { CaseBillingActionsCard } from './CaseBillingActionsCard.jsx'
import { CaseServiceAddressForm } from './CaseServiceAddressForm.jsx'
import { PortalTabBar, StatusBadge } from './ui/index.js'
import { AdminCaseReportsPanel } from './AdminCaseReportsPanel.jsx'
import { AdminCaseIncidentsPanel } from './AdminCaseIncidentsPanel.jsx'
import { AdminCaseCmMeetingsPanel } from './AdminCaseCmMeetingsPanel.jsx'
import { AdminCaseSchedulingPanel } from './AdminCaseSchedulingPanel.jsx'
import { AdminCaseDetailMobileHeader } from './AdminCaseDetailMobileHeader.jsx'
import { AdminCaseDetailMobileNav } from './AdminCaseDetailMobileNav.jsx'
import { AdminCaseDetailQuickStats } from './AdminCaseDetailQuickStats.jsx'
import { AdminCaseDetailFab } from './AdminCaseDetailFab.jsx'
import { CaseActivityPanel } from './CaseActivityPanel.jsx'
import { CaseDocumentsPanel } from '../documents/CaseDocumentsPanel.jsx'
import { IepBuilderPanel } from './IepBuilderPanel.jsx'
import { CaseSessionsAndLogsPanel } from './CaseSessionsAndLogsPanel.jsx'
import './admin-case-detail-mobile.css'

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'activity', label: 'Activity' },
  { id: 'assignments', label: 'Assignments' },
  { id: 'logs', label: 'Session logs' },
  { id: 'reports', label: 'Reports' },
  { id: 'incidents', label: 'Incidents', perm: 'incident.read_sensitive' },
  { id: 'iep', label: 'IEP builder', perm: 'iep.read' },
  { id: 'documents', label: 'Documents' },
  { id: 'cm-meetings', label: 'CM meetings' },
  { id: 'billing', label: 'Billing', perm: 'case.update' },
  { id: 'scheduling', label: 'Scheduling', perm: 'slot.book_any' },
]

export function AdminCaseDetailPage() {
  const { caseId } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'overview'
  const highlightSessionId = searchParams.get('session_id')
  const highlightIncidentId = searchParams.get('incident_id')
  const { can, canWriteProduct, isViewOnly } = useAuth()
  const { canReviewLogs } = useModuleWrite()
  const [caseRow, setCaseRow] = useState(null)
  const [assignments, setAssignments] = useState([])
  const [therapistId, setTherapistId] = useState('')
  const [assignStartDate, setAssignStartDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [assignReason, setAssignReason] = useState('Assigned from case hub')
  const [assignBusy, setAssignBusy] = useState(false)
  const [assignSuccess, setAssignSuccess] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [parentContact, setParentContact] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [c, asg] = await Promise.all([
        apiFetch(`/api/v1/cases/${caseId}`),
        apiFetch(`/api/v1/cases/${caseId}/assignments`),
      ])
      setCaseRow(c)
      setAssignments(asg || [])
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

  useEffect(() => {
    if (!caseRow?.child_id) {
      setParentContact(null)
      return
    }
    let cancelled = false
    apiFetch(`/api/v1/admin/families?search=${encodeURIComponent(caseRow.case_code || '')}`)
      .then((rows) => {
        if (cancelled) return
        const match = (rows || []).find((f) => f.childId === caseRow.child_id)
        const parent = match?.parents?.[0]
        if (parent?.parentPhone || parent?.parentEmail) {
          setParentContact({ phone: parent.parentPhone, email: parent.parentEmail })
        } else {
          setParentContact(null)
        }
      })
      .catch(() => {
        if (!cancelled) setParentContact(null)
      })
    return () => {
      cancelled = true
    }
  }, [caseRow?.child_id, caseRow?.case_code])

  useEffect(() => {
    if (highlightSessionId && tab !== 'logs') {
      setSearchParams({ tab: 'logs', session_id: highlightSessionId }, { replace: true })
    }
  }, [highlightSessionId, tab, setSearchParams])

  useEffect(() => {
    if (!highlightIncidentId || tab === 'incidents' || !can('incident.read_sensitive')) return
    setSearchParams({ tab: 'incidents', incident_id: highlightIncidentId }, { replace: true })
  }, [highlightIncidentId, tab, setSearchParams])

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

  const [billingMsg, setBillingMsg] = useState('')
  const [billingErr, setBillingErr] = useState('')

  async function saveBilling(payload) {
    setBillingErr('')
    setBillingMsg('')
    const updated = await apiFetch(`/api/v1/cases/${caseId}`, { method: 'PATCH', body: JSON.stringify(payload) })
    setCaseRow(updated)
    setBillingMsg('Billing saved.')
  }

  async function saveServiceAddress(payload) {
    const updated = await apiFetch(`/api/v1/cases/${caseId}`, { method: 'PATCH', body: JSON.stringify(payload) })
    setCaseRow(updated)
  }

  const activeAssignment = assignments.find((a) => a.status === 'ACTIVE') || assignments[0]
  const canEditCase = Boolean(
    caseRow && can('case.update') && !isViewOnly && canWriteProduct(caseRow.product_module),
  )
  const canAssignCase = Boolean(caseRow && can('case.assign') && canWriteProduct(caseRow.product_module))
  const canReviewCaseLogs = Boolean(
    caseRow && can('daily_log.review') && canReviewLogs(caseRow.product_module),
  )
  const visibleTabs = TABS.filter((t) => !t.perm || can(t.perm))
  const visibleTabIds = visibleTabs.map((t) => t.id)

  function openScheduleTab() {
    if (visibleTabIds.includes('scheduling')) setTab('scheduling')
    else if (visibleTabIds.includes('cm-meetings')) setTab('cm-meetings')
  }

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
    <div className="admin-page admin-case-detail-page">
      <p style={{ marginBottom: 8 }}>
        <Link to="/admin/cases" className="admin-btn admin-btn--ghost admin-btn--sm">
          ← Cases
        </Link>
      </p>

      <AdminCaseDetailMobileHeader
        caseRow={caseRow}
        activeAssignment={activeAssignment}
        parentContact={parentContact}
        onQuickAction={(id) => (id === 'scheduling' ? openScheduleTab() : setTab(id))}
      />

      <header className="admin-case-detail__header-compact admin-case-detail__header--desktop" style={{ marginBottom: 12 }}>
        <p className="admin-page__eyebrow">{caseRow.case_code}</p>
        <h1 className="admin-page__title">{caseRow.child_name}</h1>
        <p className="admin-page__subtitle admin-portal-lead">
          Therapist:{' '}
          <strong>{activeAssignment?.therapist_name || 'Unassigned'}</strong>
          {' · '}
          {caseRow.service_type} · <span className="admin-chip">{caseRow.product_module}</span>{' '}
          <StatusBadge status={caseRow.status} />
        </p>
      </header>

      <AdminCaseDetailQuickStats
        caseId={caseId}
        caseRow={caseRow}
        onNavigateTab={setTab}
        visibleTabIds={visibleTabIds}
      />

      <PortalTabBar
        className="admin-case-detail__tabs admin-case-detail__tabs--desktop admin-page__tabs-scroll"
        ariaLabel="Case sections"
        activeId={tab}
        onChange={setTab}
        tabs={visibleTabs.map((t) => ({ id: t.id, label: t.label }))}
      />

      <AdminCaseDetailMobileNav activeId={tab} onChange={setTab} visibleTabIds={visibleTabIds} />

      {tab === 'activity' && <CaseActivityPanel caseId={caseId} />}

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
          <CaseBillingForm caseItem={caseRow} readOnly />
          {canEditCase ? (
            <>
              <p style={{ fontSize: '0.85rem', margin: '8px 0 0' }}>
                <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setTab('billing')}>
                  Edit billing & address →
                </button>
              </p>
            </>
          ) : null}
          {canEditCase ? (
            <CaseServiceAddressForm caseItem={caseRow} onSave={saveServiceAddress} />
          ) : null}
        </section>
      )}

      {tab === 'assignments' && (
        <section>
          {canAssignCase ? (
            <div className="admin-form-grid" style={{ maxWidth: 480, marginBottom: 16 }}>
              {activeAssignment ? (
                <p className="admin-muted" style={{ gridColumn: '1 / -1', fontSize: '0.875rem' }}>
                  Active: {activeAssignment.therapist_name || `#${activeAssignment.therapist_user_id}`} since{' '}
                  {activeAssignment.start_date}. Selecting another therapist will end this assignment.
                </p>
              ) : null}
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
              <label>
                Start date
                <input
                  type="date"
                  className="admin-input"
                  value={assignStartDate}
                  onChange={(e) => setAssignStartDate(e.target.value)}
                />
              </label>
              <label style={{ gridColumn: '1 / -1' }}>
                Reason for change
                <input
                  type="text"
                  className="admin-input"
                  value={assignReason}
                  onChange={(e) => setAssignReason(e.target.value)}
                  placeholder="e.g. Caseload rebalance"
                />
              </label>
              {assignSuccess ? <p className="admin-alert admin-alert--success" style={{ gridColumn: '1 / -1' }}>{assignSuccess}</p> : null}
              <button
                type="button"
                className="admin-btn admin-btn--primary"
                onClick={handleAssign}
                disabled={!therapistId || assignBusy}
              >
                {assignBusy ? 'Saving…' : activeAssignment ? 'Reassign therapist' : 'Assign therapist'}
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
          <CaseSessionsAndLogsPanel
            caseId={caseId}
            highlightSessionId={highlightSessionId}
            canReview={canReviewCaseLogs}
          />
        </section>
      )}

      {tab === 'reports' && (
        <AdminCaseReportsPanel
          caseId={caseRow?.id || caseId}
          highlightReportId={searchParams.get('reportId')}
          highlightType={searchParams.get('type')}
        />
      )}

      {tab === 'incidents' && can('incident.read_sensitive') && (
        <AdminCaseIncidentsPanel
          caseId={caseRow?.id || caseId}
          highlightIncidentId={highlightIncidentId}
        />
      )}

      {tab === 'iep' && can('iep.read') && <IepBuilderPanel caseId={caseRow?.id || caseId} />}

      {tab === 'documents' && (
        <CaseDocumentsPanel caseId={Number(caseRow?.id || caseId)} variant="admin" />
      )}

      {tab === 'cm-meetings' && <AdminCaseCmMeetingsPanel caseId={caseRow?.id || caseId} />}

      {tab === 'billing' && can('case.update') && (
        <section className="admin-layout admin-layout--stack">
          {(can('invoice.approve') || can('case.update')) && caseRow?.id ? (
            <CaseBillingActionsCard caseId={caseRow.id} />
          ) : null}
          {!canEditCase ? (
            <p className="admin-alert" style={{ color: '#b45309' }}>
              View-only access — you cannot change billing for this module.
            </p>
          ) : null}
          {billingErr ? <p className="admin-alert" style={{ color: '#b91c1c' }}>{billingErr}</p> : null}
          {billingMsg ? <p className="admin-alert admin-alert--success">{billingMsg}</p> : null}
          <CaseBillingForm
            caseItem={caseRow}
            onSave={saveBilling}
            readOnly={!canEditCase}
            onError={setBillingErr}
          />
          <CaseServiceAddressForm caseItem={caseRow} onSave={saveServiceAddress} readOnly={!canEditCase} />
        </section>
      )}

      {tab === 'scheduling' && can('slot.book_any') && (
        <AdminCaseSchedulingPanel caseItem={caseRow} assignments={assignments} onDone={load} />
      )}

      <AdminCaseDetailFab
        caseId={caseRow.id}
        visibleTabIds={visibleTabIds}
        onSelectTab={setTab}
        canInvoice={can('invoice.approve') || can('case.update')}
      />
    </div>
  )
}
