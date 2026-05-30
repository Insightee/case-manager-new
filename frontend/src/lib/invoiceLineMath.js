/** Client invoice line display and live-edit calculations (qty × unit + GST). */

export function lineTaxLabel(gstRatePercent) {
  const rate = Number(gstRatePercent)
  if (!rate || rate <= 0) return 'Non-taxable'
  return `GST ${rate}%`
}

export function computeLineFromInputs({ quantity, unitRateInr, gstRatePercent, amountInr }) {
  const qty = Math.max(Number(quantity) || 1, 0.01)
  let rate = unitRateInr !== '' && unitRateInr != null ? Number(unitRateInr) : null
  const gstPct = gstRatePercent !== '' && gstRatePercent != null ? Number(gstRatePercent) : 0

  if (rate == null && amountInr != null && amountInr !== '') {
    const total = Number(amountInr)
    if (gstPct > 0) {
      const taxableTotal = total / (1 + gstPct / 100)
      rate = taxableTotal / qty
    } else {
      rate = total / qty
    }
  }

  if (rate == null) {
    return {
      quantity: qty,
      unitRateInr: null,
      taxableAmountInr: 0,
      gstRatePercent: gstPct,
      gstAmountInr: 0,
      lineTotalInr: 0,
      taxLabel: lineTaxLabel(gstPct),
    }
  }

  const taxable = Math.round(qty * rate * 100) / 100
  const gstAmount = gstPct > 0 ? Math.round(taxable * (gstPct / 100) * 100) / 100 : 0
  const lineTotal = Math.round((taxable + gstAmount) * 100) / 100

  return {
    quantity: qty,
    unitRateInr: Math.round(rate * 100) / 100,
    taxableAmountInr: taxable,
    gstRatePercent: gstPct,
    gstAmountInr: gstAmount,
    lineTotalInr: lineTotal,
    taxLabel: lineTaxLabel(gstPct),
  }
}

export function displayLineFields(line) {
  const computed = computeLineFromInputs({
    quantity: line.quantity ?? 1,
    unitRateInr: line.unitRateInr ?? line.amountInr,
    gstRatePercent: line.gstRatePercent ?? '',
    amountInr: line.amountInr,
  })
  return {
    ...computed,
    unitRateInr: line.unitRateInr != null ? line.unitRateInr : computed.unitRateInr,
    taxableAmountInr:
      line.taxableAmountInr != null ? line.taxableAmountInr : computed.taxableAmountInr,
    gstAmountInr: line.gstAmountInr != null ? line.gstAmountInr : computed.gstAmountInr,
    lineTotalInr: line.amountInr != null ? line.amountInr : computed.lineTotalInr,
    hsnSacCode: line.hsnSacCode || '',
    taxLabel: lineTaxLabel(line.gstRatePercent),
  }
}

export function sumLinesForDisplay(lines) {
  let taxable = 0
  let gst = 0
  let lineTotal = 0
  for (const l of lines || []) {
    if (l.lineItemType === 'DISCOUNT') continue
    const d = displayLineFields(l)
    taxable += d.taxableAmountInr || 0
    gst += d.gstAmountInr || 0
    lineTotal += d.lineTotalInr || 0
  }
  return { taxable, gst, lineTotal }
}
