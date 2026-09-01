import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { isLeaveBalanceUpdated, paidLeaveCreditHint } from '../../lib/leaveBalanceDisplay.js'
import { caseLabel, caseServiceLine, formatLeaveSplitLabel, LEAVE_CATEGORIES } from '../../lib/leaveFormUtils.js'
import './therapist-leave.css'

/**
 * Shared leave request fields — case selection, dates, split preview, parent consultation.
 * When hideLeaveCreditDetails is true, credit balance copy is hidden; paid/unpaid radios
 * still show for shadow so therapists can choose (paid default).
 */
export function TherapistLeaveRequestFields({
  assignedCases = [],
  caseIds = [],
  onCaseIdsChange,
  lockedCase = null,
  startDate = '',
  endDate = '',
  onStartDateChange,
  onEndDateChange,
  reason = '',
  onReasonChange,
  consultedWithParents = false,
  onConsultedWithParentsChange,
  billingCategory = 'PAID',
  onBillingCategoryChange,
  disabled = false,
  leaveBalance = null,
  forTherapistUserId = null,
  casesLoading = false,
  casesError = '',
  onRetryCases,
  hideLeaveCreditDetails = false,
}) {
  const [suggestion, setSuggestion] = useState(null)

  const selectedCases = useMemo(() => {
    if (lockedCase) return [lockedCase]
    return assignedCases.filter((c) => caseIds.includes(Number(c.id)))
  }, [assignedCases, caseIds, lockedCase])

  const hasShadowSelection = selectedCases.some((c) => caseServiceLine(c) === 'shadow_support')
  const hasHomecareSelection = selectedCases.some((c) => caseServiceLine(c) === 'homecare')
  const allCasesSelected = assignedCases.length > 0 && caseIds.length === assignedCases.length
  const creditPending = leaveBalance?.leave_credit_pending ?? leaveBalance?.paid_remaining ?? 0
  const creditsAvailable =
    hasShadowSelection && isLeaveBalanceUpdated(leaveBalance) && Number(creditPending) > 0
  const showLeaveType = hasShadowSelection
  const canChoosePaid = showLeaveType && creditsAvailable
  const forceUnpaid = showLeaveType && !creditsAvailable

  useEffect(() => {
    if (!onBillingCategoryChange) return
    if (!hasShadowSelection) {
      if (billingCategory !== 'UNPAID') onBillingCategoryChange('UNPAID')
      return
    }
    if (forceUnpaid && billingCategory !== 'UNPAID') {
      onBillingCategoryChange('UNPAID')
      return
    }
    if (canChoosePaid && billingCategory !== 'PAID' && billingCategory !== 'UNPAID') {
      onBillingCategoryChange('PAID')
    }
  }, [hasShadowSelection, forceUnpaid, canChoosePaid, billingCategory, onBillingCategoryChange])

  useEffect(() => {
    if (!startDate || !endDate || endDate < startDate) {
      setSuggestion(null)
      return
    }
    const q = new URLSearchParams({
      start_date: startDate,
      end_date: endDate,
      service_line: hasShadowSelection ? 'shadow_support' : 'homecare',
    })
    if (forTherapistUserId) q.set('therapist_id', String(forTherapistUserId))
    if (caseIds.length) q.set('case_ids', caseIds.join(','))
    apiFetch(`/api/v1/leave/suggest?${q}`)
      .then((s) => setSuggestion(s))
      .catch(() => setSuggestion(null))
  }, [startDate, endDate, hasShadowSelection, caseIds, forTherapistUserId])

  function toggleCaseId(caseId) {
    const id = Number(caseId)
    const next = caseIds.includes(id) ? caseIds.filter((x) => x !== id) : [...caseIds, id]
    onCaseIdsChange?.(next)
  }

  return (
    <div className="therapist-leave-page__form-card therapist-leave-page__form-card--embedded">
      {!lockedCase ? (
        <fieldset style={{ border: 'none', margin: 0, padding: 0 }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 8,
              marginBottom: 8,
              flexWrap: 'wrap',
            }}
          >
            <legend style={{ fontSize: '0.875rem', fontWeight: 500, margin: 0 }}>
              Cases {assignedCases.length ? '(pick one or more)' : '(optional)'}
            </legend>
            {assignedCases.length ? (
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  type="button"
                  className="therapist-leave-page__link-btn"
                  onClick={() => onCaseIdsChange?.(assignedCases.map((c) => Number(c.id)))}
                  disabled={disabled || allCasesSelected}
                >
                  Select all
                </button>
                <button
                  type="button"
                  className="therapist-leave-page__link-btn"
                  onClick={() => onCaseIdsChange?.([])}
                  disabled={disabled || !caseIds.length}
                >
                  Clear
                </button>
              </div>
            ) : null}
          </div>
          {casesLoading ? (
            <p style={{ margin: 0, fontSize: '0.8125rem', color: '#64748b' }}>Loading your cases…</p>
          ) : casesError ? (
            <p style={{ margin: 0, fontSize: '0.8125rem', color: '#b91c1c' }}>
              {casesError}{' '}
              {onRetryCases ? (
                <button type="button" className="therapist-leave-page__link-btn" onClick={onRetryCases}>
                  Retry
                </button>
              ) : null}
            </p>
          ) : assignedCases.length ? (
            <div className="therapist-leave-page__case-list">
              {assignedCases.map((c) => (
                <label key={c.id} className="therapist-leave-page__case-option">
                  <input
                    type="checkbox"
                    checked={caseIds.includes(Number(c.id))}
                    onChange={() => toggleCaseId(c.id)}
                    disabled={disabled}
                  />
                  <span>{caseLabel(c)}</span>
                </label>
              ))}
            </div>
          ) : (
            <p style={{ margin: 0, fontSize: '0.8125rem', color: '#64748b' }}>
              No active cases assigned — you can still submit leave for HR tracking.
            </p>
          )}
        </fieldset>
      ) : null}

      {hasHomecareSelection && !hasShadowSelection ? (
        <div className="therapist-leave-page__warn" role="alert">
          {hideLeaveCreditDetails ? (
            <>
              <strong>Homecare only.</strong> Sessions will be cancelled and parents informed.
            </>
          ) : (
            <>
              <strong>Homecare only.</strong> Sessions will be cancelled and parents informed — leave credits are not
              used.
            </>
          )}
        </div>
      ) : null}

      {hasShadowSelection && !hasHomecareSelection ? (
        hideLeaveCreditDetails ? (
          <div className="therapist-leave-page__warn" role="alert">
            <strong>Shadow support.</strong> Sessions on these dates will be cancelled after HR approval.
          </div>
        ) : (
          <p className="therapist-leave-page__hint">
            {paidLeaveCreditHint(leaveBalance) ||
              'Available leave credits are used first for shadow support days.'}
          </p>
        )
      ) : null}

      {hasShadowSelection && hasHomecareSelection ? (
        <div className="therapist-leave-page__warn" role="alert">
          {hideLeaveCreditDetails ? (
            <>
              <strong>Mixed cases.</strong> Shadow and homecare sessions on these dates will be cancelled after HR
              approval.
            </>
          ) : (
            <>
              <strong>Mixed cases.</strong> Leave credits apply to shadow days only; homecare sessions cancel without
              using credits.
            </>
          )}
        </div>
      ) : null}

      {!hideLeaveCreditDetails && suggestion ? (
        <p className="therapist-leave-page__suggest">{formatLeaveSplitLabel(suggestion)}</p>
      ) : null}

      {showLeaveType ? (
        <fieldset className="therapist-leave-page__leave-type" style={{ border: 'none', margin: 0, padding: 0 }}>
          <legend className="therapist-leave-page__field" style={{ marginBottom: 8 }}>
            Leave type
          </legend>
          <div className="therapist-leave-page__leave-type-options">
            {LEAVE_CATEGORIES.map((cat) => {
              const isPaid = cat.value === 'PAID'
              const isSelected = billingCategory === cat.value
              const isDisabled = disabled || (isPaid && !canChoosePaid)
              return (
                <label key={cat.value} className="therapist-leave-page__case-option">
                  <input
                    type="radio"
                    name="leave_billing_category"
                    value={cat.value}
                    checked={isSelected}
                    disabled={isDisabled}
                    onChange={() => onBillingCategoryChange?.(cat.value)}
                  />
                  <span>{cat.label}</span>
                </label>
              )
            })}
          </div>
          {canChoosePaid && billingCategory === 'PAID' ? (
            <p className="therapist-leave-page__hint" style={{ marginTop: 8 }}>
              Paid leave is selected by default — your available leave credits will be used.
            </p>
          ) : null}
          {billingCategory === 'UNPAID' && showLeaveType ? (
            <div className="therapist-leave-page__warn" role="alert" style={{ marginTop: 8 }}>
              {forceUnpaid
                ? 'No paid leave credits left — this leave is unpaid.'
                : 'You will not be compensated for this leave.'}
            </div>
          ) : null}
        </fieldset>
      ) : null}

      <div className="therapist-leave-page__form-dates">
        <label className="therapist-leave-page__field">
          From date
          <input
            type="date"
            value={startDate}
            onChange={(e) => {
              const start = e.target.value
              const end = endDate && endDate >= start ? endDate : start
              onStartDateChange?.(start)
              if (end !== endDate) onEndDateChange?.(end)
            }}
            required
            disabled={disabled}
            className="therapist-leave-page__input"
          />
        </label>
        <label className="therapist-leave-page__field">
          To date
          <input
            type="date"
            value={endDate}
            min={startDate || undefined}
            onChange={(e) => onEndDateChange?.(e.target.value)}
            required
            disabled={disabled}
            className="therapist-leave-page__input"
          />
        </label>
      </div>

      <label className="therapist-leave-page__field">
        Reason (optional)
        <textarea
          value={reason}
          onChange={(e) => onReasonChange?.(e.target.value)}
          rows={3}
          disabled={disabled}
          className="therapist-leave-page__input therapist-leave-page__textarea"
        />
      </label>

      <label className="therapist-leave-page__case-option" style={{ marginTop: 4 }}>
        <input
          type="checkbox"
          checked={consultedWithParents}
          onChange={(e) => onConsultedWithParentsChange?.(e.target.checked)}
          disabled={disabled}
        />
        <span>Consulted with parents</span>
      </label>
    </div>
  )
}
