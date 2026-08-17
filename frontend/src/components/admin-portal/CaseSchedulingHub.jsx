import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { TherapistCalendar } from '../scheduling/TherapistCalendar.jsx'
import { SlotDetailSheet } from '../scheduling/SlotDetailSheet.jsx'
import { ScheduleWeekdayPicker } from '../scheduling/ScheduleWeekdayPicker.jsx'
import { ONGOING_MATERIALIZE_WEEKS } from '../scheduling/scheduleTemplateUtils.js'
import { AdminTherapistPicker } from './AdminTherapistPicker.jsx'
import {
  FlagOutgoingTherapistCheckbox,
  ReassignmentBillingConfirm,
  isReassignmentReasonValid,
} from './ReassignmentBillingConfirm.jsx'
import { CaseBillingForm } from './CaseBillingForm.jsx'
import { billingSummary } from '../invoices/invoiceUtils.js'
import { filterUpcomingSessions, formatSessionWhen } from '../../lib/sessionDisplay.js'
import { formatDisplayDateTime } from '../../lib/datetime.js'
import { mapSlotToCalendarEvent } from '../../lib/googleCalendar.js'
import { BookingSuccessSheet } from '../shared/BookingSuccessSheet.jsx'
import { CaseDayTypeSection } from './CaseDayTypeSection.jsx'
import { TransitionTherapistSection } from './TransitionTherapistSection.jsx'
import './admin-scheduling-hub.css'

function addDaysIso(iso, days) {
  const d = new Date(iso + 'T12:00:00')
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

// ─── Section 1: Therapist Assignment ─────────────────────────────────────────

function TherapistAssignSection({
  caseItem,
  assignments,
  activeTransition,
  canAssign,
  readOnly,
  onAssigned,
}) {
  const activeAssignments = (assignments || []).filter((a) => a.status === 'ACTIVE')
  const primaryAssignment = activeTransition
    ? activeAssignments.find((a) => a.therapist_user_id === activeTransition.outgoing_therapist_user_id)
      || activeAssignments[0]
      || null
    : activeAssignments[0] || null
  const assignedTherapistId = primaryAssignment ? String(primaryAssignment.therapist_user_id) : ''
  const transitionBlocked = Boolean(activeTransition)

  const [selectedId, setSelectedId] = useState(assignedTherapistId)
  const [startDate, setStartDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [reason, setReason] = useState('')
  const [flagOutgoingTherapist, setFlagOutgoingTherapist] = useState(false)
  const [billingReady, setBillingReady] = useState(false)
  const [billingPayload, setBillingPayload] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  // Sync if assignments prop changes (e.g. after parent reload / reopen with no active therapist)
  useEffect(() => {
    setSelectedId(assignedTherapistId)
  }, [assignedTherapistId])

  useEffect(() => {
    setBillingReady(false)
    setBillingPayload(null)
  }, [selectedId, assignedTherapistId])

  const isChanging = selectedId && selectedId !== assignedTherapistId
  const isNew = !primaryAssignment && selectedId

  async function handleSave() {
    if (!selectedId || !caseItem?.id) return
    if (transitionBlocked) {
      setError('A transition handover is in progress. Wait for it to finish before changing the therapist.')
      return
    }
    if (isChanging && !isReassignmentReasonValid(reason)) {
      setError('Please add a reason for this reassignment (at least 5 characters).')
      return
    }
    if (isChanging && !billingReady) {
      setError('Update billing for the new therapist before confirming reassignment.')
      return
    }
    setBusy(true)
    setError('')
    setSuccess('')
    try {
      const body = {
        therapist_user_id: Number(selectedId),
        start_date: startDate,
      }
      if (isChanging) {
        body.reason_for_change = reason.trim()
        body.flag_outgoing_therapist = flagOutgoingTherapist
        if (billingPayload) {
          body.billing_update = billingPayload
        }
      }
      await apiFetch(`/api/v1/cases/${caseItem.id}/assignments`, {
        method: 'POST',
        body: JSON.stringify(body),
      })
      setSuccess(isNew ? 'Therapist assigned.' : 'Therapist reassigned.')
      setReason('')
      setFlagOutgoingTherapist(false)
      setBillingReady(false)
      setBillingPayload(null)
      onAssigned?.()
    } catch (err) {
      setError(err.message || 'Could not save assignment')
    } finally {
      setBusy(false)
    }
  }

  return (
    <article className="admin-scheduling-hub__therapist card">
      <h3>Therapist assignment</h3>

      {primaryAssignment ? (
        <p className="admin-scheduling-hub__assigned">
          Currently assigned:{' '}
          <strong>{primaryAssignment.therapist_name || `Therapist #${primaryAssignment.therapist_user_id}`}</strong>
          {primaryAssignment.start_date ? ` · since ${primaryAssignment.start_date}` : ''}
        </p>
      ) : (
        <p className="admin-scheduling-hub__billing-note">
          No active therapist assignment. Select a therapist below to assign.
        </p>
      )}

      {activeTransition ? (
        <p className="admin-scheduling-hub__billing-note" style={{ marginTop: 8 }}>
          Handover with{' '}
          <strong>{activeTransition.incoming_therapist_name || `Therapist #${activeTransition.incoming_therapist_user_id}`}</strong>
          {' '}on {(activeTransition.transition_dates || []).join(', ')}. Both therapists submit logs during this period.
        </p>
      ) : null}

      {transitionBlocked ? (
        <p className="admin-muted" style={{ fontSize: '0.85rem', marginTop: 8 }}>
          Change therapist is paused while the transition handover is active.
        </p>
      ) : null}

      {!canAssign ? (
        <p className="admin-muted" style={{ fontSize: '0.85rem' }}>
          You don't have permission to change therapist assignments.
        </p>
      ) : !transitionBlocked ? (
        <div className="admin-form-grid" style={{ maxWidth: 480, marginTop: 12 }}>
          <label className="admin-label" style={{ gridColumn: '1 / -1' }}>
            {primaryAssignment ? 'Change therapist' : 'Assign therapist'}
            <AdminTherapistPicker
              mode="allotment"
              productModule={caseItem.product_module}
              caseId={caseItem.id}
              value={selectedId}
              onChange={setSelectedId}
              disabled={readOnly}
            />
          </label>

          {(isChanging || isNew) && (
            <>
              <label className="admin-label">
                Start date for new assignment
                <input
                  type="date"
                  className="admin-input"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  disabled={readOnly}
                />
              </label>
              {isChanging ? (
                <>
                  <label className="admin-label admin-label--stacked" style={{ gridColumn: '1 / -1' }}>
                    <span className="admin-label__caption">
                      Reason for change <span className="admin-label__required" aria-hidden="true">*</span>
                    </span>
                    <input
                      type="text"
                      className="admin-input"
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      placeholder="e.g. Caseload rebalance, therapist resigned"
                      disabled={readOnly}
                    />
                  </label>
                  <FlagOutgoingTherapistCheckbox
                    checked={flagOutgoingTherapist}
                    onChange={setFlagOutgoingTherapist}
                    disabled={readOnly}
                  />
                  <ReassignmentBillingConfirm
                    caseItem={caseItem}
                    billingReady={billingReady}
                    onBillingReady={(payload) => {
                      setBillingPayload(payload)
                      setBillingReady(true)
                      setError('')
                    }}
                    onBillingDraftChange={() => {
                      setBillingReady(false)
                      setBillingPayload(null)
                    }}
                    readOnly={readOnly}
                  />
                </>
              ) : null}
            </>
          )}

          {error ? <p className="admin-alert admin-alert--error" style={{ gridColumn: '1 / -1' }}>{error}</p> : null}
          {success ? <p className="admin-alert admin-alert--success" style={{ gridColumn: '1 / -1' }}>{success}</p> : null}

          {(isChanging || isNew) && !readOnly ? (
            <div style={{ gridColumn: '1 / -1' }}>
              {isChanging ? (
                <>
                  {billingReady ? (
                    <>
                      <p className="reassignment-billing-confirm__step" style={{ marginBottom: 10 }}>
                        Step 2 of 2 — Confirm reassignment
                      </p>
                      <button
                        type="button"
                        className="admin-btn admin-btn--primary"
                        onClick={handleSave}
                        disabled={busy || !selectedId || !isReassignmentReasonValid(reason) || !billingReady}
                      >
                        {busy ? 'Saving…' : 'Confirm reassignment'}
                      </button>
                    </>
                  ) : null}
                  <button
                    type="button"
                    className="admin-btn admin-btn--ghost"
                    style={{ marginLeft: billingReady ? 8 : 0 }}
                    onClick={() => setSelectedId(assignedTherapistId)}
                  >
                    Cancel
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  className="admin-btn admin-btn--primary"
                  onClick={handleSave}
                  disabled={busy || !selectedId}
                >
                  {busy ? 'Saving…' : 'Assign therapist'}
                </button>
              )}
            </div>
          ) : null}
        </div>
      ) : null}

      <TransitionTherapistSection
        caseItem={caseItem}
        activeTransition={activeTransition}
        canAssign={canAssign}
        readOnly={readOnly}
        primaryTherapistId={assignedTherapistId}
        onChanged={onAssigned}
      />

      {/* Assignment history */}
      {assignments?.length > 0 ? (
        <details style={{ marginTop: 16 }}>
          <summary className="admin-muted" style={{ cursor: 'pointer', fontSize: '0.825rem' }}>
            Assignment history ({assignments.length})
          </summary>
          <ul className="admin-queue" style={{ marginTop: 8 }}>
            {assignments.map((a) => (
              <li key={a.id} className="admin-queue__item">
                <div>
                  <p className="admin-queue__title">{a.therapist_name || `Therapist #${a.therapist_user_id}`}</p>
                  <p className="admin-queue__meta">
                    {a.start_date}{a.end_date ? ` → ${a.end_date}` : ''}
                    {a.reason_for_change ? ` · ${a.reason_for_change}` : ''}
                  </p>
                </div>
                <span className={`admin-status-pill admin-status-pill--${String(a.status).toLowerCase()}`}>
                  {a.status}
                </span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </article>
  )
}

// ─── Section 2: Inline Billing Review ────────────────────────────────────────

function BillingReviewSection({ caseItem, canEdit, onSaved }) {
  const [expanded, setExpanded] = useState(false)
  const [localCase, setLocalCase] = useState(caseItem)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    setLocalCase(caseItem)
  }, [caseItem])

  const hint = useMemo(
    () =>
      billingSummary({
        billing_type: localCase?.billing_type,
        client_rate_per_session_inr: localCase?.client_rate_per_session_inr,
        package_session_count: localCase?.package_session_count,
        package_amount_inr: localCase?.package_amount_inr,
        compensation_mode: localCase?.compensation_mode,
        pay_share_amount_inr: localCase?.pay_share_amount_inr,
        therapist_fixed_pay_inr: localCase?.therapist_fixed_pay_inr,
      }),
    [localCase],
  )

  async function handleSave(payload) {
    const updated = await apiFetch(`/api/v1/cases/${caseItem.id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
    setLocalCase(updated)
    setSaved(true)
    setExpanded(false)
    onSaved?.(updated)
    setTimeout(() => setSaved(false), 3000)
  }

  return (
    <article className="admin-scheduling-hub__billing card">
      <div className="admin-scheduling-hub__billing-head">
        <div>
          <h3>Billing</h3>
          <p className="admin-muted">
            {localCase?.service_type || 'Service'} · {localCase?.product_module?.replace(/_/g, ' ') || '—'}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {canEdit ? (
            <button
              type="button"
              className="admin-btn admin-btn--secondary admin-btn--sm"
              onClick={() => setExpanded((v) => !v)}
            >
              {expanded ? 'Close' : 'Edit billing'}
            </button>
          ) : null}
          <Link
            to={`/admin/cases/${caseItem?.id}?tab=billing`}
            className="admin-btn admin-btn--ghost admin-btn--sm"
          >
            Full billing tab →
          </Link>
        </div>
      </div>

      {hint ? (
        <p className="admin-scheduling-hub__billing-summary">{hint}</p>
      ) : (
        <p className="admin-scheduling-hub__billing-note">
          No billing configured. Use "Edit billing" or go to the Billing tab to set rates.
        </p>
      )}

      {saved ? <p className="admin-alert admin-alert--success" style={{ marginTop: 8 }}>Billing saved.</p> : null}

      {expanded && canEdit ? (
        <div style={{ marginTop: 16, borderTop: '1px solid var(--border, #e2e8f0)', paddingTop: 16 }}>
          <CaseBillingForm
            caseItem={localCase}
            onSave={handleSave}
            readOnly={false}
          />
        </div>
      ) : null}
    </article>
  )
}

// ─── Main Component ───────────────────────────────────────────────────────────

export function CaseSchedulingHub({
  caseItem,
  assignments,
  onDone,
  onSessionsChange,
  onCaseUpdated,
  canBook = true,
  canAssign = false,
  canEditBilling = false,
}) {
  const { isViewOnly } = useAuth()
  const readOnly = !canBook || isViewOnly

  const [activeTransition, setActiveTransition] = useState(null)
  const activeAssignments = (assignments || []).filter((a) => a.status === 'ACTIVE')
  const primaryAssignment = activeTransition
    ? activeAssignments.find((a) => a.therapist_user_id === activeTransition.outgoing_therapist_user_id)
      || activeAssignments[0]
      || null
    : activeAssignments[0] || null
  const assignedTherapistId = primaryAssignment ? String(primaryAssignment.therapist_user_id) : ''

  // Schedule state
  const [therapistId, setTherapistId] = useState('')
  const [showOneOff, setShowOneOff] = useState(false)
  const [upcoming, setUpcoming] = useState([])
  const [loadingUpcoming, setLoadingUpcoming] = useState(true)
  const [detailSlot, setDetailSlot] = useState(null)
  const [calendarRefresh, setCalendarRefresh] = useState(0)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [bookingSuccess, setBookingSuccess] = useState(null)
  const [productRules, setProductRules] = useState([])

  const [fromDate, setFromDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [toDate, setToDate] = useState(() => addDaysIso(new Date().toISOString().slice(0, 10), 14))
  const [availSlots, setAvailSlots] = useState([])
  const [booking, setBooking] = useState(false)
  const [adminComment, setAdminComment] = useState('')
  const [forceBook, setForceBook] = useState(false)

  const [weekdays, setWeekdays] = useState(['mon', 'wed', 'fri'])
  const [startTime, setStartTime] = useState('16:00')
  const [endTime, setEndTime] = useState('17:00')
  const [rangeMode, setRangeMode] = useState('weeks')
  const [rangeWeeks, setRangeWeeks] = useState(8)
  const [recurStart, setRecurStart] = useState('')
  const [recurPreview, setRecurPreview] = useState(null)

  const selectedRule = useMemo(() => {
    if (!caseItem?.product_billing_rule_id) return null
    return productRules.find((r) => r.id === caseItem.product_billing_rule_id) || null
  }, [caseItem, productRules])

  const recurRange = useMemo(() => {
    const start = recurStart || new Date().toISOString().slice(0, 10)
    if (rangeMode === 'ongoing') {
      return { start, end: addDaysIso(start, ONGOING_MATERIALIZE_WEEKS * 7) }
    }
    if (rangeMode === 'weeks') {
      return { start, end: addDaysIso(start, Math.max(1, rangeWeeks) * 7) }
    }
    return { start, end: start }
  }, [recurStart, rangeMode, rangeWeeks])

  const loadUpcoming = useCallback(() => {
    if (!caseItem?.id) return
    setLoadingUpcoming(true)
    apiFetch(`/api/v1/sessions?case_id=${caseItem.id}&page_size=50`)
      .then((d) => {
        const rows = unwrapList(d)
        const list = filterUpcomingSessions(rows).slice(0, 15)
        setUpcoming(list)
        onSessionsChange?.(list)
      })
      .catch(() => setUpcoming([]))
      .finally(() => setLoadingUpcoming(false))
  }, [caseItem?.id, onSessionsChange])

  useEffect(() => {
    loadUpcoming()
  }, [loadUpcoming, onDone, calendarRefresh])

  useEffect(() => {
    if (!caseItem?.id) return
    apiFetch(`/api/v1/cases/${caseItem.id}/transitions/active`)
      .then((row) => setActiveTransition(row || null))
      .catch(() => setActiveTransition(null))
  }, [caseItem?.id, onDone])

  useEffect(() => {
    if (assignedTherapistId) setTherapistId(assignedTherapistId)
    const today = new Date().toISOString().slice(0, 10)
    setRecurStart(today)
  }, [assignedTherapistId, primaryAssignment?.id])

  useEffect(() => {
    if (!caseItem?.product_module) return
    apiFetch(`/api/v1/admin/ledger-billing/product-rules?product_module=${caseItem.product_module}`)
      .then(setProductRules)
      .catch(() => setProductRules([]))
  }, [caseItem?.product_module])

  useEffect(() => {
    if (!therapistId || !showOneOff) {
      setAvailSlots([])
      return
    }
    apiFetch(`/api/v1/booking/availability?therapist_id=${therapistId}&from_date=${fromDate}&to_date=${toDate}`)
      .then(setAvailSlots)
      .catch(() => setAvailSlots([]))
  }, [therapistId, fromDate, toDate, showOneOff])

  async function bookSingleSlot(slot) {
    if (readOnly) return
    setBooking(true)
    setError('')
    setSuccess('')
    setBookingSuccess(null)
    try {
      await apiFetch(`/api/v1/scheduling/slots/${slot.id}/book`, {
        method: 'POST',
        body: JSON.stringify({
          case_id: caseItem.id,
          require_therapist_approval: forceBook,
          admin_request_comment: adminComment.trim() || null,
          force_unavailable: forceBook,
        }),
      })
      setBookingSuccess({
        event: mapSlotToCalendarEvent(
          { ...slot, child_name: caseItem.child_name, case_code: caseItem.case_code },
          { deepLinkPath: `/admin/cases/${caseItem.id}?tab=scheduling` },
        ),
        detailLines: [
          caseItem.child_name ? `Client: ${caseItem.child_name}` : null,
          caseItem.case_code ? `Case: ${caseItem.case_code}` : null,
        ].filter(Boolean),
      })
      setSuccess(forceBook ? 'Booked — pending therapist confirmation.' : 'Session booked.')
      setCalendarRefresh((k) => k + 1)
      onDone?.()
      loadUpcoming()
    } catch (err) {
      setError(err.message || 'Booking failed')
    } finally {
      setBooking(false)
    }
  }

  async function previewRecurring() {
    setError('')
    setRecurPreview(null)
    if (!therapistId) {
      setError('Assign or confirm a therapist above first.')
      return
    }
    try {
      const res = await apiFetch('/api/v1/scheduling/assign-recurring/preview', {
        method: 'POST',
        body: JSON.stringify({
          case_id: caseItem.id,
          therapist_user_id: Number(therapistId),
          weekdays,
          start_time: startTime,
          end_time: endTime,
          start_date: recurRange.start,
          end_date: recurRange.end,
        }),
      })
      setRecurPreview(res)
    } catch (err) {
      setError(err.message || 'Preview failed')
    }
  }

  async function confirmRecurring() {
    if (readOnly) return
    setBooking(true)
    setError('')
    try {
      const res = await apiFetch('/api/v1/scheduling/assign-recurring', {
        method: 'POST',
        body: JSON.stringify({
          case_id: caseItem.id,
          therapist_user_id: Number(therapistId),
          weekdays,
          start_time: startTime,
          end_time: endTime,
          start_date: recurRange.start,
          end_date: recurRange.end,
        }),
      })
      setSuccess(`Recurring schedule created (${res.booked_slot_count || 0} sessions).`)
      setRecurPreview(null)
      setCalendarRefresh((k) => k + 1)
      onDone?.()
      loadUpcoming()
    } catch (err) {
      setError(err.message || 'Could not assign schedule')
    } finally {
      setBooking(false)
    }
  }

  const tid = therapistId ? Number(therapistId) : null

  return (
    <section className="admin-layout admin-layout--stack admin-scheduling-hub">
      {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}
      {success ? <p className="admin-alert admin-alert--success">{success}</p> : null}

      {/* ── Section 1: Therapist Assignment ── */}
      <TherapistAssignSection
        caseItem={caseItem}
        assignments={assignments}
        activeTransition={activeTransition}
        canAssign={canAssign}
        readOnly={isViewOnly}
        onAssigned={() => {
          if (caseItem?.id) {
            apiFetch(`/api/v1/cases/${caseItem.id}/transitions/active`)
              .then((row) => setActiveTransition(row || null))
              .catch(() => setActiveTransition(null))
          }
          onDone?.()
        }}
      />

      <CaseDayTypeSection
        caseItem={caseItem}
        readOnly={isViewOnly || Boolean(activeTransition)}
        canEdit={canEditBilling}
        onCaseUpdated={onCaseUpdated}
      />

      {/* ── Section 2: Billing Review ── */}
      <BillingReviewSection
        caseItem={caseItem}
        canEdit={canEditBilling && !activeTransition}
        onSaved={(updated) => onCaseUpdated?.(updated)}
      />

      {/* ── Section 3: Book sessions (recurring) ── */}
      <article className="admin-scheduling-hub__book card">
        <h3>Book sessions</h3>
        <p className="admin-muted" style={{ marginBottom: 16 }}>
          Set up a weekly recurring schedule. Use one-off booking below when you need a single extra session.
        </p>

        {activeTransition ? (
          <p className="admin-scheduling-hub__billing-note">
            Scheduling changes are paused during the therapist handover. Existing sessions and transition logs remain available.
          </p>
        ) : !therapistId ? (
          <p className="admin-scheduling-hub__billing-note">
            Assign or confirm a therapist above to continue scheduling.
          </p>
        ) : (
          <>
            <div className="admin-scheduling-hub__recurring">
              <ScheduleWeekdayPicker value={weekdays} onChange={setWeekdays} label="Repeat on" />
              <div className="admin-form-grid" style={{ maxWidth: 420, marginTop: 12 }}>
                <label>
                  Start time
                  <input type="time" className="admin-input" value={startTime} onChange={(e) => setStartTime(e.target.value)} disabled={readOnly} />
                </label>
                <label>
                  End time
                  <input type="time" className="admin-input" value={endTime} onChange={(e) => setEndTime(e.target.value)} disabled={readOnly} />
                </label>
              </div>

              <div className="admin-scheduling-hub__range">
                <p className="admin-scheduling-hub__range-title">How long</p>
                {[
                  { id: 'weeks', label: 'For N weeks from start date' },
                  { id: 'ongoing', label: `Ongoing (${ONGOING_MATERIALIZE_WEEKS} weeks ahead, extend by re-running)` },
                  { id: 'once', label: 'Single week (start date only)' },
                ].map((m) => (
                  <label key={m.id} className="admin-scheduling-hub__range-option">
                    <input
                      type="radio"
                      name="rangeMode"
                      checked={rangeMode === m.id}
                      onChange={() => setRangeMode(m.id)}
                      disabled={readOnly}
                    />
                    {m.label}
                  </label>
                ))}
                {rangeMode === 'weeks' ? (
                  <label className="admin-label" style={{ marginTop: 8 }}>
                    Number of weeks
                    <input
                      type="number"
                      className="admin-input"
                      min={1}
                      max={52}
                      value={rangeWeeks}
                      onChange={(e) => setRangeWeeks(Number(e.target.value))}
                      disabled={readOnly}
                    />
                  </label>
                ) : null}
                <label className="admin-label" style={{ marginTop: 8 }}>
                  Start date
                  <input
                    type="date"
                    className="admin-input"
                    value={recurStart}
                    onChange={(e) => setRecurStart(e.target.value)}
                    disabled={readOnly}
                  />
                </label>
                <p className="admin-muted" style={{ fontSize: '0.75rem', marginTop: 6 }}>
                  Scheduling through {recurRange.end}
                  {rangeMode === 'ongoing' ? ` (${ONGOING_MATERIALIZE_WEEKS} weeks materialized)` : ''}
                </p>
              </div>

              {selectedRule ? (
                <p className="admin-muted" style={{ fontSize: '0.8rem', marginTop: 8 }}>
                  Ledger rule: {selectedRule.productName} ({selectedRule.billingModel})
                </p>
              ) : null}

              {!readOnly ? (
                <div className="admin-btn-group" style={{ marginTop: 12 }}>
                  <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" onClick={previewRecurring}>
                    Preview conflicts
                  </button>
                  <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" disabled={booking} onClick={confirmRecurring}>
                    {booking ? 'Booking…' : 'Create recurring schedule'}
                  </button>
                </div>
              ) : null}

              {recurPreview?.conflicts?.length ? (
                <div className="admin-alert" style={{ marginTop: 12, color: '#b45309' }}>
                  <strong>{recurPreview.conflicts.length} conflict(s):</strong>
                  <ul style={{ margin: '8px 0 0', paddingLeft: 18 }}>
                    {recurPreview.conflicts.slice(0, 8).map((c, i) => (
                      <li key={i}>
                        {formatDisplayDateTime(c.date, c.start)} — {c.status}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : recurPreview ? (
                <p style={{ marginTop: 12, fontSize: '0.85rem', color: '#059669' }}>
                  ~{recurPreview.planned_count} sessions can be booked.
                </p>
              ) : null}
            </div>

            {/* ── One-off booking ── */}
            <div className="admin-scheduling-hub__oneoff">
              <button
                type="button"
                className="admin-scheduling-hub__oneoff-toggle"
                onClick={() => setShowOneOff((v) => !v)}
              >
                {showOneOff ? '− Hide one-off session' : '+ Book one additional session'}
              </button>
              {showOneOff ? (
                <div className="admin-scheduling-hub__oneoff-body">
                  <div className="admin-form-grid" style={{ maxWidth: 420 }}>
                    <label>
                      From
                      <input type="date" className="admin-input" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
                    </label>
                    <label>
                      To
                      <input type="date" className="admin-input" value={toDate} onChange={(e) => setToDate(e.target.value)} />
                    </label>
                  </div>
                  {!readOnly ? (
                    <>
                      <label className="admin-scheduling-hub__checkbox">
                        <input type="checkbox" checked={forceBook} onChange={(e) => setForceBook(e.target.checked)} />
                        Request therapist approval if slot is busy or not open
                      </label>
                      {forceBook ? (
                        <label className="admin-label">
                          Message to therapist
                          <input
                            className="admin-input"
                            value={adminComment}
                            onChange={(e) => setAdminComment(e.target.value)}
                            placeholder="Why this booking is needed…"
                          />
                        </label>
                      ) : null}
                    </>
                  ) : null}
                  {tid ? (
                    <>
                      <div className="admin-scheduling-hub__calendar-wrap">
                        <TherapistCalendar
                          therapistId={tid}
                          caseId={caseItem.id}
                          mode="therapist"
                          refreshKey={calendarRefresh}
                          onSlotClick={(slot) => setDetailSlot(slot)}
                          selectedSlotId={detailSlot?.id}
                        />
                      </div>
                      {availSlots.length > 0 ? (
                        <ul className="admin-queue" style={{ marginTop: 12 }}>
                          {availSlots.slice(0, 12).map((s) => (
                            <li key={s.id} className="admin-queue__item">
                              <div>
                                <p className="admin-queue__title">
                                  {formatDisplayDateTime(s.slot_date, s.start_time)}
                                </p>
                              </div>
                              {!readOnly ? (
                                <button
                                  type="button"
                                  className="admin-btn admin-btn--primary admin-btn--sm"
                                  disabled={booking}
                                  onClick={() => bookSingleSlot(s)}
                                >
                                  Book
                                </button>
                              ) : null}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="admin-muted" style={{ marginTop: 12, fontSize: '0.85rem' }}>
                          Click an open slot on the calendar, or enable therapist approval to request a busy slot.
                        </p>
                      )}
                    </>
                  ) : null}
                </div>
              ) : null}
            </div>
          </>
        )}
      </article>

      {/* ── Section 4: Upcoming sessions ── */}
      <article className="admin-scheduling-hub__upcoming card">
        <h3>Upcoming sessions</h3>
        {loadingUpcoming ? (
          <p className="admin-muted">Loading…</p>
        ) : upcoming.length === 0 ? (
          <p className="admin-muted">No upcoming sessions.</p>
        ) : (
          <ul className="admin-queue">
            {upcoming.map((s) => (
              <li key={s.id} className="admin-queue__item">
                <div>
                  <p className="admin-queue__title">{formatSessionWhen(s)}</p>
                  <p className="admin-queue__meta">{s.status}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </article>

      <SlotDetailSheet
        open={!!detailSlot}
        slot={detailSlot}
        onClose={() => setDetailSlot(null)}
        onChanged={() => {
          setDetailSlot(null)
          setCalendarRefresh((k) => k + 1)
          onDone?.()
          loadUpcoming()
        }}
      />

      <BookingSuccessSheet
        open={!!bookingSuccess}
        title="Session booked"
        event={bookingSuccess?.event}
        detailLines={bookingSuccess?.detailLines}
        onClose={() => setBookingSuccess(null)}
      />
    </section>
  )
}
