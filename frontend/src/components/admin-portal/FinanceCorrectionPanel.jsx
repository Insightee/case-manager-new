import { useCallback, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { formatInr } from '../../lib/financeConfidence.js'

const WRONG_SIDES = [
  { value: 'INVOICE_WRONG', label: 'Invoice wrong — fix invoice to match activity' },
  { value: 'RECORD_WRONG', label: 'Record wrong — fix ledger/activity, invoice stands' },
]

export function FinanceCorrectionPanel({ row, billingMonth, onDone }) {
  const [wrongSide, setWrongSide] = useState('')
  const [reason, setReason] = useState('')
  const [preview, setPreview] = useState(null)
  const [proposal, setProposal] = useState(null)
  const [newClientAmount, setNewClientAmount] = useState('')
  const [deductionAmount, setDeductionAmount] = useState('')
  const [deductionReason, setDeductionReason] = useState('')
  const [noteReason, setNoteReason] = useState('')
  const [noteScope, setNoteScope] = useState('CRM')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(null)
  const [error, setError] = useState(null)

  const hasDiff =
    row.reconciliation?.amountDiffInr != null && Math.abs(row.reconciliation.amountDiffInr) > 0.01

  const loadPreview = useCallback(async () => {
    if (!wrongSide) return
    setBusy(true)
    setError(null)
    try {
      const body = await apiFetch('/api/v1/admin/finance-writable/corrections/preview-correct-reshare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          case_id: row.caseId,
          billing_month: billingMonth,
          wrong_side: wrongSide,
        }),
      })
      setPreview(body)
      if (body.blocked) setError(body.blockReason)
    } catch (err) {
      setError(err?.message || 'Preview could not load.')
    } finally {
      setBusy(false)
    }
  }, [wrongSide, row.caseId, billingMonth])

  const proposeCorrectReshare = async () => {
    if (!wrongSide || !reason.trim()) {
      setError('Pick which side was wrong and add a reason before proposing.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const body = await apiFetch('/api/v1/admin/finance-writable/corrections/correct-reshare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          case_id: row.caseId,
          billing_month: billingMonth,
          wrong_side: wrongSide,
          reason: reason.trim(),
        }),
      })
      setProposal(body)
      setMessage('Correction proposed — review the four numbers below, then approve or reject.')
    } catch (err) {
      setError(err?.message || 'Could not save proposal.')
    } finally {
      setBusy(false)
    }
  }

  const proposeLinkedEdit = async () => {
    const amt = parseFloat(newClientAmount)
    if (!Number.isFinite(amt) || !reason.trim()) {
      setError('Enter the corrected client amount and a reason.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const body = await apiFetch('/api/v1/admin/finance-writable/corrections/linked-amount-edit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          case_id: row.caseId,
          billing_month: billingMonth,
          new_client_amount_inr: amt,
          reason: reason.trim(),
        }),
      })
      setProposal(body)
      setMessage('Linked edit proposed — client and payout will move together on approve.')
    } catch (err) {
      setError(err?.message || 'Could not save linked edit.')
    } finally {
      setBusy(false)
    }
  }

  const approve = async () => {
    if (!proposal?.id) return
    setBusy(true)
    setError(null)
    try {
      await apiFetch(`/api/v1/admin/finance-writable/corrections/${proposal.id}/approve`, { method: 'POST' })
      setMessage('Approved — client invoice and therapist payout updated together.')
      setProposal(null)
      onDone?.()
    } catch (err) {
      setError(err?.message || 'Approve did not go through.')
    } finally {
      setBusy(false)
    }
  }

  const reject = async () => {
    if (!proposal?.id) return
    setBusy(true)
    setError(null)
    try {
      await apiFetch(`/api/v1/admin/finance-writable/corrections/${proposal.id}/reject`, { method: 'POST' })
      setMessage('Rejected — nothing moved.')
      setProposal(null)
    } catch (err) {
      setError(err?.message || 'Reject did not go through.')
    } finally {
      setBusy(false)
    }
  }

  const addDeduction = async () => {
    const amt = parseFloat(deductionAmount)
    if (!Number.isFinite(amt) || !deductionReason.trim() || !row.therapistId) {
      setError('Deduction needs amount, reason, and an assigned therapist.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await apiFetch('/api/v1/admin/finance-writable/deductions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          case_id: row.caseId,
          billing_month: billingMonth,
          therapist_user_id: row.therapistId,
          amount_inr: amt,
          direction: 'DEDUCT',
          reason: deductionReason.trim(),
          note_type: 'DEDUCTION',
        }),
      })
      setDeductionAmount('')
      setDeductionReason('')
      setMessage('Deduction recorded (applies after TDS on payout).')
      onDone?.()
    } catch (err) {
      setError(err?.message || 'Deduction could not be saved.')
    } finally {
      setBusy(false)
    }
  }

  const addNote = async () => {
    if (!noteReason.trim()) {
      setError('Structured notes need a reason.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await apiFetch('/api/v1/admin/finance-writable/notes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          case_id: row.caseId,
          note_scope: noteScope,
          note_type: 'OTHER',
          reason: noteReason.trim(),
          billing_month: billingMonth,
        }),
      })
      setNoteReason('')
      setMessage(`${noteScope} note saved.`)
      onDone?.()
    } catch (err) {
      setError(err?.message || 'Note could not be saved.')
    } finally {
      setBusy(false)
    }
  }

  const confirm = proposal?.confirmScreen

  return (
    <section className="brms-correction" aria-label="Finance correction proposals">
      <h4>Finance corrections (proposal → confirm → approve)</h4>
      <p className="admin-muted">
        Every money change is a proposal a human confirms. Pick which side was wrong — never a single ambiguous edit.
      </p>

      {error ? <p className="brms-correction__error" role="alert">{error}</p> : null}
      {message ? <p className="brms-correction__ok">{message}</p> : null}

      {hasDiff ? (
        <div className="brms-correction__block">
          <p className="admin-muted">Reconciliation diff detected — correct and reshare</p>
          <fieldset className="brms-correction__sides">
            <legend>Which side was wrong?</legend>
            {WRONG_SIDES.map((opt) => (
              <label key={opt.value} className="brms-correction__side">
                <input
                  type="radio"
                  name={`wrong-side-${row.caseId}`}
                  value={opt.value}
                  checked={wrongSide === opt.value}
                  onChange={() => {
                    setWrongSide(opt.value)
                    setPreview(null)
                  }}
                />
                {opt.label}
              </label>
            ))}
          </fieldset>
          <button type="button" className="btn btn--secondary btn--sm" disabled={!wrongSide || busy} onClick={loadPreview}>
            Preview correction
          </button>
          {preview ? (
            <div className="brms-correction__confirm-grid">
              <div><span>Old client</span><strong>{formatInr(preview.oldClientAmountInr ?? 0)}</strong></div>
              <div><span>New client</span><strong>{formatInr(preview.newClientAmountInr ?? 0)}</strong></div>
              <div><span>Old payout</span><strong>{formatInr(preview.oldPayoutAmountInr ?? 0)}</strong></div>
              <div><span>New payout</span><strong>{formatInr(preview.newPayoutAmountInr ?? 0)}</strong></div>
            </div>
          ) : null}
          <label className="brms-correction__reason">
            Reason (required)
            <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} />
          </label>
          <button type="button" className="btn btn--primary btn--sm" disabled={busy || !wrongSide} onClick={proposeCorrectReshare}>
            Propose correction
          </button>
        </div>
      ) : null}

      <div className="brms-correction__block">
        <p className="admin-muted">Linked client ↔ payout amount edit</p>
        <label>
          New client amount (INR)
          <input
            type="number"
            step="0.01"
            value={newClientAmount}
            onChange={(e) => setNewClientAmount(e.target.value)}
            placeholder={row.reconciliation?.raisedInvoiceAmountInr ?? ''}
          />
        </label>
        <label className="brms-correction__reason">
          Reason (required)
          <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} />
        </label>
        <button type="button" className="btn btn--secondary btn--sm" disabled={busy} onClick={proposeLinkedEdit}>
          Propose linked edit
        </button>
      </div>

      {confirm ? (
        <div className="brms-correction__confirm brms-correction__confirm-grid">
          <h5>Confirm screen — four numbers + reason</h5>
          <div><span>Old client</span><strong>{formatInr(confirm.oldClientAmountInr ?? 0)}</strong></div>
          <div><span>New client</span><strong>{formatInr(confirm.newClientAmountInr ?? 0)}</strong></div>
          <div><span>Old payout</span><strong>{formatInr(confirm.oldPayoutAmountInr ?? 0)}</strong></div>
          <div><span>New payout</span><strong>{formatInr(confirm.newPayoutAmountInr ?? 0)}</strong></div>
          <p className="brms-correction__reason-text"><em>{proposal?.reason}</em></p>
          <div className="brms-correction__actions">
            <button type="button" className="btn btn--primary btn--sm" disabled={busy} onClick={approve}>
              Approve (both sides)
            </button>
            <button type="button" className="btn btn--ghost btn--sm" disabled={busy} onClick={reject}>
              Reject
            </button>
          </div>
        </div>
      ) : null}

      <div className="brms-correction__block brms-correction__deduction">
        <p className="admin-muted">Structured deduction (payout side, after TDS)</p>
        <input type="number" step="0.01" placeholder="Amount INR" value={deductionAmount} onChange={(e) => setDeductionAmount(e.target.value)} />
        <textarea placeholder="Deduction reason" value={deductionReason} onChange={(e) => setDeductionReason(e.target.value)} rows={2} />
        <button type="button" className="btn btn--secondary btn--sm" disabled={busy} onClick={addDeduction}>
          Add deduction
        </button>
      </div>

      <div className="brms-correction__block">
        <p className="admin-muted">Structured CRM / HR note</p>
        <select value={noteScope} onChange={(e) => setNoteScope(e.target.value)}>
          <option value="CRM">CRM</option>
          <option value="HR">HR</option>
          <option value="FINANCE">Finance</option>
        </select>
        <textarea placeholder="Note reason" value={noteReason} onChange={(e) => setNoteReason(e.target.value)} rows={2} />
        <button type="button" className="btn btn--secondary btn--sm" disabled={busy} onClick={addNote}>
          Save note
        </button>
      </div>
    </section>
  )
}
