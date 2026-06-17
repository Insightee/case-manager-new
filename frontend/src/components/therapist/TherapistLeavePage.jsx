import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext.jsx'
import { apiFetch } from '../../lib/apiClient.js'
import { formatDisplayDate } from '../../lib/datetime.js'
import { fetchAllPages } from '../../lib/listApi.js'
import { isLeaveBalanceUpdated, leaveBalanceRemainingLabel } from '../../lib/leaveBalanceDisplay.js'
import { LEAVE_CATEGORIES, caseLabel, caseServiceLine, categoryLabel } from '../../lib/leaveFormUtils.js'
import './therapist-leave.css'

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

const STATUS_COLORS = {
  PENDING: { bg: '#fefce8', color: '#a16207', border: '#fde047' },
  APPROVED: { bg: '#f0fdf4', color: '#15803d', border: '#86efac' },
  REJECTED: { bg: '#fef2f2', color: '#b91c1c', border: '#fca5a5' },
  CANCELLED: { bg: '#f4f4f5', color: '#71717a', border: '#d4d4d8' },
}

const TYPE_COLORS = {
  ANNUAL: '#dbeafe',
  SICK: '#fce7f3',
  CASUAL: '#d1fae5',
  UNPAID: '#fde8d8',
  PAID: '#dbeafe',
  CARRY_FORWARD: '#ede9fe',
}

function leaveRowLabel(l) {
  if (l.billing_category) return categoryLabel(l.billing_category)
  return l.leave_type || '—'
}

function leaveRowColor(l) {
  const key = l.billing_category || l.leave_type
  return TYPE_COLORS[key] || '#f3f4f6'
}

const EMPTY_FORM = {
  billing_category: 'PAID',
  case_ids: [],
  start_date: '',
  end_date: '',
  reason: '',
}

export function TherapistLeavePage() {
  const { user, loading: authLoading } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const now = useMemo(() => new Date(), [])

  const [calYear, setCalYear] = useState(now.getFullYear())
  const [listMonthFilter, setListMonthFilter] = useState('ALL')
  const [listYearFilter, setListYearFilter] = useState(String(now.getFullYear()))
  const [leaves, setLeaves] = useState([])
  const [summary, setSummary] = useState(null)
  const [balance, setBalance] = useState(null)
  const [suggestion, setSuggestion] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [assignedCases, setAssignedCases] = useState([])
  const [casesLoading, setCasesLoading] = useState(true)
  const [casesError, setCasesError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const loadLeaves = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      const [data, sum, bal] = await Promise.all([
        apiFetch('/api/v1/leave'),
        apiFetch(`/api/v1/leave/summary?year=${calYear}`),
        apiFetch(`/api/v1/leave/balance?year=${calYear}`).catch(() => null),
      ])
      setLeaves(Array.isArray(data) ? data : [])
      setSummary(sum)
      setBalance(bal || sum?.leave_balance || null)
    } catch (err) {
      setLeaves([])
      setSummary(null)
      setLoadError(err.message || 'Could not load leave requests')
    } finally {
      setLoading(false)
    }
  }, [calYear])

  const loadAssignedCases = useCallback(async () => {
    setCasesLoading(true)
    setCasesError('')
    try {
      const { items } = await fetchAllPages(
        (page, pageSize) => apiFetch(`/api/v1/cases?assigned=true&page=${page}&page_size=${pageSize}`),
        { pageSize: 100 },
      )
      const active = items.filter((c) => c.status !== 'CLOSED' && c.status !== 'SUSPENDED')
      setAssignedCases(active)
    } catch (err) {
      setAssignedCases([])
      setCasesError(err.message || 'Could not load your cases')
    } finally {
      setCasesLoading(false)
    }
  }, [])

  useEffect(() => {
    if (authLoading || !user) return
    loadLeaves()
    loadAssignedCases()
  }, [authLoading, user, loadLeaves, loadAssignedCases])

  const selectedCases = useMemo(
    () => assignedCases.filter((c) => form.case_ids.includes(Number(c.id))),
    [assignedCases, form.case_ids],
  )
  const hasShadowSelection = selectedCases.some((c) => caseServiceLine(c) === 'shadow_support')
  const hasHomecareSelection = selectedCases.some((c) => caseServiceLine(c) === 'homecare')
  const allCasesSelected =
    assignedCases.length > 0 && form.case_ids.length === assignedCases.length

  useEffect(() => {
    if (!form.start_date || !form.end_date || form.end_date < form.start_date || !hasShadowSelection) {
      setSuggestion(null)
      return
    }
    const q = new URLSearchParams({
      start_date: form.start_date,
      end_date: form.end_date,
      service_line: 'shadow_support',
    })
    apiFetch(`/api/v1/leave/suggest?${q}`)
      .then((s) => {
        setSuggestion(s)
        if (s.paid_days > 0) setForm((f) => ({ ...f, billing_category: 'PAID' }))
        else if (s.carry_forward_days > 0) setForm((f) => ({ ...f, billing_category: 'CARRY_FORWARD' }))
        else setForm((f) => ({ ...f, billing_category: 'UNPAID' }))
      })
      .catch(() => setSuggestion(null))
  }, [form.start_date, form.end_date, hasShadowSelection])

  useEffect(() => {
    if (searchParams.get('new') === '1') {
      setShowForm(true)
      searchParams.delete('new')
      setSearchParams(searchParams, { replace: true })
    }
  }, [searchParams, setSearchParams])

  useEffect(() => {
    if (!hasShadowSelection && hasHomecareSelection) {
      setForm((f) => (f.billing_category === 'UNPAID' ? f : { ...f, billing_category: 'UNPAID' }))
    }
  }, [hasShadowSelection, hasHomecareSelection])

  function toggleCaseId(caseId) {
    const id = Number(caseId)
    setForm((f) => {
      const ids = f.case_ids.includes(id) ? f.case_ids.filter((x) => x !== id) : [...f.case_ids, id]
      return { ...f, case_ids: ids }
    })
  }

  function selectAllCases() {
    setForm((f) => ({ ...f, case_ids: assignedCases.map((c) => Number(c.id)) }))
  }

  function clearAllCases() {
    setForm((f) => ({ ...f, case_ids: [] }))
  }

  async function submitLeave(e) {
    e.preventDefault()
    if (assignedCases.length && !form.case_ids.length) {
      setError('Select at least one case, or use Select all.')
      return
    }
    if (!form.start_date || !form.end_date) {
      setError('Choose from and to dates.')
      return
    }
    if (form.end_date < form.start_date) {
      setError('End date must be on or after start date.')
      return
    }

    setSubmitting(true)
    setError('')
    setSuccess('')
    try {
      const targets =
        form.case_ids.length > 0
          ? form.case_ids.map((id) => assignedCases.find((c) => Number(c.id) === Number(id))).filter(Boolean)
          : [null]

      for (const caseRow of targets) {
        const serviceLine = caseRow ? caseServiceLine(caseRow) : 'shadow_support'
        let billingCategory = 'UNPAID'
        if (serviceLine === 'shadow_support') {
          billingCategory = form.billing_category
        }
        await apiFetch('/api/v1/leave', {
          method: 'POST',
          body: JSON.stringify({
            service_line: serviceLine,
            billing_category: billingCategory,
            case_id: caseRow ? Number(caseRow.id) : null,
            start_date: form.start_date,
            end_date: form.end_date,
            reason: form.reason || null,
          }),
        })
      }

      setForm(EMPTY_FORM)
      setSuggestion(null)
      setShowForm(false)
      setSuccess(
        targets.length > 1
          ? `${targets.length} leave requests submitted.`
          : 'Leave request submitted.',
      )
      await loadLeaves()
    } catch (err) {
      setError(err.message || 'Could not submit leave')
    } finally {
      setSubmitting(false)
    }
  }

  async function cancelLeave(id) {
    try {
      await apiFetch(`/api/v1/leave/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: 'CANCELLED' }),
      })
      await loadLeaves()
    } catch (err) {
      setError(err.message || 'Could not cancel leave')
    }
  }

  const pendingCount = summary?.pending_count ?? leaves.filter((l) => l.status === 'PENDING').length
  const rejectedCount = summary?.rejected_count ?? leaves.filter((l) => l.status === 'REJECTED').length
  const approvedDaysYtd = summary?.approved_days ?? 0
  const daysByType = summary?.days_by_type ?? {}

  const listYearOptions = useMemo(() => {
    const years = new Set([now.getFullYear(), now.getFullYear() - 1, now.getFullYear() + 1])
    leaves.forEach((l) => {
      if (l.start_date) years.add(Number(l.start_date.slice(0, 4)))
      if (l.end_date) years.add(Number(l.end_date.slice(0, 4)))
    })
    return Array.from(years).filter(Number.isFinite).sort((a, b) => b - a).map(String)
  }, [leaves, now])

  const filteredLeaves = useMemo(() => {
    return leaves.filter((l) => {
      const start = l.start_date ? new Date(`${l.start_date}T00:00:00`) : null
      if (!start) return false
      const yearOk = String(start.getFullYear()) === listYearFilter
      if (!yearOk) return false
      if (listMonthFilter === 'ALL') return true
      return start.getMonth() === Number(listMonthFilter)
    })
  }, [leaves, listYearFilter, listMonthFilter])

  function exportLeavesExcelLikeCsv() {
    const header = ['Category', 'Service', 'From', 'To', 'Days', 'Reason', 'Status', 'Note']
    const rows = filteredLeaves.map((l) => [
      leaveRowLabel(l),
      l.service_line || '',
      formatDisplayDate(l.start_date),
      formatDisplayDate(l.end_date),
      l.day_count ?? '',
      (l.reason || '').replaceAll('"', '""'),
      l.status || '',
      (l.status === 'REJECTED' ? l.review_note : '') || '',
    ])
    const csv = [header, ...rows]
      .map((row) => row.map((cell) => `"${String(cell ?? '')}"`).join(','))
      .join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `leave-requests-${listYearFilter}${listMonthFilter === 'ALL' ? '' : `-${Number(listMonthFilter) + 1}`}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  const categoryOptions = hasShadowSelection
    ? LEAVE_CATEGORIES
    : LEAVE_CATEGORIES.filter((c) => c.value === 'UNPAID')

  const leaveForm = showForm ? (
    <div className="therapist-leave-page__form-card">
      <p style={{ fontWeight: 600, marginBottom: 8 }}>New leave request</p>
      <form onSubmit={submitLeave} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <fieldset style={{ border: 'none', margin: 0, padding: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
            <legend style={{ fontSize: '0.875rem', fontWeight: 500, margin: 0 }}>
              Cases {assignedCases.length ? '(pick one or more)' : '(optional)'}
            </legend>
            {assignedCases.length ? (
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  type="button"
                  className="therapist-leave-page__link-btn"
                  onClick={selectAllCases}
                  disabled={allCasesSelected}
                >
                  Select all
                </button>
                <button
                  type="button"
                  className="therapist-leave-page__link-btn"
                  onClick={clearAllCases}
                  disabled={!form.case_ids.length}
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
              <button type="button" className="therapist-leave-page__link-btn" onClick={loadAssignedCases}>
                Retry
              </button>
            </p>
          ) : assignedCases.length ? (
            <div className="therapist-leave-page__case-list">
              {assignedCases.map((c) => (
                <label key={c.id} className="therapist-leave-page__case-option">
                  <input
                    type="checkbox"
                    checked={form.case_ids.includes(Number(c.id))}
                    onChange={() => toggleCaseId(c.id)}
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

        {hasHomecareSelection ? (
          <div className="therapist-leave-page__warn" role="alert">
            <strong>Paid leave applies to shadow clients only.</strong> Homecare and other services on this request
            will be recorded as therapist absence — sessions are treated like a cancellation, not paid leave.
          </div>
        ) : null}

        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
          Leave category
          <select
            value={form.billing_category}
            onChange={(e) => setForm({ ...form, billing_category: e.target.value })}
            disabled={!hasShadowSelection && hasHomecareSelection}
            style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem', minHeight: 44 }}
          >
            {categoryOptions.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </label>

        {hasShadowSelection && form.billing_category === 'PAID' ? (
          <p style={{ margin: 0, fontSize: '0.8rem', color: '#64748b' }}>
            Monthly leave uses your paid shadow balance (max 1 paid day per request; extra days go to carry forward).
          </p>
        ) : null}

        {hasShadowSelection && form.billing_category === 'UNPAID' ? (
          <p style={{ margin: 0, fontSize: '0.8rem', color: '#64748b' }}>
            Unpaid leave is reflected in your payout calculation and may affect client billing (prepaid clients are
            adjusted in the next billing cycle after admin approval).
          </p>
        ) : null}

        {hasShadowSelection && form.billing_category === 'CARRY_FORWARD' ? (
          <p style={{ margin: 0, fontSize: '0.8rem', color: '#64748b' }}>
            Carry forward applies to shadow support paid leave policy only.
          </p>
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
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
            From date
            <input
              type="date"
              value={form.start_date}
              onChange={(e) => {
                const start = e.target.value
                const end = form.end_date && form.end_date >= start ? form.end_date : start
                setForm({ ...form, start_date: start, end_date: end })
              }}
              required
              style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem', minHeight: 44 }}
            />
          </label>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
            To date
            <input
              type="date"
              value={form.end_date}
              min={form.start_date || undefined}
              onChange={(e) => setForm({ ...form, end_date: e.target.value })}
              required
              style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem', minHeight: 44 }}
            />
          </label>
        </div>

        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
          Reason (optional)
          <textarea
            value={form.reason}
            onChange={(e) => setForm({ ...form, reason: e.target.value })}
            rows={3}
            style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem', resize: 'vertical' }}
          />
        </label>

        <button
          type="submit"
          disabled={submitting || balance?.requires_employment_start_date}
          className="therapist-leave-page__request-btn"
          style={{ opacity: submitting ? 0.7 : 1 }}
        >
          {submitting ? 'Submitting…' : 'Submit request'}
        </button>
      </form>
    </div>
  ) : null

  return (
    <div className="therapist-leave-page">
      <div className="therapist-leave-page__header">
        <p style={{ fontSize: '0.75rem', fontWeight: 600, color: '#6366f1', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
          Leave management
        </p>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>My Leave</h1>
        <p style={{ fontSize: '0.875rem', color: '#6b7280', marginTop: 4 }}>
          Request leave by case and date range. HR reviews before sessions are cancelled.
        </p>
      </div>

      <div className="therapist-leave-page__stats">
        <div className="therapist-leave-page__stat-card">
          <p style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: 4 }}>Approved days ({calYear})</p>
          <p style={{ fontSize: '1.5rem', fontWeight: 700, color: '#15803d' }}>{loading ? '…' : approvedDaysYtd}</p>
        </div>
        <div className="therapist-leave-page__stat-card">
          <p style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: 4 }}>Pending</p>
          <p style={{ fontSize: '1.5rem', fontWeight: 700, color: '#a16207' }}>{loading ? '…' : pendingCount}</p>
        </div>
        <div className="therapist-leave-page__stat-card">
          <p style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: 4 }}>Rejected ({calYear})</p>
          <p style={{ fontSize: '1.5rem', fontWeight: 700, color: '#b91c1c' }}>{loading ? '…' : rejectedCount}</p>
        </div>
      </div>

      {Object.keys(daysByType).length > 0 ? (
        <p style={{ fontSize: '0.8rem', color: '#6b7280', margin: '-8px 0 16px' }}>
          By type:{' '}
          {Object.entries(daysByType)
            .map(([t, d]) => `${categoryLabel(t)} ${d}d`)
            .join(' · ')}
        </p>
      ) : null}

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <label style={{ fontSize: '0.8rem', color: '#6b7280', display: 'flex', alignItems: 'center', gap: 6 }}>
          Year
          <select
            value={calYear}
            onChange={(e) => setCalYear(Number(e.target.value))}
            style={{ padding: '6px 10px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem' }}
          >
            {[now.getFullYear() - 1, now.getFullYear(), now.getFullYear() + 1].map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </label>
      </div>

      {balance ? (
        <div className="therapist-leave-page__balance" style={{ background: '#eef2ff', border: '1px solid #c7d2fe', borderRadius: 12, padding: '14px 18px', marginBottom: 16, fontSize: '0.875rem' }}>
          <p style={{ margin: '0 0 6px', fontWeight: 700, color: '#3730a3' }}>
            Paid leave remaining ({calYear}): {leaveBalanceRemainingLabel(balance)}
            {!isLeaveBalanceUpdated(balance) ? (
              <span style={{ marginLeft: 8, fontWeight: 600, color: '#b45309' }}>To be updated</span>
            ) : null}
          </p>
          {isLeaveBalanceUpdated(balance) ? (
            <p style={{ margin: 0, color: '#4f46e5', fontSize: '0.8rem' }}>
              Used {balance.paid_used_effective} paid days
              {balance.backfill_paid_used > 0 ? ` (includes ${balance.backfill_paid_used} HR adjustment)` : ''}
              {' · '}
              Carry forward {balance.carry_forward_used_display}
            </p>
          ) : (
            <p style={{ margin: 0, color: '#64748b', fontSize: '0.8rem' }}>
              HR will confirm your opening balance for {calYear}. You can still submit leave requests.
            </p>
          )}
          {balance.requires_employment_start_date ? (
            <p style={{ margin: '8px 0 0', color: '#b45309', fontSize: '0.8rem' }}>
              Employment start date must be set in your profile and approved by admin before you can submit leave.
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="therapist-leave-page__sticky-actions">
        <button
          type="button"
          className="therapist-leave-page__request-btn"
          onClick={() => {
            const next = !showForm
            setShowForm(next)
            setError('')
            setSuccess('')
          }}
        >
          {showForm ? 'Close form' : '+ Request leave'}
        </button>
      </div>

      {leaveForm}

      <div className="therapist-leave-page__info">
        <p style={{ margin: 0, fontWeight: 600 }}>How leave affects your caseload</p>
        <p style={{ margin: '6px 0 0' }}>
          <strong>Monthly leave (paid)</strong> is adjusted only for shadow support clients after admin approval.
          For homecare and other services, approved leave marks you absent — sessions are cancelled like a no-show.
          <strong> Unpaid</strong> leave affects your payout and client billing (prepaid packages adjust in the next cycle).
        </p>
      </div>

      {loadError ? (
        <div className="therapist-leave-page__alert therapist-leave-page__alert--error">
          {loadError}
          <button type="button" onClick={loadLeaves} className="therapist-leave-page__link-btn" style={{ marginLeft: 12 }}>
            Retry
          </button>
        </div>
      ) : null}
      {error ? <div className="therapist-leave-page__alert therapist-leave-page__alert--error">{error}</div> : null}
      {success ? <div className="therapist-leave-page__alert therapist-leave-page__alert--success">{success}</div> : null}

      <div className="therapist-leave-page__requests-card">
        <div className="therapist-leave-page__requests-head">
          <p style={{ fontWeight: 600, margin: 0 }}>Leave requests</p>
          <div className="leave-filters">
            <select
              value={listMonthFilter}
              onChange={(e) => setListMonthFilter(e.target.value)}
              className="admin-input"
              style={{ minWidth: 130, padding: '6px 10px', fontSize: '0.8rem' }}
              aria-label="Filter by month"
            >
              <option value="ALL">All months</option>
              {MONTHS.map((m, idx) => (
                <option key={m} value={idx}>
                  {m}
                </option>
              ))}
            </select>
            <select
              value={listYearFilter}
              onChange={(e) => setListYearFilter(e.target.value)}
              className="admin-input"
              style={{ minWidth: 100, padding: '6px 10px', fontSize: '0.8rem' }}
              aria-label="Filter by year"
            >
              {listYearOptions.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
            <button type="button" onClick={exportLeavesExcelLikeCsv} className="therapist-leave-page__link-btn" style={{ fontWeight: 600 }}>
              Export
            </button>
            <button type="button" onClick={loadLeaves} className="therapist-leave-page__link-btn">
              Refresh
            </button>
          </div>
        </div>
        {loading ? (
          <div style={{ padding: 32, textAlign: 'center', color: '#9ca3af' }}>Loading leave requests…</div>
        ) : filteredLeaves.length === 0 ? (
          <div style={{ padding: 32, textAlign: 'center', color: '#6b7280' }}>
            <p style={{ margin: '0 0 8px' }}>No leave requests for this filter.</p>
            <button
              type="button"
              onClick={() => setShowForm(true)}
              className="therapist-leave-page__link-btn"
              style={{ fontWeight: 600 }}
            >
              Submit your first request
            </button>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="therapist-leave-page__table">
              <thead>
                <tr>
                  {['Category', 'Service', 'From', 'To', 'Days', 'Reason', 'Status', 'Note', ''].map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredLeaves.map((l) => {
                  const sc = STATUS_COLORS[l.status] || STATUS_COLORS.PENDING
                  const tc = leaveRowColor(l)
                  return (
                    <tr key={l.id}>
                      <td>
                        <span className="therapist-leave-page__pill" style={{ background: tc }}>{leaveRowLabel(l)}</span>
                      </td>
                      <td style={{ color: '#6b7280', fontSize: '0.8rem' }}>{l.service_line || '—'}</td>
                      <td>{formatDisplayDate(l.start_date)}</td>
                      <td>{formatDisplayDate(l.end_date)}</td>
                      <td>{l.day_count ?? '—'}</td>
                      <td style={{ color: '#6b7280' }}>{l.reason || '—'}</td>
                      <td>
                        <span className="therapist-leave-page__pill" style={{ background: sc.bg, color: sc.color, border: `1px solid ${sc.border}` }}>
                          {l.status}
                        </span>
                      </td>
                      <td style={{ color: '#6b7280', fontSize: '0.8rem', maxWidth: 160 }}>
                        {l.status === 'REJECTED' && l.review_note ? l.review_note : '—'}
                      </td>
                      <td>
                        {l.status === 'PENDING' ? (
                          <button type="button" onClick={() => cancelLeave(l.id)} className="therapist-leave-page__cancel-btn">
                            Cancel
                          </button>
                        ) : null}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
