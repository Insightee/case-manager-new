import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { LEAVE_CATEGORIES, caseLabel, caseServiceLine } from '../../lib/leaveFormUtils.js'
import './therapist-leave.css'

/**
 * Shared leave request fields — same UI as TherapistLeavePage form card.
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
  billingCategory = 'PAID',
  onBillingCategoryChange,
  reason = '',
  onReasonChange,
  disabled = false,
  casesLoading = false,
  casesError = '',
  onRetryCases,
}) {
  const [suggestion, setSuggestion] = useState(null)

  const selectedCases = useMemo(
    () => {
      if (lockedCase) return [lockedCase]
      return assignedCases.filter((c) => caseIds.includes(Number(c.id)))
    },
    [assignedCases, caseIds, lockedCase],
  )

  const hasShadowSelection = selectedCases.some((c) => caseServiceLine(c) === 'shadow_support')
  const hasHomecareSelection = selectedCases.some((c) => caseServiceLine(c) === 'homecare')
  const allCasesSelected = assignedCases.length > 0 && caseIds.length === assignedCases.length

  const categoryOptions = hasShadowSelection
    ? LEAVE_CATEGORIES
    : LEAVE_CATEGORIES.filter((c) => c.value === 'UNPAID')

  useEffect(() => {
    if (!hasShadowSelection && hasHomecareSelection && billingCategory !== 'UNPAID') {
      onBillingCategoryChange?.('UNPAID')
    }
  }, [hasShadowSelection, hasHomecareSelection, billingCategory, onBillingCategoryChange])

  useEffect(() => {
    if (!startDate || !endDate || endDate < startDate || !hasShadowSelection) {
      setSuggestion(null)
      return
    }
    const q = new URLSearchParams({
      start_date: startDate,
      end_date: endDate,
      service_line: 'shadow_support',
    })
    apiFetch(`/api/v1/leave/suggest?${q}`)
      .then((s) => {
        setSuggestion(s)
        if (s.paid_days > 0) onBillingCategoryChange?.('PAID')
        else if (s.carry_forward_days > 0) onBillingCategoryChange?.('CARRY_FORWARD')
        else onBillingCategoryChange?.('UNPAID')
      })
      .catch(() => setSuggestion(null))
  }, [startDate, endDate, hasShadowSelection, onBillingCategoryChange])

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

      {hasHomecareSelection ? (
        <div className="therapist-leave-page__warn" role="alert">
          <strong>Paid leave applies to shadow clients only.</strong> Homecare and other services on this request will
          be recorded as therapist absence — sessions are treated like a cancellation, not paid leave.
        </div>
      ) : null}

      <label className="therapist-leave-page__field">
        Leave category
        <select
          value={billingCategory}
          onChange={(e) => onBillingCategoryChange?.(e.target.value)}
          disabled={disabled || (!hasShadowSelection && hasHomecareSelection)}
          className="therapist-leave-page__input"
        >
          {categoryOptions.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
      </label>

      {hasShadowSelection && billingCategory === 'PAID' ? (
        <p className="therapist-leave-page__hint">
          Monthly leave uses your paid shadow balance (max 1 paid day per request; extra days go to carry forward).
        </p>
      ) : null}

      {hasShadowSelection && billingCategory === 'UNPAID' ? (
        <p className="therapist-leave-page__hint">
          Unpaid leave is reflected in your payout calculation and may affect client billing (prepaid clients are
          adjusted in the next billing cycle after admin approval).
        </p>
      ) : null}

      {hasShadowSelection && billingCategory === 'CARRY_FORWARD' ? (
        <p className="therapist-leave-page__hint">Carry forward applies to shadow support paid leave policy only.</p>
      ) : null}

      {suggestion && hasShadowSelection ? (
        <p className="therapist-leave-page__suggest">
          {suggestion.message}
          {suggestion.paid_days > 0 || suggestion.carry_forward_days > 0
            ? ` (${suggestion.paid_days} monthly, ${suggestion.carry_forward_days} carry forward, ${suggestion.unpaid_days} unpaid)`
            : ''}
        </p>
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
    </div>
  )
}
