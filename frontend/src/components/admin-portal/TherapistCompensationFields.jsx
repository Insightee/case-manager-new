/**
 * Therapist pay: percentage of client billing or fixed INR amount.
 * Used for both PER_SESSION and PACKAGE billing on cases.
 */
export function TherapistCompensationFields({
  compensationMode,
  paySharePct,
  therapistFixedPayInr,
  onCompensationModeChange,
  onPaySharePctChange,
  onTherapistFixedPayChange,
  fixedAmountLabel = 'Therapist fixed pay (INR)',
  disabled = false,
  percentageRequired = false,
  fixedRequired = false,
}) {
  const mode = compensationMode || 'PERCENTAGE'

  return (
    <>
      <label>
        Therapist compensation
        <select
          className="admin-input"
          value={mode}
          onChange={(e) => onCompensationModeChange(e.target.value)}
          disabled={disabled}
        >
          <option value="PERCENTAGE">Percentage</option>
          <option value="FIXED_LUMP">Fixed amount (INR)</option>
        </select>
      </label>
      {mode === 'PERCENTAGE' ? (
        <label>
          Therapist share % (50–100)
          <input
            type="number"
            min="50"
            max="100"
            step="0.01"
            inputMode="decimal"
            className="admin-input"
            value={paySharePct}
            onChange={(e) => onPaySharePctChange(e.target.value)}
            disabled={disabled}
            required={percentageRequired}
          />
        </label>
      ) : (
        <label>
          {fixedAmountLabel}
          <input
            type="number"
            min="0"
            step="0.01"
            inputMode="decimal"
            className="admin-input"
            value={therapistFixedPayInr}
            onChange={(e) => onTherapistFixedPayChange(e.target.value)}
            disabled={disabled}
            required={fixedRequired}
          />
        </label>
      )}
    </>
  )
}

export function buildTherapistCompensationPayload(compensationMode, paySharePct, therapistFixedPayInr) {
  const mode = compensationMode || 'PERCENTAGE'
  const payload = { compensation_mode: mode }
  if (mode === 'FIXED_LUMP') {
    payload.therapist_fixed_pay_inr = Number(therapistFixedPayInr)
    payload.pay_share_pct = null
  } else {
    payload.pay_share_pct = Number(paySharePct)
    payload.therapist_fixed_pay_inr = null
  }
  return payload
}
