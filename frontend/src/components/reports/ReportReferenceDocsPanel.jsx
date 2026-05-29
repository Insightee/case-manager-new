import { useMemo, useRef, useState } from 'react'
import { useAuth } from '../../context/AuthContext.jsx'
import { apiDownload } from '../../lib/apiClient.js'
import { useCaseDocumentMutations, useCaseDocumentsList } from '../../hooks/useCaseDocuments.js'

const REF_PREFIX = 'Report reference'

function isReferenceDoc(doc) {
  const title = (doc.title || '').trim()
  return doc.category === 'OTHER' && title.startsWith(REF_PREFIX)
}

export function ReportReferenceDocsPanel({ caseId, month }) {
  const { can } = useAuth()
  const fileRef = useRef(null)
  const [uploading, setUploading] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const canCreate = can('case_document.create')

  const { data: list = [], isLoading, refetch } = useCaseDocumentsList(caseId, { category: 'OTHER' }, { enabled: !!caseId })
  const { create } = useCaseDocumentMutations(caseId)
  const refs = useMemo(() => list.filter(isReferenceDoc), [list])

  async function onFileChange(e) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file || !caseId) return
    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      setError('Reference documents must be PDF files.')
      return
    }
    if (file.size > 5 * 1024 * 1024) {
      setError('PDF must be 5 MB or smaller.')
      return
    }
    setUploading(true)
    setError('')
    setMessage('')
    try {
      const fd = new FormData()
      fd.append('category', 'OTHER')
      fd.append('title', `${REF_PREFIX}: ${file.name.replace(/\.pdf$/i, '')}`)
      fd.append('source_type', 'UPLOAD')
      if (month) fd.append('report_month', month)
      fd.append('file', file)
      await create.mutateAsync({ formData: fd })
      setMessage('Reference PDF uploaded.')
      await refetch()
    } catch (err) {
      setError(err.message || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  if (!caseId) return null

  return (
    <aside className="report-ref-docs rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-800">Reference documents</h3>
        {canCreate ? (
          <>
            <input
              ref={fileRef}
              type="file"
              accept="application/pdf,.pdf"
              className="sr-only"
              onChange={onFileChange}
            />
            <button
              type="button"
              className="admin-btn admin-btn--secondary admin-btn--sm"
              disabled={uploading}
              onClick={() => fileRef.current?.click()}
            >
              {uploading ? 'Uploading…' : 'Upload PDF'}
            </button>
          </>
        ) : null}
      </div>
      <p className="mt-1 text-xs text-slate-500">PDFs for this case, visible to staff on the case file.</p>
      {message ? <p className="mt-2 text-xs text-emerald-700">{message}</p> : null}
      {error ? <p className="mt-2 text-xs text-red-600">{error}</p> : null}
      {isLoading ? <p className="mt-2 text-xs text-slate-500">Loading…</p> : null}
      {!isLoading && refs.length === 0 ? (
        <p className="mt-2 text-xs text-slate-500">No reference PDFs yet.</p>
      ) : (
        <ul className="mt-2 space-y-2">
          {refs.map((doc) => (
            <li key={doc.id} className="flex items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs">
              <span className="min-w-0 truncate font-medium text-slate-800">{doc.title.replace(`${REF_PREFIX}: `, '')}</span>
              <button
                type="button"
                className="shrink-0 font-semibold text-indigo-600 hover:underline"
                onClick={() => apiDownload(`/api/v1/documents/${doc.id}/download`, `${doc.title}.pdf`)}
              >
                Download
              </button>
            </li>
          ))}
        </ul>
      )}
    </aside>
  )
}
