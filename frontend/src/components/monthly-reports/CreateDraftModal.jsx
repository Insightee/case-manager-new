import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { therapistClinicalReportPath } from '../../lib/clinicalReportPaths.js'
import { REPORTS_HUB_CATEGORIES } from '../../lib/reportCategories.js'
import { isReportsEngineActive } from '../../lib/reportsRevampFlags.js'
import { buildReportMonthOptions } from '../../lib/reportMonthOptions.js'
import { unwrapList } from '../../lib/listApi.js'

function buildCategoryOptions() {
  const options = [...REPORTS_HUB_CATEGORIES]
  if (isReportsEngineActive()) {
    options.push({ id: 'IEP_CLINICAL', label: 'IEP report (builder)' })
  }
  return options
}

function parseConflictDetail(err) {
  const detail = err?.detail
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    return detail
  }
  return null
}

export function CreateDraftModal({ open, onClose, onCreated, defaultMonth, defaultCaseId = null }) {
  const navigate = useNavigate()
  const reportsBase = window.location.pathname.startsWith('/therapist') ? '/therapist/reports' : '/reports'
  const monthOptions = useMemo(() => buildReportMonthOptions(), [])
  const categoryOptions = useMemo(() => buildCategoryOptions(), [])

  const [cases, setCases] = useState([])
  const [caseId, setCaseId] = useState(defaultCaseId ? String(defaultCaseId) : '')
  const [month, setMonth] = useState(defaultMonth || monthOptions[0] || '')
  const [category, setCategory] = useState('CLIENT_MONTHLY')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [conflict, setConflict] = useState(null)

  const resolvedCaseId = defaultCaseId ? String(defaultCaseId) : caseId
  const isClinicalRoute = category === 'OBSERVATION' || category === 'IEP_CLINICAL'
  const showMonthPicker = !isClinicalRoute

  useEffect(() => {
    if (!open) return
    setMonth(defaultMonth || monthOptions[0] || '')
    setCaseId(defaultCaseId ? String(defaultCaseId) : '')
    setCategory('CLIENT_MONTHLY')
    setError('')
    setConflict(null)
    apiFetch('/api/v1/cases?assigned=true&page_size=100')
      .then((data) => setCases(unwrapList(data)))
      .catch(() => setCases([]))
  }, [open, defaultMonth, defaultCaseId, monthOptions])

  if (!open) return null

  function closeAndReset() {
    setConflict(null)
    setError('')
    onClose()
  }

  function openClinicalBuilder(kind) {
    onCreated?.()
    closeAndReset()
    navigate(therapistClinicalReportPath(Number(resolvedCaseId), kind))
  }

  async function deleteConflictDraft() {
    if (!conflict?.existing_report_id) return
    setLoading(true)
    setError('')
    try {
      await apiFetch(`/api/v1/reports/monthly/${conflict.existing_report_id}`, { method: 'DELETE' })
      setConflict(null)
      await createMonthlyDraft()
    } catch (err) {
      setError(err.message || 'Could not remove the existing draft')
    } finally {
      setLoading(false)
    }
  }

  async function createMonthlyDraft() {
    const created = await apiFetch('/api/v1/reports/monthly', {
      method: 'POST',
      body: JSON.stringify({
        case_id: Number(resolvedCaseId),
        month,
        category,
      }),
    })
    onCreated?.(created)
    closeAndReset()
    navigate(`${reportsBase}/edit/${created.id}`)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!resolvedCaseId) {
      setError('Pick a client before continuing.')
      return
    }

    if (category === 'OBSERVATION') {
      openClinicalBuilder('observation')
      return
    }
    if (category === 'IEP_CLINICAL') {
      openClinicalBuilder('iep')
      return
    }

    setLoading(true)
    setError('')
    setConflict(null)
    try {
      const existing = await apiFetch(
        `/api/v1/reports/monthly/existing?case_id=${Number(resolvedCaseId)}&month=${encodeURIComponent(month)}&category=${encodeURIComponent(category)}`,
      )
      if (existing?.exists && existing.can_continue) {
        setConflict({
          message: existing.can_delete
            ? `A draft already exists for ${month}. Continue editing it, or remove it to start fresh.`
            : `A report for ${month} is already in progress. Open the existing report instead of creating another draft.`,
          existing_report_id: existing.report_id,
          existing_status: existing.status,
          can_delete: existing.can_delete,
          can_continue: existing.can_continue,
        })
        setLoading(false)
        return
      }
      await createMonthlyDraft()
    } catch (err) {
      const detail = parseConflictDetail(err)
      if (detail) {
        setConflict({
          message: detail.message || err.message,
          existing_report_id: detail.existing_report_id,
          existing_status: detail.existing_status,
          can_delete: detail.can_delete,
          can_continue: Boolean(detail.existing_report_id),
        })
      } else {
        setError(err.message || 'Could not create draft')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-[90] flex items-center justify-center bg-slate-900/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-draft-title"
    >
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
        <h2 id="create-draft-title" className="text-lg font-semibold text-slate-900">
          New report draft
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Choose a client and report type. Monthly reports use one draft per client per month.
        </p>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3">
          {defaultCaseId ? (
            <p className="text-sm text-slate-600">
              <span className="font-medium text-slate-800">Client: </span>
              {cases.find((c) => c.id === Number(defaultCaseId))?.case_code || `#${defaultCaseId}`}
              {' — '}
              {cases.find((c) => c.id === Number(defaultCaseId))?.child_name || 'Client'}
            </p>
          ) : (
            <label className="text-sm font-medium text-slate-700">
              Client
              <select
                required
                value={caseId}
                onChange={(e) => setCaseId(e.target.value)}
                className="mt-1 block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              >
                <option value="">Select client…</option>
                {cases.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.case_code} — {c.child_name}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label className="text-sm font-medium text-slate-700">
            Report type
            <select
              value={category}
              onChange={(e) => {
                setCategory(e.target.value)
                setConflict(null)
                setError('')
              }}
              className="mt-1 block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            >
              {categoryOptions.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>
          </label>
          {showMonthPicker ? (
            <label className="text-sm font-medium text-slate-700">
              Reporting month
              <select
                required
                value={month}
                onChange={(e) => {
                  setMonth(e.target.value)
                  setConflict(null)
                }}
                className="mt-1 block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              >
                {monthOptions.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <p className="text-xs text-slate-500 m-0">
              Observation and IEP builders open in their dedicated workspace — no month needed here.
            </p>
          )}
          {error ? <p className="text-sm text-red-600 m-0" role="alert">{error}</p> : null}
          {conflict ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-3 text-sm text-amber-950">
              <p className="m-0">{conflict.message}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {conflict.can_continue && conflict.existing_report_id ? (
                  <button
                    type="button"
                    className="rounded-lg bg-indigo-600 px-3 py-2 text-xs font-semibold text-white"
                    onClick={() => {
                      closeAndReset()
                      navigate(`${reportsBase}/edit/${conflict.existing_report_id}`)
                    }}
                  >
                    Continue existing
                  </button>
                ) : null}
                {conflict.can_delete ? (
                  <button
                    type="button"
                    className="rounded-lg border border-amber-300 bg-white px-3 py-2 text-xs font-semibold text-amber-900"
                    disabled={loading}
                    onClick={deleteConflictDraft}
                  >
                    Remove draft & start fresh
                  </button>
                ) : null}
                <button
                  type="button"
                  className="rounded-lg px-3 py-2 text-xs font-semibold text-amber-900 underline"
                  onClick={() => setConflict(null)}
                >
                  Go back
                </button>
              </div>
            </div>
          ) : null}
          {!conflict ? (
            <div className="flex gap-2 pt-2">
              <button
                type="button"
                onClick={closeAndReset}
                className="flex-1 rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="flex-1 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
              >
                {loading ? 'Working…' : isClinicalRoute ? 'Open builder' : 'Save draft'}
              </button>
            </div>
          ) : null}
        </form>
      </div>
    </div>
  )
}
