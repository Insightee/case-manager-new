import { useCallback, useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'

import { CaseBillingForm } from './CaseBillingForm.jsx'
import { CaseBillingActionsCard } from './CaseBillingActionsCard.jsx'
import { CaseZohoIdForm } from './CaseZohoIdForm.jsx'
import { BillingApprovalPanel } from './BillingApprovalPanel.jsx'
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
import { IepReportRoute } from '../reports-engine/iep/IepReportRoute.jsx'
import { ObservationReportRoute } from '../reports-engine/observation/ObservationReportRoute.jsx'
import { isReportsRevampActive } from '../../lib/reportsRevampFlags.js'
import { CaseSessionsAndLogsPanel } from './CaseSessionsAndLogsPanel.jsx'
import { CaseClientStatusCard } from './CaseClientStatusCard.jsx'
import { CaseDayTypeBadge } from './CaseDayTypeBadge.jsx'
import './admin-case-detail-mobile.css'

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'activity', label: 'Activity' },
  { id: 'logs', label: 'Session logs' },
  { id: 'reports', label: 'Reports' },
  { id: 'incidents', label: 'Incidents', perm: 'incident.read_sensitive' },
  { id: 'iep', label: 'IEP', perm: 'iep.read' },
  { id: 'observation', label: 'Observation' },
  { id: 'documents', label: 'Documents' },
  { id: 'cm-meetings', label: 'Meetings' },
  { id: 'billing', label: 'Billing', perms: ['case.update', 'case.billing.update'] },
  { id: 'scheduling', label: 'Assign & Schedule', perm: 'slot.book_any' },
]

export function AdminCaseDetailPage() {
  const { caseId } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'overview'
  const highlightSessionId = searchParams.get('session_id')
  const highlightIncidentId = searchParams.get('incident_id')
  const billingApprovalRequestId = searchParams.get('billing_approval')
  const { can, canWriteProduct, isViewOnly, user } = useAuth()
  const { canReviewLogs } = useModuleWrite()
  const [caseRow, setCaseRow] = useState(null)
  const [assignments, setAssignments] = useState([])
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
    const next = { tab: id }
    if (id === 'logs' && highlightSessionId) {
      next.session_id = highlightSessionId
    }
    setSearchParams(next, { replace: true })
  }



  const [billingMsg, setBillingMsg] = useState('')
  const [billingErr, setBillingErr] = useState('')

  async function saveBilling(payload) {
    setBillingErr('')
    setBillingMsg('')
    const updated = await apiFetch(`/api/v1/cases/${caseId}/billing`, { method: 'PATCH', body: JSON.stringify(payload) })
    setCaseRow(updated)
    if (updated.billing_approval_status === 'PENDING') {
      setSearchParams(
        { tab: 'billing', billing_approval: String(updated.billing_approval_request_id) },
        { replace: true },
      )
      setBillingMsg('Approval requested. Current billing remains active until Nicky approves it.')
    } else {
      setBillingMsg('Billing saved.')
    }
  }

  async function saveServiceAddress(payload) {
    const updated = await apiFetch(`/api/v1/cases/${caseId}`, { method: 'PATCH', body: JSON.stringify(payload) })
    setCaseRow(updated)
  }

  const activeAssignment = assignments.find((a) => a.status === 'ACTIVE') || null
  const canEditCase = Boolean(
    caseRow &&
      !caseRow.in_transition &&
      can('case.update') &&
      !isViewOnly &&
      canWriteProduct(caseRow.product_module),
  )
  const canEditBilling = Boolean(
    caseRow &&
      !caseRow.in_transition &&
      !isViewOnly &&
      (can('case.billing.update') || canEditCase),
  )
  const canManageStatus = Boolean(
    caseRow &&
      !caseRow.in_transition &&
      !isViewOnly &&
      (can('admin.override') ||
        can('case.status_manage') ||
        (can('case.update') && canWriteProduct(caseRow.product_module))),
  )
  const canReopenCase = Boolean(
    can('admin.override') ||
      (user?.roles || []).some((r) => ['SUPER_ADMIN', 'MODULE_ADMIN', 'ADMIN', 'HR'].includes(r)),
  )
  const canAssignCase = Boolean(caseRow && can('case.assign') && canWriteProduct(caseRow.product_module))
  const isAssignedCaseManager = Boolean(
    caseRow && user?.id && caseRow.case_manager_user_id === user.id,
  )
  const canReviewCaseLogs = Boolean(
    caseRow &&
      can('daily_log.review') &&
      !isViewOnly &&
      (canReviewLogs(caseRow.product_module) || isAssignedCaseManager),
  )
  const clinicalRevamp = isReportsRevampActive('admin')
  const visibleTabs = TABS.filter(
    (t) =>
      (!t.perm || can(t.perm)) &&
      (!t.perms || t.perms.some((permission) => can(permission))) &&
      (t.id !== 'observation' || clinicalRevamp),
  )
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
      {caseRow.in_transition ? (
        <p className="admin-alert admin-alert--info">
          Therapist handover in progress. Case changes are paused; transition logs, transition-date management, and incident reporting remain available.
        </p>
      ) : null}
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
          {caseRow.day_type ? <CaseDayTypeBadge dayType={caseRow.day_type} /> : null}
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
          {caseRow ? (
            <CaseClientStatusCard
              caseId={caseRow.id}
              caseRow={caseRow}
              canEdit={canManageStatus}
              canReopen={canReopenCase}
              onStatusChanged={(updatedCase) => setCaseRow(updatedCase)}
            />
          ) : null}
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
          <CaseZohoIdForm caseItem={caseRow} canEdit={canEditCase} onSaved={setCaseRow} />
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

      {tab === 'iep' && can('iep.read') && (
        clinicalRevamp ? (
          <IepReportRoute
            caseId={Number(caseRow?.id || caseId)}
            caseCode={caseRow?.case_code}
            childName={caseRow?.child_name || caseRow?.child?.full_name}
            variant="admin"
          />
        ) : (
          <IepBuilderPanel caseId={caseRow?.id || caseId} />
        )
      )}

      {tab === 'observation' && clinicalRevamp ? (
        <ObservationReportRoute
          caseId={Number(caseRow?.id || caseId)}
          caseCode={caseRow?.case_code}
          childName={caseRow?.child_name || caseRow?.child?.full_name}
          variant="admin"
        />
      ) : null}

      {tab === 'documents' && (
        <CaseDocumentsPanel caseId={Number(caseRow?.id || caseId)} variant="admin" />
      )}

      {tab === 'cm-meetings' && <AdminCaseCmMeetingsPanel caseId={caseRow?.id || caseId} />}

      {tab === 'billing' && (can('case.update') || can('case.billing.update')) && (
        <section className="admin-layout admin-layout--stack">
          {billingApprovalRequestId ? (
            <BillingApprovalPanel requestId={billingApprovalRequestId} onApplied={load} />
          ) : null}
          {(can('invoice.approve') || can('case.update')) && caseRow?.id ? (
            <CaseBillingActionsCard caseId={caseRow.id} />
          ) : null}
          {!canEditBilling ? (
            <p className="admin-alert" style={{ color: '#b45309' }}>
              View-only access — you cannot change billing for this module.
            </p>
          ) : null}
          {billingErr ? <p className="admin-alert" style={{ color: '#b91c1c' }}>{billingErr}</p> : null}
          {billingMsg ? <p className="admin-alert admin-alert--success">{billingMsg}</p> : null}
          <CaseBillingForm
            caseItem={caseRow}
            onSave={saveBilling}
            readOnly={!canEditBilling}
            onError={setBillingErr}
          />
          <CaseServiceAddressForm caseItem={caseRow} onSave={saveServiceAddress} readOnly={!canEditCase} />
        </section>
      )}

      {tab === 'scheduling' && can('slot.book_any') && (
        <AdminCaseSchedulingPanel
          caseItem={caseRow}
          assignments={assignments}
          onDone={load}
          onCaseUpdated={(updated) => setCaseRow(updated)}
          canAssign={canAssignCase}
          canEditBilling={canEditCase}
        />
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
