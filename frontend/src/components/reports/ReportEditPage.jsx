import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { apiFetch, apiDownload } from '../../lib/apiClient.js'
import { categoryLabel, PROGRESS_SUB_CATEGORIES, REPORT_CATEGORIES } from '../../lib/reportCategories.js'
import { ReportEditor } from './ReportEditor.jsx'
import { SessionLogContextPanel } from './SessionLogContextPanel.jsx'
import './report-editor.css'

function reportsBase(pathname) {
  if (pathname.startsWith('/therapist')) return '/therapist/reports'
  return '/reports'
}

function htmlFromPlain(text) {
  if (!text || !String(text).trim()) return ''
  const escaped = String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  return escaped
    .split(/\n\n+/)
    .map((p) => `<p>${p.replace(/\n/g, '<br/>')}</p>`)
    .join('')
}

function draftKey(reportId) {
  return `report-draft-${reportId}`
}

export function ReportEditPage() {
  const { reportId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const isAdminEditor = location.pathname.startsWith('/admin')
  const adminEditMode = searchParams.get('edit') === '1'
  const base = isAdminEditor ? '/admin/reports' : reportsBase(location.pathname)

  const [report, setReport] = useState(null)
  const [bodyHtml, setBodyHtml] = useState('')
  const [planNextMonth, setPlanNextMonth] = useState('')
  const [category, setCategory] = useState('CLIENT_MONTHLY')
  const [subCategory, setSubCategory] = useState('')
  const [month, setMonth] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [savedAt, setSavedAt] = useState(null)
  const [saveFailed, setSaveFailed] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [documentVersion, setDocumentVersion] = useState(0)
  const [localDraft, setLocalDraft] = useState(null)
  const saveTimer = useRef(null)
  const skipAutosaveRef = useRef(true)

  const editable =
    report &&
    (isAdminEditor
      ? ['DRAFT', 'UNDER_REVIEW', 'REJECTED'].includes(report.status)
      : report.status === 'DRAFT' || report.status === 'REJECTED')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const row = await apiFetch(`/api/v1/reports/monthly/${reportId}`)
      if (isAdminEditor && !adminEditMode) {
        navigate(`/admin/reports/view/${reportId}`, { replace: true })
        return
      }
      setReport(row)
      const serverHtml = row.body_html || htmlFromPlain(row.summary)
      const stored = localStorage.getItem(draftKey(reportId))
      if (stored) {
        try {
          const parsed = JSON.parse(stored)
          setLocalDraft(parsed)
        } catch {
          setLocalDraft(null)
        }
      }
      setBodyHtml(serverHtml)
      setPlanNextMonth(row.plan_next_month || '')
      setCategory(row.category || 'CLIENT_MONTHLY')
      setSubCategory(row.sub_category || '')
      setMonth(row.month || '')
      setDocumentVersion((v) => v + 1)
      skipAutosaveRef.current = true
    } catch (err) {
      setError(err.message || 'Report not found')
      setReport(null)
    } finally {
      setLoading(false)
      queueMicrotask(() => {
        skipAutosaveRef.current = false
      })
    }
  }, [reportId, isAdminEditor, adminEditMode, navigate])

  useEffect(() => {
    load()
  }, [load])

  function saveLocalDraft() {
    const payload = {
      bodyHtml,
      planNextMonth,
      category,
      subCategory,
      month,
      savedAt: new Date().toISOString(),
    }
    localStorage.setItem(draftKey(reportId), JSON.stringify(payload))
    setLocalDraft(payload)
    setMessage('Draft saved on this device.')
  }

  function restoreLocalDraft() {
    if (!localDraft) return
    setBodyHtml(localDraft.bodyHtml || '')
    setPlanNextMonth(localDraft.planNextMonth || '')
    setCategory(localDraft.category || category)
    setSubCategory(localDraft.subCategory || '')
    setMonth(localDraft.month || month)
    setDocumentVersion((v) => v + 1)
    setMessage('Restored local draft.')
  }

  function clearLocalDraft() {
    localStorage.removeItem(draftKey(reportId))
    setLocalDraft(null)
  }

  const persist = useCallback(
    async (silent = true) => {
      if (!report || !editable) return
      setSaving(true)
      setSaveFailed(false)
      if (!silent) setError('')
      try {
        const patchUrl = isAdminEditor
          ? `/api/v1/admin/reports/monthly/${report.id}`
          : `/api/v1/reports/monthly/${report.id}`
        const updated = await apiFetch(patchUrl, {
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
        setDirty(false)
        clearLocalDraft()
        if (!silent) setMessage('Saved to server.')
      } catch (err) {
        setSaveFailed(true)
        setError(err.message || 'Could not save')
      } finally {
        setSaving(false)
      }
    },
    [report, editable, bodyHtml, planNextMonth, category, subCategory, month, isAdminEditor],
  )

  useEffect(() => {
    if (!editable || loading || skipAutosaveRef.current) return
    setDirty(true)
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => persist(true), 2000)
    return () => {
      if (saveTimer.current) clearTimeout(saveTimer.current)
    }
  }, [bodyHtml, planNextMonth, category, subCategory, month, editable, loading, persist])

  useEffect(() => {
    if (!dirty || !editable) return undefined
    const onBeforeUnload = (e) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => window.removeEventListener('beforeunload', onBeforeUnload)
  }, [dirty, editable])

  async function handleSubmit() {
    if (isAdminEditor) {
      await persist(false)
      setMessage('Saved — report remains in review until you approve for parents from report management.')
      return
    }
    setError('')
    if (!(month || '').trim()) {
      setError('Set the report month before submitting.')
      return
    }
    await persist(false)
    if (saveFailed) return
    try {
      await apiFetch(`/api/v1/reports/monthly/${reportId}/submit`, { method: 'POST' })
      setMessage('Submitted for admin review.')
      setError('')
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
            {saving ? 'Saving…' : 'Save to server'}
          </button>
          {editable ? (
            <button
              type="button"
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700"
              onClick={saveLocalDraft}
            >
              Save draft on device
            </button>
          ) : null}
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

      {localDraft ? (
        <div className="rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-indigo-900">
          Local draft from {localDraft.savedAt ? new Date(localDraft.savedAt).toLocaleString() : 'this device'}.
          <div className="mt-2 flex flex-wrap gap-2">
            <button type="button" className="text-sm font-semibold underline" onClick={restoreLocalDraft}>
              Restore draft
            </button>
            <button type="button" className="text-sm font-semibold underline" onClick={clearLocalDraft}>
              Dismiss
            </button>
          </div>
        </div>
      ) : null}
      {message ? <p className="text-sm text-emerald-700">{message}</p> : null}
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {editable ? (
        <div className="report-save-status" role="status">
          {saving ? (
            <span className="report-save-status__chip report-save-status__chip--saving">Saving…</span>
          ) : saveFailed ? (
            <>
              <span className="report-save-status__chip report-save-status__chip--error">Save failed</span>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => persist(false)}>
                Retry
              </button>
            </>
          ) : savedAt ? (
            <span className="report-save-status__chip report-save-status__chip--ok">
              Saved {savedAt.toLocaleTimeString()}
            </span>
          ) : dirty ? (
            <span className="report-save-status__chip">Unsaved changes</span>
          ) : null}
        </div>
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
            documentVersion={documentVersion}
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
          onInsertIepGoals={(html) => {
            setBodyHtml((prev) => `${prev || ''}${html}`)
            setDocumentVersion((v) => v + 1)
          }}
        />
      </div>
    </div>
  )
}
