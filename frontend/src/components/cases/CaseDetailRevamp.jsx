import { useCallback, useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { mergeUpcomingSchedule } from '../../lib/therapistSchedule.js'
import { therapistTicketsUrl } from '../../lib/therapistTicketOptions.js'
import { caseServiceLine } from '../../lib/moduleLabels.js'
import { CaseProfileShell } from '../case-profile/CaseProfileShell.jsx'
import { CaseReportsHub } from '../case-profile/CaseReportsHub.jsx'
import { THERAPIST_CASE_TABS } from '../case-profile/caseProfileTabs.js'
import { CaseSessionsPanel } from './CaseSessionsPanel.jsx'
import { ClinicalInsightsPanel } from '../clinical/ClinicalInsightsPanel.jsx'
import { CaseGoalsPanel } from '../case-profile/sections/CaseGoalsPanel.jsx'
import { CaseStrategiesPanel } from '../case-profile/sections/CaseStrategiesPanel.jsx'
import { EvidenceDrivePanel } from '../case-profile/sections/EvidenceDrivePanel.jsx'
import { TherapistCaseOverviewDashboard } from '../clinical/therapist/TherapistCaseOverviewDashboard.jsx'
import './my-cases.css'

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
  const [caseRow, setCaseRow] = useState(null)
  const [scheduleItems, setScheduleItems] = useState([])
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
      const today = new Date()
      const from = today.toISOString().slice(0, 10)
      const toDate = new Date(today)
      toDate.setDate(toDate.getDate() + 90)
      const to = toDate.toISOString().slice(0, 10)

      const [c, upcoming, slots, profile, statusReqs, quality] = await Promise.all([
        apiFetch(`/api/v1/cases/${caseId}`),
        apiFetch('/api/v1/sessions/upcoming?days=90').catch(() => []),
        apiFetch(`/api/v1/slots?from_date=${from}&to_date=${to}`).catch(() => []),
        apiFetch(`/api/v1/cases/${caseId}/clinical-profile`).catch(() => null),
        apiFetch(`/api/v1/cases/${caseId}/status-requests`).catch(() => ({ pending: null, history: [] })),
        apiFetch(`/api/v1/cases/${caseId}/clinical-quality-summary`).catch(() => null),
      ])
      setCaseRow(c)
      setClinicalProfile(profile)
      setStatusPending(statusReqs?.pending || null)
      setStatusHistory(statusReqs?.history || [])
      setQualitySummary(quality)
      const upcomingList = Array.isArray(upcoming) ? upcoming : unwrapList(upcoming)
      const slotList = unwrapList(slots)
      setScheduleItems(
        mergeUpcomingSchedule({ sessions: upcomingList, slots: slotList }).filter((i) => i.caseId === Number(caseId)),
      )
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
    const next = new URLSearchParams(searchParams)
    next.set('tab', id)
    if (id !== 'reports') next.delete('section')
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

  const addr = caseRow.service_address?.formatted
  const childLabel = `${caseRow.child_name} (${caseRow.case_code})`
  const focusLine = caseServiceLine(caseRow.service_type, caseRow.product_module)

  return (
    <>
      <CaseProfileShell
        caseCode={caseRow.case_code}
        childName={caseRow.child_name}
        status={caseRow.status}
        serviceType={focusLine}
        onRequestChange={() => { setStatusMsg(''); setStatusModalOpen(true) }}
        supportHref={therapistTicketsUrl({ topic: 'CASE_MANAGER', caseId, openForm: true })}
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
            scheduleItems={scheduleItems}
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

        {tab === 'goals' ? <CaseGoalsPanel caseId={caseId} variant="therapist" /> : null}
        {tab === 'strategies' ? <CaseStrategiesPanel caseId={caseId} variant="therapist" /> : null}

        {tab === 'logs' ? (
          <CaseSessionsPanel
            caseId={Number(caseId)}
            caseCode={caseRow.case_code}
            childName={caseRow.child_name}
            childLabel={childLabel}
            scheduleItems={scheduleItems}
            onScheduleChange={load}
          />
        ) : null}

        {tab === 'insights' ? (
          <ClinicalInsightsPanel caseId={caseId} variant="therapist" />
        ) : null}

        {tab === 'documents' ? (
          <EvidenceDrivePanel caseId={Number(caseId)} variant="therapist" />
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
