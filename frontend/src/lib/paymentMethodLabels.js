export function formatPaymentMethod(method) {
  const key = String(method || '').toUpperCase()
  const labels = {
    UPI: 'UPI',
    BANK_TRANSFER: 'Bank transfer',
    CASH: 'Cash',
    CHEQUE: 'Cheque',
    GATEWAY: 'Online gateway',
  }
  return labels[key] || key.replaceAll('_', ' ')
}

export function paymentStatusLabel(status) {
  const key = String(status || '').toLowerCase()
  const labels = {
    pending_review: 'Awaiting review',
    confirmed: 'Confirmed',
    rejected: 'Rejected',
  }
  return labels[key] || key.replaceAll('_', ' ')
}
