import { useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { AdminTherapistPicker } from './AdminTherapistPicker.jsx'
import { ReassignmentBillingConfirm } from './ReassignmentBillingConfirm.jsx'
import { TransitionDateCalendar } from './TransitionDateCalendar.jsx'
import { productRequiresDayType } from '../../lib/dayTypeLabels.js'

const TRANSITION_DAY_COUNT = 3

function defaultTransitionDates() {
  return []
}

function formatDates(dates) {
  return (dates || []).map((d) => String(d).slice(0, 10)).join(', ')
}

export function TransitionTherapistSection({
  caseItem,
  activeTransition,
  canAssign,
  readOnly,
  primaryTherapistId,
  onChanged,
}) {
  const [expanded, setExpanded] = useState(false)
  const [incomingId, setIncomingId] = useState('')
  const [transitionDates, setTransitionDates] = useState(defaultTransitionDates)
  const [billingReady, setBillingReady] = useState(false)
  const [billingPayload, setBillingPayload] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [editingDates, setEditingDates] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [cancellationReason, setCancellationReason] = useState('')

  const blocked = Boolean(activeTransition)
  const canStart = canAssign && !readOnly && primaryTherapistId && !blocked
  const dayTypeRequired = productRequiresDayType(caseItem?.product_module)
  const dayTypeMissing = dayTypeRequired && !caseItem?.day_type

  const statusLine = useMemo(() => {
    if (!activeTransition) return null
    const outgoing = activeTransition.outgoing_therapist_name || `Therapist #${activeTransition.outgoing_therapist_user_id}`
    const incoming = activeTransition.incoming_therapist_name || `Therapist #${activeTransition.incoming_therapist_user_id}`
    return `${outgoing} + ${incoming} · ${formatDates(activeTransition.transition_dates)} · ${activeTransition.status}`
  }, [activeTransition])

  function openTransitionForm() {
    if (dayTypeMissing) {
      setError('Choose the school day type before adding a transition therapist.')
      document.getElementById('case-school-day-type')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      return
    }
    setError('')
    setSuccess('')
    setExpanded(true)
  }

  function resetTransitionDraft() {
    setIncomingId('')
    setTransitionDates(defaultTransitionDates())
    setBillingReady(false)
    setBillingPayload(null)
  }

  function closeTransitionForm() {
    setExpanded(false)
    resetTransitionDraft()
    setError('')
  }

  async function handleSubmit() {
    if (!caseItem?.id || !incomingId) return
    if (dayTypeMissing) {
      setError('Choose the school day type before starting the transition.')
      return
    }
    if (String(incomingId) === String(primaryTherapistId)) {
      setError('The transition therapist must be different from the current therapist.')
      return
    }
    if (!billingReady || !billingPayload) {
      setError('Enter billing for the incoming therapist before starting the transition.')
      return
    }
    const uniqueDates = new Set(transitionDates)
    if (transitionDates.length !== TRANSITION_DAY_COUNT || uniqueDates.size !== TRANSITION_DAY_COUNT) {
      setError('Please choose three different transition dates.')
      return
    }
    setBusy(true)
    setError('')
    setSuccess('')
    try {
      await apiFetch(`/api/v1/cases/${caseItem.id}/transitions`, {
        method: 'POST',
        body: JSON.stringify({
          incoming_therapist_user_id: Number(incomingId),
          transition_dates: transitionDates,
          billing_update: billingPayload,
        }),
      })
      setSuccess('Transition handover started. Both therapists can submit logs on the selected dates.')
      setExpanded(false)
      resetTransitionDraft()
      onChanged?.()
    } catch (err) {
      setError(err.message || 'Could not start transition')
    } finally {
      setBusy(false)
    }
  }

  function beginDateEdit() {
    setTransitionDates([...(activeTransition?.transition_dates || [])].sort())
    setEditingDates(true)
    setError('')
    setSuccess('')
  }

  async function saveDateEdit() {
    if (!activeTransition?.id || transitionDates.length !== TRANSITION_DAY_COUNT) {
      setError('Please choose exactly three transition dates.')
      return
    }
    setBusy(true)
    setError('')
    try {
      await apiFetch(`/api/v1/cases/${caseItem.id}/transitions/${activeTransition.id}/dates`, {
        method: 'PATCH',
        body: JSON.stringify({ transition_dates: transitionDates }),
      })
      setEditingDates(false)
      setSuccess('Transition dates updated. Dates with submitted logs remain protected.')
      onChanged?.()
    } catch (err) {
      setError(err.message || 'Could not update transition dates')
    } finally {
      setBusy(false)
    }
  }

  async function cancelTransition() {
    if (!activeTransition?.id) return
    setBusy(true)
    setError('')
    try {
      await apiFetch(`/api/v1/cases/${caseItem.id}/transitions/${activeTransition.id}/cancel`, {
        method: 'POST',
        body: JSON.stringify({ reason: cancellationReason.trim() || null }),
      })
      setCancelling(false)
      setCancellationReason('')
      setSuccess('Transition cancelled. The original therapist remains assigned.')
      onChanged?.()
    } catch (err) {
      setError(err.message || 'Could not cancel transition')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="admin-scheduling-hub__transition" style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border, #e2e8f0)' }}>
      <h4 style={{ margin: '0 0 8px', fontSize: '0.95rem' }}>Transition therapist</h4>
      <p className="admin-muted" style={{ fontSize: '0.85rem', marginBottom: 10 }}>
        Run a {TRANSITION_DAY_COUNT}-day handover where both therapists submit logs. Flat pay ₹500 full day / ₹350 half day during transition.
        Billing for the incoming therapist applies after handover completes.
      </p>
      {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}
      {success ? <p className="admin-alert admin-alert--success">{success}</p> : null}

      {activeTransition ? (
        <div className="admin-alert admin-alert--success" style={{ marginBottom: 10 }}>
          <strong>Handover in progress.</strong> {statusLine}
        </div>
      ) : null}

      {activeTransition && canAssign && !readOnly ? (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
          <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" onClick={beginDateEdit}>
            Edit transition dates
          </button>
          {activeTransition.can_cancel ? (
            <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setCancelling(true)}>
              Cancel transition
            </button>
          ) : null}
        </div>
      ) : null}

      {editingDates && activeTransition ? (
        <div style={{ marginBottom: 12 }}>
          <TransitionDateCalendar
            caseId={caseItem.id}
            incomingTherapistId={activeTransition.incoming_therapist_user_id}
            outgoingTherapistId={activeTransition.outgoing_therapist_user_id}
            value={transitionDates}
            onChange={setTransitionDates}
            lockedDates={activeTransition.locked_dates || []}
            disabled={busy || readOnly}
            requiredCount={TRANSITION_DAY_COUNT}
          />
          <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
            <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={saveDateEdit} disabled={busy || transitionDates.length !== TRANSITION_DAY_COUNT}>
              {busy ? 'Saving…' : 'Save transition dates'}
            </button>
            <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setEditingDates(false)} disabled={busy}>
              Keep current dates
            </button>
          </div>
        </div>
      ) : null}

      {cancelling && activeTransition ? (
        <div className="admin-alert admin-alert--warning" style={{ marginBottom: 10 }}>
          <label className="admin-label">
            Cancellation note (optional)
            <textarea className="admin-input" rows={2} value={cancellationReason} onChange={(event) => setCancellationReason(event.target.value)} />
          </label>
          <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
            <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={cancelTransition} disabled={busy}>
              {busy ? 'Cancelling…' : 'Confirm cancellation'}
            </button>
            <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setCancelling(false)} disabled={busy}>
              Keep transition
            </button>
          </div>
        </div>
      ) : null}

      {!primaryTherapistId ? (
        <p className="admin-muted" style={{ fontSize: '0.85rem' }}>
          Assign a primary therapist first before starting a transition.
        </p>
      ) : null}

      {!canAssign ? (
        <p className="admin-muted" style={{ fontSize: '0.85rem' }}>
          You don&apos;t have permission to start a transition.
        </p>
      ) : null}

      {canStart && !expanded ? (
        <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" onClick={openTransitionForm}>
          Add transition therapist
        </button>
      ) : null}

      {expanded && canStart ? (
        <div className="admin-form-grid" style={{ maxWidth: 520, marginTop: 8 }}>
          <label className="admin-label" style={{ gridColumn: '1 / -1' }}>
            Incoming transition therapist
            <AdminTherapistPicker
              mode="allotment"
              productModule={caseItem.product_module}
              caseId={caseItem.id}
              value={incomingId}
              onChange={(value) => {
                setIncomingId(value)
                setBillingReady(false)
                setBillingPayload(null)
                setTransitionDates(defaultTransitionDates())
              }}
              disabled={readOnly}
            />
          </label>

          <div style={{ gridColumn: '1 / -1' }}>
            <p className="admin-label__caption" style={{ marginBottom: 6 }}>
              Transition dates ({TRANSITION_DAY_COUNT} days)
            </p>
            <TransitionDateCalendar
              caseId={caseItem.id}
              incomingTherapistId={incomingId}
              outgoingTherapistId={primaryTherapistId}
              value={transitionDates}
              onChange={setTransitionDates}
              disabled={readOnly || busy}
              requiredCount={TRANSITION_DAY_COUNT}
            />
          </div>

          {incomingId ? (
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
          ) : null}

          <div style={{ gridColumn: '1 / -1', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              type="button"
              className="admin-btn admin-btn--primary"
              onClick={handleSubmit}
              disabled={busy || !incomingId || !billingReady || transitionDates.length !== TRANSITION_DAY_COUNT}
            >
              {busy ? 'Starting…' : 'Start transition handover'}
            </button>
            <button type="button" className="admin-btn admin-btn--ghost" onClick={closeTransitionForm} disabled={busy}>
              Cancel
            </button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
