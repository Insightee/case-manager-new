import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { AdminTherapistPicker } from './AdminTherapistPicker.jsx'
import { ReassignmentBillingConfirm } from './ReassignmentBillingConfirm.jsx'

const TRANSITION_DAY_COUNT = 3

function defaultTransitionDates() {
  const today = new Date()
  const dates = []
  for (let i = 0; i < TRANSITION_DAY_COUNT; i += 1) {
    const d = new Date(today)
    d.setDate(d.getDate() + i)
    dates.push(d.toISOString().slice(0, 10))
  }
  return dates
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

  useEffect(() => {
    if (!expanded) {
      setIncomingId('')
      setTransitionDates(defaultTransitionDates())
      setBillingReady(false)
      setBillingPayload(null)
      setError('')
      setSuccess('')
    }
  }, [expanded])

  useEffect(() => {
    setBillingReady(false)
    setBillingPayload(null)
  }, [incomingId])

  const blocked = Boolean(activeTransition)
  const canStart = canAssign && !readOnly && primaryTherapistId && !blocked

  const statusLine = useMemo(() => {
    if (!activeTransition) return null
    const outgoing = activeTransition.outgoing_therapist_name || `Therapist #${activeTransition.outgoing_therapist_user_id}`
    const incoming = activeTransition.incoming_therapist_name || `Therapist #${activeTransition.incoming_therapist_user_id}`
    return `${outgoing} + ${incoming} · ${formatDates(activeTransition.transition_dates)} · ${activeTransition.status}`
  }, [activeTransition])

  function updateDate(index, value) {
    setTransitionDates((prev) => prev.map((d, i) => (i === index ? value : d)))
  }

  async function handleSubmit() {
    if (!caseItem?.id || !incomingId) return
    if (String(incomingId) === String(primaryTherapistId)) {
      setError('The transition therapist must be different from the current therapist.')
      return
    }
    if (!billingReady || !billingPayload) {
      setError('Enter billing for the incoming therapist before starting the transition.')
      return
    }
    const uniqueDates = new Set(transitionDates)
    if (uniqueDates.size !== TRANSITION_DAY_COUNT) {
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
      onChanged?.()
    } catch (err) {
      setError(err.message || 'Could not start transition')
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

      {activeTransition ? (
        <div className="admin-alert admin-alert--success" style={{ marginBottom: 10 }}>
          <strong>Handover in progress.</strong> {statusLine}
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
        <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" onClick={() => setExpanded(true)}>
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
              onChange={setIncomingId}
              disabled={readOnly}
            />
          </label>

          <div style={{ gridColumn: '1 / -1' }}>
            <p className="admin-label__caption" style={{ marginBottom: 6 }}>
              Transition dates ({TRANSITION_DAY_COUNT} days)
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {transitionDates.map((d, index) => (
                <label key={`transition-date-${index}`} className="admin-label" style={{ minWidth: 150 }}>
                  Day {index + 1}
                  <input
                    type="date"
                    className="admin-input"
                    value={d}
                    onChange={(e) => updateDate(index, e.target.value)}
                    disabled={readOnly}
                  />
                </label>
              ))}
            </div>
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

          {error ? <p className="admin-alert admin-alert--error" style={{ gridColumn: '1 / -1' }}>{error}</p> : null}
          {success ? <p className="admin-alert admin-alert--success" style={{ gridColumn: '1 / -1' }}>{success}</p> : null}

          <div style={{ gridColumn: '1 / -1', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              type="button"
              className="admin-btn admin-btn--primary"
              onClick={handleSubmit}
              disabled={busy || !incomingId || !billingReady}
            >
              {busy ? 'Starting…' : 'Start transition handover'}
            </button>
            <button type="button" className="admin-btn admin-btn--ghost" onClick={() => setExpanded(false)} disabled={busy}>
              Cancel
            </button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
