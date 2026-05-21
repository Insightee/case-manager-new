import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiFetch, apiDownload } from '../../lib/apiClient.js'
import { categoryLabel, PROGRESS_SUB_CATEGORIES, REPORT_CATEGORIES } from '../../lib/reportCategories.js'
import { ReportEditor } from './ReportEditor.jsx'
import { SessionLogContextPanel } from './SessionLogContextPanel.jsx'
import './report-editor.css'

function reportsBase(pathname) {
  if (pathname.startsWith('/therapist')) return '/therapist/reports'
  return '/reports'
}

export function ReportEditPage() {
  const { reportId } = useParams()
  const navigate = useNavigate()
  const base = reportsBase(window.location.pathname)

  const [report, setReport] = useState(null)
  const [bodyHtml, setBodyHtml] = useState('')
  const [planNextMonth, setPlanNextMonth] = useState('')
  const [category, setCategory] = useState('CLIENT_MONTHLY')
  const [subCategory, setSubCategory] = useState('')
  const [month, setMonth] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [savedAt, setSavedAt] = useState(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const saveTimer = useRef(null)

  const editable =
    report && (report.status === 'DRAFT' || report.status === 'REJECTED')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const row = await apiFetch(`/api/v1/reports/monthly/${reportId}`)
      setReport(row)
      setBodyHtml(row.body_html || '')
      setPlanNextMonth(row.plan_next_month || '')
      setCategory(row.category || 'CLIENT_MONTHLY')
      setSubCategory(row.sub_category || '')
      setMonth(row.month || '')
    } catch (err) {
      setError(err.message || 'Report not found')
      setReport(null)
    } finally {
      setLoading(false)
    }
  }, [reportId])

  useEffect(() => {
    load()
  }, [load])

  const persist = useCallback(
    async (silent = true) => {
      if (!report || !editable) return
      setSaving(true)
      if (!silent) setError('')
      try {
        const updated = await apiFetch(`/api/v1/reports/monthly/${report.id}`, {
          method: 'PATCH',
          body: JSON.stringify({
            body_html: bodyHtml,
            plan_next_month: planNextMonth,
            category,
            sub_category: category === 'PROGRESS' ? subCategory || null : null,
            month,
          }),
        })
        setReport(updated)
        setSavedAt(new Date())
        if (!silent) setMessage('Saved.')
      } catch (err) {
        setError(err.message || 'Could not save')
      } finally {
        setSaving(false)
      }
    },
    [report, editable, bodyHtml, planNextMonth, category, subCategory, month],
  )

  useEffect(() => {
    if (!editable || loading) return
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => persist(true), 2000)
    return () => {
      if (saveTimer.current) clearTimeout(saveTimer.current)
    }
  }, [bodyHtml, planNextMonth, category, subCategory, month, editable, loading, persist])

  async function handleSubmit() {
    await persist(false)
    try {
      await apiFetch(`/api/v1/reports/monthly/${reportId}/submit`, { method: 'POST' })
      setMessage('Submitted for admin review.')
      await load()
    } catch (err) {
      setError(err.message || 'Could not submit')
    }
  }

  async function handleDownload() {
    await apiDownload(`/api/v1/reports/monthly/${reportId}/download`, `report_${month || reportId}.pdf`)
  }

  if (loading) return <p className="p-6 text-slate-500">Loading report…</p>
  if (error && !report) {
    return (
      <div className="p-6">
        <p className="text-red-600">{error}</p>
        <Link to={base} className="mt-4 inline-block text-indigo-600 font-semibold">
          Back to reports
        </Link>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-6xl space-y-4 px-2 py-4 sm:px-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to={base} className="text-sm font-semibold text-indigo-600 hover:underline">
            ← Reports
          </Link>
          <h1 className="mt-2 text-xl font-bold text-slate-900">
            {report.child_name} · {report.month}
          </h1>
          <p className="text-sm text-slate-500">
            {report.case_code} · {categoryLabel(category)} · {report.status}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700"
            onClick={() => persist(false)}
            disabled={!editable || saving}
          >
            {saving ? 'Saving…' : 'Save now'}
          </button>
          <button
            type="button"
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700"
            onClick={handleDownload}
          >
            Download PDF
          </button>
          {editable ? (
            <button
              type="button"
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white"
              onClick={handleSubmit}
            >
              Submit for review
            </button>
          ) : null}
        </div>
      </div>

      {report.reviewer_comment ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <strong>Reviewer note:</strong> {report.reviewer_comment}
        </div>
      ) : null}

      {message ? <p className="text-sm text-emerald-700">{message}</p> : null}
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {savedAt && editable ? (
        <p className="text-xs text-slate-400">Autosaved {savedAt.toLocaleTimeString()}</p>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-sm font-medium text-slate-700">
              Month
              <input
                className="mt-1 block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                value={month}
                onChange={(e) => setMonth(e.target.value)}
                disabled={!editable}
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Category
              <select
                className="mt-1 block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                disabled={!editable}
              >
                {REPORT_CATEGORIES.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.label}
                  </option>
                ))}
              </select>
            </label>
            {category === 'PROGRESS' ? (
              <label className="text-sm font-medium text-slate-700 sm:col-span-2">
                Progress type
                <select
                  className="mt-1 block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  value={subCategory}
                  onChange={(e) => setSubCategory(e.target.value)}
                  disabled={!editable}
                >
                  <option value="">Select…</option>
                  {PROGRESS_SUB_CATEGORIES.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
          </div>

          <ReportEditor
            reportId={Number(reportId)}
            initialHtml={bodyHtml}
            planNextMonth={planNextMonth}
            onPlanChange={setPlanNextMonth}
            onHtmlChange={setBodyHtml}
            disabled={!editable}
          />
        </div>

        <SessionLogContextPanel
          reportId={Number(reportId)}
          caseId={report.case_id}
          month={month}
        />
      </div>
    </div>
  )
}
