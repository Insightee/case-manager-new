import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { apiFetch, apiDownload } from '../../lib/apiClient.js'
import { generateReportFromLogs } from '../../lib/reportGenerateFromLogs.js'
import { categoryLabel, PROGRESS_SUB_CATEGORIES, REPORT_CATEGORIES } from '../../lib/reportCategories.js'
import { useIsMobilePortal } from '../../hooks/useMediaQuery.js'
import { ReportEditor } from './ReportEditor.jsx'
import { ReportReferenceDocsPanel } from './ReportReferenceDocsPanel.jsx'
import { ReportSaveMenu } from './ReportSaveMenu.jsx'
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
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const saveTimer = useRef(null)
  const localDraftTimer = useRef(null)
  const skipAutosaveRef = useRef(true)
  const AUTOSAVE_SERVER_MS = 120_000
  const AUTOSAVE_LOCAL_MS = 5_000
  const [serverVersionChanged, setServerVersionChanged] = useState(false)
  const [generatingFromLogs, setGeneratingFromLogs] = useState(false)
  const lastPersistedHtmlRef = useRef('')
  const bodyHtmlRef = useRef('')
  const planNextMonthRef = useRef('')
  const categoryRef = useRef('CLIENT_MONTHLY')
  const subCategoryRef = useRef('')
  const monthRef = useRef('')
  const isMobile = useIsMobilePortal()

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
          if (parsed.baseUpdatedAt && row.updated_at && parsed.baseUpdatedAt !== row.updated_at) {
            setServerVersionChanged(true)
          } else {
            setServerVersionChanged(false)
          }
        } catch {
          setLocalDraft(null)
          setServerVersionChanged(false)
        }
      } else {
        setServerVersionChanged(false)
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

  function saveLocalDraft(silent = false) {
    const payload = {
      bodyHtml: bodyHtmlRef.current,
      planNextMonth: planNextMonthRef.current,
      category: categoryRef.current,
      subCategory: subCategoryRef.current,
      month: monthRef.current,
      baseUpdatedAt: report?.updated_at || null,
      savedAt: new Date().toISOString(),
    }
    try {
      localStorage.setItem(draftKey(reportId), JSON.stringify(payload))
      setLocalDraft(payload)
      if (!silent) {
        setMessage(`Saved on this device at ${new Date().toLocaleTimeString()}.`)
        setError('')
      }
    } catch {
      const msg = 'Could not save on this device — storage may be full or blocked.'
      if (!silent) {
        setError(msg)
        setMessage('')
      }
    }
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

  bodyHtmlRef.current = bodyHtml
  planNextMonthRef.current = planNextMonth
  categoryRef.current = category
  subCategoryRef.current = subCategory
  monthRef.current = month

  const persist = useCallback(
    async (silent = true) => {
      if (!report || !editable) return
      const html = bodyHtmlRef.current
      if (silent && html === lastPersistedHtmlRef.current) return
      setSaving(true)
      setSaveFailed(false)
      if (!silent) setError('')
      try {
        const cat = categoryRef.current
        const patchUrl = isAdminEditor
          ? `/api/v1/admin/reports/monthly/${report.id}`
          : `/api/v1/reports/monthly/${report.id}`
        const updated = await apiFetch(patchUrl, {
          method: 'PATCH',
          body: JSON.stringify({
            body_html: html,
            plan_next_month: planNextMonthRef.current,
            category: cat,
            sub_category: cat === 'PROGRESS' ? subCategoryRef.current || null : null,
            month: monthRef.current,
          }),
        })
        setReport(updated)
        lastPersistedHtmlRef.current = html
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
    [report, editable, isAdminEditor],
  )

  useEffect(() => {
    if (!editable || loading || skipAutosaveRef.current) return
    setDirty(true)
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => persist(true), AUTOSAVE_SERVER_MS)
    if (localDraftTimer.current) clearTimeout(localDraftTimer.current)
    localDraftTimer.current = setTimeout(() => saveLocalDraft(true), AUTOSAVE_LOCAL_MS)
    return () => {
      if (saveTimer.current) clearTimeout(saveTimer.current)
      if (localDraftTimer.current) clearTimeout(localDraftTimer.current)
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

  async function handleGenerateFromLogs(mode = 'replace') {
    if (!report || !editable) return
    const hasContent = Boolean((bodyHtml || '').replace(/<[^>]+>/g, '').trim())
    if (hasContent && mode === 'replace') {
      const ok = window.confirm(
        'Replace the current report body with text compiled from session logs? Use Cancel to keep your draft.',
      )
      if (!ok) return
    }
    setGeneratingFromLogs(true)
    setError('')
    try {
      const updated = await generateReportFromLogs(Number(reportId), mode)
      setReport(updated)
      setBodyHtml(updated.body_html || '')
      setPlanNextMonth(updated.plan_next_month || '')
      lastPersistedHtmlRef.current = updated.body_html || ''
      setDocumentVersion((v) => v + 1)
      setDirty(false)
      setMessage('Report body generated from session logs.')
    } catch (err) {
      setError(err.message || 'Could not generate from session logs')
    } finally {
      setGeneratingFromLogs(false)
    }
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

  const detailsSummary = `${month || '—'} · ${categoryLabel(category)}`
  const submitLabel = isAdminEditor ? 'Save' : 'Submit for review'

  function SaveStatusLine({ className = '' }) {
    if (!editable) return null
    return (
      <div className={`report-save-status report-save-status--inline ${className}`.trim()} role="status">
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
    )
  }

  const metadataFields = (
    <>
      <label className="report-edit-field text-sm font-medium text-slate-700">
        Month
        <input
          className="mt-1 block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
          value={month}
          onChange={(e) => setMonth(e.target.value)}
          disabled={!editable}
        />
      </label>
      <label className="report-edit-field text-sm font-medium text-slate-700">
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
        <label className="report-edit-field text-sm font-medium text-slate-700 sm:col-span-2">
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
    </>
  )

  const pageClass = `report-edit-page mx-auto max-w-6xl space-y-4 px-2 py-4 sm:px-4${
    isMobile ? ' report-edit-page--mobile' : ''
  }`

  return (
    <div className={pageClass}>
      {isMobile ? (
        <header className="report-edit-mobile-head">
          <Link to={base} className="report-edit-mobile-head__back">
            ← Reports
          </Link>
          <div className="report-edit-mobile-head__row">
            <h1 className="report-edit-mobile-head__title">{report.child_name}</h1>
            <span className="report-edit-mobile-head__status">{report.status}</span>
          </div>
          <p className="report-edit-mobile-head__meta">
            {report.case_code} · {month || 'No month set'}
          </p>
          <SaveStatusLine className="report-edit-mobile-head__save" />
        </header>
      ) : (
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
          <ReportSaveMenu
            saving={saving}
            editable={editable}
            onSaveCloud={() => persist(false)}
            onSaveLocal={() => saveLocalDraft(false)}
            onDownloadPdf={handleDownload}
            onGenerateFromLogs={() => handleGenerateFromLogs('replace')}
            generatingFromLogs={generatingFromLogs}
            workflowLabel={submitLabel}
            onWorkflow={handleSubmit}
            variant="desktop"
          />
        </div>
      )}

      {report.reviewer_comment ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <strong>Reviewer note:</strong> {report.reviewer_comment}
        </div>
      ) : null}

      {localDraft ? (
        <div className="rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-indigo-900">
          Local draft from {localDraft.savedAt ? new Date(localDraft.savedAt).toLocaleString() : 'this device'}.
          {serverVersionChanged ? (
            <p className="mt-2 text-amber-700">
              Newer server version detected. Restoring draft will merge locally and will not overwrite server content
              silently.
            </p>
          ) : null}
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
      {!isMobile && editable ? <SaveStatusLine /> : null}

      <div
        className={
          isMobile
            ? 'report-edit-layout report-edit-layout--mobile'
            : 'grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]'
        }
      >
        <div className="report-edit-main space-y-4">
          {isMobile ? (
            <details className="report-edit-details">
              <summary className="report-edit-details__summary">
                <span className="report-edit-details__label">Report details</span>
                <span className="report-edit-details__hint">{detailsSummary}</span>
              </summary>
              <div className="report-edit-details__body grid gap-3">{metadataFields}</div>
            </details>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">{metadataFields}</div>
          )}

          <ReportEditor
            reportId={Number(reportId)}
            documentVersion={documentVersion}
            initialHtml={bodyHtml}
            planNextMonth={planNextMonth}
            onPlanChange={setPlanNextMonth}
            onHtmlChange={setBodyHtml}
            disabled={!editable}
            mobile={isMobile}
          />
        </div>

        <div className="space-y-4">
          <ReportReferenceDocsPanel caseId={report.case_id} month={month} />
          <SessionLogContextPanel
            reportId={Number(reportId)}
            caseId={report.case_id}
            month={month}
            collapsed={isMobile}
            exportVariant={isAdminEditor ? 'admin' : 'therapist'}
            onInsertIepGoals={(html) => {
              setBodyHtml((prev) => `${prev || ''}${html}`)
              setDocumentVersion((v) => v + 1)
            }}
          />
        </div>
      </div>

      {isMobile ? (
        <>
          {mobileMenuOpen ? (
            <button
              type="button"
              className="report-edit-mobile-menu-backdrop"
              aria-label="Close menu"
              onClick={() => setMobileMenuOpen(false)}
            />
          ) : null}
          <div className="report-edit-mobile-bar" role="toolbar" aria-label="Report actions">
            {editable ? (
              <>
                <ReportSaveMenu
                  variant="mobile"
                  saving={saving}
                  editable={editable}
                  onSaveCloud={() => persist(false)}
                  onSaveLocal={() => saveLocalDraft(false)}
                  workflowLabel={submitLabel}
                  onWorkflow={handleSubmit}
                />
                <button
                  type="button"
                  className="report-edit-mobile-bar__btn report-edit-mobile-bar__btn--menu"
                  aria-expanded={mobileMenuOpen}
                  aria-haspopup="menu"
                  onClick={() => setMobileMenuOpen((o) => !o)}
                >
                  ⋯
                </button>
              </>
            ) : (
              <button
                type="button"
                className="report-edit-mobile-bar__btn report-edit-mobile-bar__btn--secondary"
                onClick={handleDownload}
              >
                Download PDF
              </button>
            )}
          </div>
          {mobileMenuOpen ? (
            <div className="report-edit-mobile-menu" role="menu">
              <button
                type="button"
                role="menuitem"
                className="report-edit-mobile-menu__item"
                onClick={() => {
                  handleDownload()
                  setMobileMenuOpen(false)
                }}
              >
                Download PDF
              </button>
              {editable ? (
                <button
                  type="button"
                  role="menuitem"
                  className="report-edit-mobile-menu__item"
                  disabled={generatingFromLogs || saving}
                  onClick={() => {
                    setMobileMenuOpen(false)
                    handleGenerateFromLogs('replace')
                  }}
                >
                  {generatingFromLogs ? 'Generating…' : 'Generate from session logs'}
                </button>
              ) : null}
              <Link
                to={base}
                role="menuitem"
                className="report-edit-mobile-menu__item report-edit-mobile-menu__link"
                onClick={() => setMobileMenuOpen(false)}
              >
                Back to reports
              </Link>
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  )
}
