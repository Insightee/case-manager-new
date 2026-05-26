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
import { billingSummary } from '../invoices/invoiceUtils.js'
import './admin-scheduling-hub.css'

function addDaysIso(iso, days) {
  const d = new Date(iso + 'T12:00:00')
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

export function CaseSchedulingHub({ caseItem, assignments, onDone, canBook = true }) {
  const { isViewOnly } = useAuth()
  const readOnly = !canBook || isViewOnly
  const activeAssignment = assignments?.find((a) => a.status === 'ACTIVE') || assignments?.[0]
  const assignedTherapistId = activeAssignment ? String(activeAssignment.therapist_user_id) : ''

  const [therapistId, setTherapistId] = useState('')
  const [pendingReassign, setPendingReassign] = useState(null)
  const [reassignReason, setReassignReason] = useState('Reassigned from scheduling')
  const [reassignBusy, setReassignBusy] = useState(false)
  const [showOneOff, setShowOneOff] = useState(false)

  const [upcoming, setUpcoming] = useState([])
  const [loadingUpcoming, setLoadingUpcoming] = useState(true)
  const [detailSlot, setDetailSlot] = useState(null)
  const [calendarRefresh, setCalendarRefresh] = useState(0)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
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
  const [recurEnd, setRecurEnd] = useState('')
  const [recurPreview, setRecurPreview] = useState(null)

  const billingHint = useMemo(() => {
    if (!caseItem) return ''
    return billingSummary({
      billing_type: caseItem.billing_type,
      client_rate_per_session_inr: caseItem.client_rate_per_session_inr,
      package_session_count: caseItem.package_session_count,
      package_amount_inr: caseItem.package_amount_inr,
      compensation_mode: caseItem.compensation_mode,
      pay_share_pct: caseItem.pay_share_pct,
      therapist_fixed_pay_inr: caseItem.therapist_fixed_pay_inr,
    })
  }, [caseItem])

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
        const now = new Date()
        setUpcoming(
          rows
            .filter((s) => s.scheduled_at && new Date(s.scheduled_at) >= now)
            .sort((a, b) => new Date(a.scheduled_at) - new Date(b.scheduled_at))
            .slice(0, 15),
        )
      })
      .catch(() => setUpcoming([]))
      .finally(() => setLoadingUpcoming(false))
  }, [caseItem?.id])

  useEffect(() => {
    loadUpcoming()
  }, [loadUpcoming, onDone])

  useEffect(() => {
    if (assignedTherapistId) setTherapistId(assignedTherapistId)
    const today = new Date().toISOString().slice(0, 10)
    setRecurStart(today)
    setRecurEnd(addDaysIso(today, 56))
  }, [assignedTherapistId, activeAssignment?.id])

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

  function handleTherapistChange(nextId) {
    if (
      assignedTherapistId &&
      nextId &&
      nextId !== assignedTherapistId
    ) {
      setPendingReassign(nextId)
      return
    }
    setTherapistId(nextId)
    setPendingReassign(null)
  }

  async function confirmReassign() {
    if (!pendingReassign || !caseItem?.id) return
    setReassignBusy(true)
    setError('')
    try {
      await apiFetch(`/api/v1/cases/${caseItem.id}/assignments`, {
        method: 'POST',
        body: JSON.stringify({
          therapist_user_id: Number(pendingReassign),
          start_date: new Date().toISOString().slice(0, 10),
          reason_for_change: reassignReason.trim() || 'Reassigned from scheduling',
        }),
      })
      setTherapistId(pendingReassign)
      setPendingReassign(null)
      setSuccess('Therapist reassigned for this case.')
      onDone?.()
    } catch (err) {
      setError(err.message || 'Could not reassign therapist')
    } finally {
      setReassignBusy(false)
    }
  }

  function cancelReassign() {
    setPendingReassign(null)
    setTherapistId(assignedTherapistId)
  }

  async function bookSingleSlot(slotId) {
    if (readOnly) return
    setBooking(true)
    setError('')
    setSuccess('')
    try {
      await apiFetch(`/api/v1/scheduling/slots/${slotId}/book`, {
        method: 'POST',
        body: JSON.stringify({
          case_id: caseItem.id,
          require_therapist_approval: forceBook,
          admin_request_comment: adminComment.trim() || null,
          force_unavailable: forceBook,
        }),
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
      setError('Select or confirm a therapist first.')
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
  const moduleLabel = caseItem.product_module?.replace(/_/g, ' ') || '—'

  return (
    <section className="admin-layout admin-layout--stack admin-scheduling-hub">
      {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}
      {success ? <p className="admin-alert admin-alert--success">{success}</p> : null}

      <article className="admin-scheduling-hub__billing card">
        <div className="admin-scheduling-hub__billing-head">
          <div>
            <h3>Billing criteria</h3>
            <p className="admin-muted">
              {caseItem.service_type || 'Service'} · {moduleLabel}
            </p>
          </div>
          <Link to={`/admin/cases/${caseItem.id}?tab=billing`} className="admin-btn admin-btn--secondary admin-btn--sm">
            Edit billing
          </Link>
        </div>
        {billingHint ? <p className="admin-scheduling-hub__billing-summary">{billingHint}</p> : null}
        {selectedRule ? (
          <p className="admin-muted" style={{ fontSize: '0.8rem', marginTop: 8 }}>
            Ledger rule: {selectedRule.productName} ({selectedRule.billingModel})
          </p>
        ) : (
          <p className="admin-scheduling-hub__billing-note">
            Product billing rules are filtered by this case&apos;s module ({moduleLabel}). To use homecare or
            another line, set the case service category / product module on the Billing tab, then pick a matching
            rule. Configure global rules under Finance → Product billing rules.
          </p>
        )}
      </article>

      <article className="admin-scheduling-hub__therapist card">
        <h3>Therapist</h3>
        {activeAssignment ? (
          <p className="admin-scheduling-hub__assigned">
            Assigned: <strong>{activeAssignment.therapist_name || `Therapist #${activeAssignment.therapist_user_id}`}</strong>
            {activeAssignment.start_date ? ` · since ${activeAssignment.start_date}` : ''}
          </p>
        ) : (
          <p className="admin-scheduling-hub__billing-note">No active assignment — choose a therapist to book sessions.</p>
        )}

        {pendingReassign ? (
          <div className="admin-scheduling-hub__reassign">
            <p>
              <strong>Reassign case?</strong> Selecting a different therapist will end the current assignment and
              start a new one before you can book.
            </p>
            <label className="admin-label">
              Reason
              <input
                className="admin-input"
                value={reassignReason}
                onChange={(e) => setReassignReason(e.target.value)}
                placeholder="e.g. Caseload rebalance"
              />
            </label>
            <div className="admin-btn-group">
              <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" disabled={reassignBusy} onClick={confirmReassign}>
                {reassignBusy ? 'Reassigning…' : 'Confirm reassign'}
              </button>
              <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={cancelReassign}>
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <label className="admin-label">
            {activeAssignment ? 'Change therapist' : 'Assign therapist'}
            <AdminTherapistPicker
              mode="allotment"
              productModule={caseItem.product_module}
              caseId={caseItem.id}
              value={therapistId}
              onChange={handleTherapistChange}
              disabled={readOnly}
            />
          </label>
        )}
      </article>

      <article className="admin-scheduling-hub__book card">
        <h3>Book sessions</h3>
        <p className="admin-muted" style={{ marginBottom: 16 }}>
          Set up a weekly recurring schedule. Use one-off booking below when you need a single extra session.
        </p>

        {!therapistId ? (
          <p className="admin-scheduling-hub__billing-note">Assign or confirm a therapist above to continue.</p>
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
                        {c.date} {c.start} — {c.status}
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
                      <div style={{ marginTop: 16 }}>
                        <TherapistCalendar
                          therapistId={tid}
                          caseId={caseItem.id}
                          mode="therapist"
                          refreshKey={calendarRefresh}
                          showLeaveActions={false}
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
                                  {s.slot_date} {s.start_time}
                                </p>
                              </div>
                              {!readOnly ? (
                                <button
                                  type="button"
                                  className="admin-btn admin-btn--primary admin-btn--sm"
                                  disabled={booking}
                                  onClick={() => bookSingleSlot(s.id)}
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
                  <p className="admin-queue__title">{s.scheduled_at ? new Date(s.scheduled_at).toLocaleString() : 'Session'}</p>
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
    </section>
  )
}
