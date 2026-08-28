/**
 * Therapist pay: flat lumpsum INR only (percentage mode retired).
 * Kept for callers that still import the helper; always emits FIXED_LUMP.
 */
export function TherapistCompensationFields({
  therapistFixedPayInr,
  onTherapistFixedPayChange,
  fixedAmountLabel = 'Therapist pay (lumpsum, INR)',
  disabled = false,
  fixedRequired = false,
}) {
  return (
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
  )
}

export function buildTherapistCompensationPayload(compensationMode, paySharePct, therapistFixedPayInr) {
  const lump =
    therapistFixedPayInr != null && therapistFixedPayInr !== ''
      ? Number(therapistFixedPayInr)
      : paySharePct != null && paySharePct !== '' && Number(paySharePct) > 0 && Number(paySharePct) <= 100
        ? null
        : Number(therapistFixedPayInr || 0)
  // Legacy callers may still pass a percent — ignore it and require an INR lump.
  return {
    compensation_mode: 'FIXED_LUMP',
    therapist_fixed_pay_inr: lump,
    pay_share_amount_inr: lump,
  }
}
