import { useCallback, useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'

import { CaseBillingForm } from './CaseBillingForm.jsx'
import { CaseBillingActionsCard } from './CaseBillingActionsCard.jsx'
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
import { isFinanceDeskUser } from '../../lib/financeDesk.js'
import { isCaseManagerOnlyRole } from '../../lib/adminCasePipeline.js'
import { CaseSessionsAndLogsPanel } from './CaseSessionsAndLogsPanel.jsx'
import { CaseDayTypeBadge } from './CaseDayTypeBadge.jsx'
import { CaseOverviewPanel } from './CaseOverviewPanel.jsx'
import './admin-case-detail-mobile.css'

const BILLING_TAB_PERMS = ['case.update', 'case.billing.update', 'invoice.approve', 'admin.override']

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
  { id: 'billing', label: 'Billing', perms: BILLING_TAB_PERMS },
  { id: 'scheduling', label: 'Assign & Schedule', perm: 'slot.book_any' },
]

const FINANCE_TAB_IDS = new Set(['overview', 'activity', 'logs', 'billing'])

export function AdminCaseDetailPage() {
  const { caseId } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'overview'
  const highlightSessionId = searchParams.get('session_id')
  const highlightIncidentId = searchParams.get('incident_id')
  const billingApprovalRequestId = searchParams.get('billing_approval')
  const { can, canWriteProduct, isViewOnly, user } = useAuth()
  const { canReviewLogs } = useModuleWrite()
  const financeDesk = isFinanceDeskUser(user)
  const cmFocused = isCaseManagerOnlyRole(user?.roles || [])
  const clinicalRevamp = isReportsRevampActive('admin')
  const [caseRow, setCaseRow] = useState(null)
  const [assignments, setAssignments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const accessAsMentor = Boolean(caseRow?.access_as_mentor)
  const canSeeBilling =
    !accessAsMentor &&
    !cmFocused &&
    (can('case.update') || can('case.billing.update') || can('invoice.approve') || can('admin.override'))
  const visibleTabs = TABS.filter(
    (t) =>
      (!financeDesk || FINANCE_TAB_IDS.has(t.id)) &&
      !(accessAsMentor && (t.id === 'billing' || t.id === 'scheduling')) &&
      !(cmFocused && (t.id === 'billing' || t.id === 'cm-meetings')) &&
      (t.id !== 'billing' || canSeeBilling) &&
      (!t.perm || can(t.perm)) &&
      (!t.perms || t.perms.some((permission) => can(permission))) &&
      (t.id !== 'observation' || clinicalRevamp),
  )
  const visibleTabIds = visibleTabs.map((t) => t.id)

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
    if (highlightSessionId && tab !== 'logs') {
      setSearchParams({ tab: 'logs', session_id: highlightSessionId }, { replace: true })
    }
  }, [highlightSessionId, tab, setSearchParams])

  useEffect(() => {
    if (financeDesk) return
    if (!highlightIncidentId || tab === 'incidents' || !can('incident.read_sensitive')) return
    setSearchParams({ tab: 'incidents', incident_id: highlightIncidentId }, { replace: true })
  }, [financeDesk, highlightIncidentId, tab, setSearchParams, can])

  useEffect(() => {
    if (!visibleTabIds.length || visibleTabIds.includes(tab)) return
    setSearchParams({ tab: visibleTabIds[0] }, { replace: true })
  }, [tab, visibleTabIds, setSearchParams])

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
      !caseRow.access_as_mentor &&
      can('case.update') &&
      !isViewOnly &&
      !financeDesk &&
      canWriteProduct(caseRow.product_module),
  )
  const canEditBilling = Boolean(
    caseRow &&
      !caseRow.in_transition &&
      !caseRow.access_as_mentor &&
      !isViewOnly &&
      !financeDesk &&
      (can('case.billing.update') || can('invoice.approve') || can('admin.override')),
  )
  const canReopenCase = Boolean(
    can('admin.override') ||
      (user?.roles || []).some((r) => ['SUPER_ADMIN', 'MODULE_ADMIN', 'ADMIN', 'HR'].includes(r)),
  )
  const canAssignCase = Boolean(
    caseRow &&
      !caseRow.access_as_mentor &&
      can('case.assign') &&
      !financeDesk &&
      canWriteProduct(caseRow.product_module),
  )
  const isAssignedCaseManager = Boolean(
    caseRow && user?.id && caseRow.case_manager_user_id === user.id,
  )
  const canReviewCaseLogs = Boolean(
    caseRow &&
      can('daily_log.review') &&
      !isViewOnly &&
      !financeDesk &&
      !accessAsMentor &&
      (canReviewLogs(caseRow.product_module) || isAssignedCaseManager),
  )

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
          {caseRow.access_as_mentor ? (
            <span className="admin-badge admin-badge--info" style={{ marginLeft: 8 }}>
              Mentor view
            </span>
          ) : null}
        </p>
      </header>

      {caseRow.access_as_mentor ? (
        <p className="admin-alert admin-alert--info" role="status">
          You are viewing this case as a mentor. You can open cases, logs, and reports, and mark logs as
          reviewed — other changes stay with the assigned case manager.
        </p>
      ) : null}
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
        <CaseOverviewPanel
          caseRow={caseRow}
          canEditCase={canEditCase}
          canReopenCase={canReopenCase}
          onCaseChanged={(updatedCase) => setCaseRow(updatedCase)}
        />
      )}



      {tab === 'logs' && (
        <section>
          <CaseSessionsAndLogsPanel
            caseId={caseId}
            highlightSessionId={highlightSessionId}
            canReview={canReviewCaseLogs}
            attendanceOnly={financeDesk}
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

      {tab === 'cm-meetings' && !cmFocused && <AdminCaseCmMeetingsPanel caseId={caseRow?.id || caseId} />}

      {tab === 'billing' && canSeeBilling && !cmFocused && (
        <section className="admin-layout admin-layout--stack">
          {billingApprovalRequestId && !financeDesk ? (
            <BillingApprovalPanel requestId={billingApprovalRequestId} onApplied={load} />
          ) : null}
          {!financeDesk && (can('invoice.approve') || can('case.update')) && caseRow?.id ? (
            <CaseBillingActionsCard caseId={caseRow.id} />
          ) : null}
          {!canEditBilling ? (
            <p className="admin-alert" style={{ color: '#b45309' }}>
              {financeDesk
                ? 'Billing is view-only here — use Client invoices or Therapist payouts to change money records.'
                : 'View-only access — you cannot change billing for this module.'}
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

      {!financeDesk ? (
        <AdminCaseDetailFab
          caseId={caseRow.id}
          visibleTabIds={visibleTabIds}
          onSelectTab={setTab}
          canInvoice={can('invoice.approve') || can('case.update')}
        />
      ) : null}
    </div>
  )
}
