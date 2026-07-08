import { useCallback, useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { caseServiceLine } from '../../lib/moduleLabels.js'
import { useTherapistActiveCase } from '../../context/TherapistActiveCaseContext.jsx'
import { CaseProfileShell } from '../case-profile/CaseProfileShell.jsx'
import { CaseReportsHub } from '../case-profile/CaseReportsHub.jsx'
import { THERAPIST_CASE_TABS } from '../case-profile/caseProfileTabs.js'
import { resolveLegacyReportsSection } from '../case-profile/reportsHubSections.js'
import { CaseInsightsTab } from '../clinical/insights-v2/CaseInsightsTab.jsx'
import { GoalStrategyEnginePage } from '../clinical/goals-strategy/GoalStrategyEnginePage.jsx'
import { EvidenceDrivePanel } from '../case-profile/sections/EvidenceDrivePanel.jsx'
import { TherapistCaseOverviewDashboard } from '../clinical/therapist/TherapistCaseOverviewDashboard.jsx'
import { CaseSessionsPanel } from './CaseSessionsPanel.jsx'
import './my-cases.css'
import '../../styles/case-profile-v2.css'

function StatusChangeModal({ open, onClose, statusTo, setStatusTo, statusReason, setStatusReason, statusBusy, statusMsg, onSubmit }) {
  if (!open) return null
  return (
    <div className="ic-case-status-modal" role="dialog" aria-modal="true" aria-labelledby="status-modal-title">
      <button type="button" className="ic-case-status-modal__backdrop" aria-label="Close" onClick={onClose} />
      <div className="ic-case-status-modal__sheet">
        <h2 id="status-modal-title">Request status change</h2>
        <p className="ic-case-panel__hint">Submit a request for admin approval. Your case stays active until reviewed.</p>
        {statusMsg ? <p className="ic-case-status-modal__msg">{statusMsg}</p> : null}
        <div className="ic-case-status-modal__form">
          <label>
            New status
            <select value={statusTo} onChange={(e) => setStatusTo(e.target.value)} className="ic-case-panel__select">
              <option value="SUSPENDED">Suspend case</option>
              <option value="CLOSED">Close case</option>
              <option value="ACTIVE">Reactivate case</option>
            </select>
          </label>
          <label>
            Reason (required)
            <textarea value={statusReason} onChange={(e) => setStatusReason(e.target.value)} rows={4} placeholder="Why are you requesting this change?" />
          </label>
          <div className="ic-case-status-modal__actions">
            <button type="button" className="ic-btn ic-btn--ghost" onClick={onClose}>Cancel</button>
            <button type="button" className="ic-btn ic-btn--primary" disabled={statusBusy || statusReason.trim().length < 5} onClick={onSubmit}>
              {statusBusy ? 'Submitting…' : 'Submit request'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export function CaseDetailRevamp() {
  const { caseId } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'overview'
  const { setActiveCase, touchRecentCase } = useTherapistActiveCase()
  const [caseRow, setCaseRow] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [statusTo, setStatusTo] = useState('SUSPENDED')
  const [statusReason, setStatusReason] = useState('')
  const [statusMsg, setStatusMsg] = useState('')
  const [statusBusy, setStatusBusy] = useState(false)
  const [statusModalOpen, setStatusModalOpen] = useState(false)
  const [clinicalProfile, setClinicalProfile] = useState(null)
  const [statusPending, setStatusPending] = useState(null)
  const [statusHistory, setStatusHistory] = useState([])
  const [qualitySummary, setQualitySummary] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [c, profile, statusReqs, quality] = await Promise.all([
        apiFetch(`/api/v1/cases/${caseId}`),
        apiFetch(`/api/v1/cases/${caseId}/clinical-profile`).catch(() => null),
        apiFetch(`/api/v1/cases/${caseId}/status-requests`).catch(() => ({ pending: null, history: [] })),
        apiFetch(`/api/v1/cases/${caseId}/clinical-quality-summary`).catch(() => null),
      ])
      setCaseRow(c)
      setClinicalProfile(profile)
      setStatusPending(statusReqs?.pending || null)
      setStatusHistory(statusReqs?.history || [])
      setQualitySummary(quality)
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
    if (!caseRow?.id) return
    setActiveCase({
      id: caseRow.id,
      case_code: caseRow.case_code,
      child_name: caseRow.child_name,
    })
    touchRecentCase(caseRow.id)
  }, [caseRow, setActiveCase, touchRecentCase])

  useEffect(() => {
    const legacy = resolveLegacyReportsSection(searchParams)
    if (legacy) {
      setSearchParams(legacy, { replace: true })
      return
    }
    if (searchParams.get('tab') === 'sessions') {
      const next = new URLSearchParams(searchParams)
      next.set('tab', 'logs')
      setSearchParams(next, { replace: true })
    }
  }, [searchParams, setSearchParams])

  function setTab(id, options = {}) {
    const next = new URLSearchParams(searchParams)
    next.set('tab', id)
    if (id === 'reports') {
      next.set('section', options.section || next.get('section') || 'dashboard')
    } else {
      next.delete('section')
      next.delete('sub')
    }
    setSearchParams(next, { replace: true })
  }

  async function submitStatusRequest() {
    setStatusBusy(true)
    setStatusMsg('')
    try {
      await apiFetch(`/api/v1/cases/${caseId}/status-requests`, {
        method: 'POST',
        body: JSON.stringify({ to_status: statusTo, reason: statusReason.trim() }),
      })
      setStatusMsg('Request submitted. Your case manager will review it.')
      setStatusReason('')
      setStatusModalOpen(false)
      await load()
    } catch (err) {
      setStatusMsg(err.message || 'Could not submit request')
    } finally {
      setStatusBusy(false)
    }
  }

  if (loading) return <p className="ic-my-cases ic-case-detail__loading">Loading case…</p>
  if (error || !caseRow) {
    return (
      <div className="ic-my-cases ic-case-detail">
        <p className="ic-case-detail__error">{error || 'Case not found'}</p>
        <Link to="/therapist/cases" className="ic-case-detail__back">← My Cases</Link>
      </div>
    )
  }

  const childLabel = `${caseRow.child_name} (${caseRow.case_code})`
  const focusLine = caseServiceLine(caseRow.service_type, caseRow.product_module)

  return (
    <>
      <CaseProfileShell
        caseId={caseId}
        enableChangeCase
        caseCode={caseRow.case_code}
        childName={caseRow.child_name}
        status={caseRow.status}
        statusPending={statusPending}
        serviceType={focusLine}
        service={caseRow.service_type}
        productModule={caseRow.product_module}
        onStatusRequest={(toStatus) => {
          setStatusTo(toStatus)
          setStatusMsg('')
          setStatusModalOpen(true)
        }}
        tabs={THERAPIST_CASE_TABS}
        activeTab={tab}
        onTabChange={setTab}
      >
        {statusPending ? (
          <p className="ic-case-detail__pending-banner" role="status">
            Status change requested — waiting for admin approval.
          </p>
        ) : null}

        {tab === 'overview' ? (
          <TherapistCaseOverviewDashboard
            caseId={caseId}
            caseRow={caseRow}
            clinicalProfile={clinicalProfile}
            qualitySummary={qualitySummary}
            onOpenTab={setTab}
            onClinicalProfileUpdated={setClinicalProfile}
          />
        ) : null}

        {tab === 'reports' ? (
          <CaseReportsHub
            caseId={caseId}
            caseCode={caseRow.case_code}
            childName={caseRow.child_name}
            variant="therapist"
            onUpdated={load}
          />
        ) : null}

        {tab === 'goals' || tab === 'strategies' ? (
          <GoalStrategyEnginePage caseId={caseId} variant="therapist" />
        ) : null}

        {tab === 'logs' ? (
          <CaseSessionsPanel
            caseId={Number(caseId)}
            caseCode={caseRow.case_code}
            childName={caseRow.child_name}
            childLabel={childLabel}
            initialSessionId={searchParams.get('session_id') || searchParams.get('session')}
            initialLogId={searchParams.get('log_id')}
            onScheduleChange={load}
          />
        ) : null}

        {tab === 'insights' ? (
          <CaseInsightsTab caseId={caseId} variant="therapist" />
        ) : null}

        {tab === 'documents' ? (
          <EvidenceDrivePanel
            caseId={Number(caseId)}
            variant="therapist"
            childName={caseRow.child_name}
            caseCode={caseRow.case_code}
          />
        ) : null}
      </CaseProfileShell>

      <StatusChangeModal
        open={statusModalOpen}
        onClose={() => setStatusModalOpen(false)}
        statusTo={statusTo}
        setStatusTo={setStatusTo}
        statusReason={statusReason}
        setStatusReason={setStatusReason}
        statusBusy={statusBusy}
        statusMsg={statusMsg}
        onSubmit={submitStatusRequest}
      />
    </>
  )
}
