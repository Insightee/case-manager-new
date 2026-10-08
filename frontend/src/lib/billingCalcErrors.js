/** Structured therapist-payout billing calc errors (e.g. missing package_session_count). */

export const MISSING_PACKAGE_COUNT_CODE = 'MISSING_PACKAGE_COUNT'

/**
 * @param {unknown} err - typically apiFetch / apiDownload rejection (Error with optional .detail)
 * @returns {{ code: string|null, message: string, caseId?: number, caseCode?: string } | null}
 */
export function parseBillingCalcApiError(err) {
  if (!err || typeof err !== 'object') return null
  const detail = err.detail
  if (detail && typeof detail === 'object' && detail.code === MISSING_PACKAGE_COUNT_CODE) {
    return {
      code: MISSING_PACKAGE_COUNT_CODE,
      message: String(detail.message || err.message || '').trim(),
      caseId: detail.caseId,
      caseCode: detail.caseCode,
    }
  }
  const message = String(err.message || '').trim()
  if (!message) return null
  return { code: null, message }
}

/**
 * User-facing copy per portal audience. Does not change amounts — only explains the block.
 * @param {'therapist'|'admin'|'parent'} audience
 */
export function billingCalcErrorBannerText(parsed, audience = 'therapist') {
  if (!parsed?.message) return ''
  if (parsed.code === MISSING_PACKAGE_COUNT_CODE) {
    if (audience === 'admin') {
      const caseRef = parsed.caseCode ? ` (${parsed.caseCode})` : ''
      return `${parsed.message} Update package session count on the case billing profile${caseRef}, or open Data exceptions to find this case.`
    }
    if (audience === 'parent') {
      return (
        'Your family statements are separate from therapist payouts. ' +
        'If something looks wrong on a statement, use Dispute on that invoice or contact your case manager.'
      )
    }
    return `${parsed.message} Your case manager can fix this on the case billing profile — submit stays paused until then.`
  }
  return parsed.message
}

export function resolveBillingCalcErrorMessage(err, audience = 'therapist') {
  const parsed = parseBillingCalcApiError(err)
  if (!parsed) return String(err?.message || 'Something went wrong. Try again in a moment.')
  return billingCalcErrorBannerText(parsed, audience)
}
