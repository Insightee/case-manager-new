import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { ClinicalPrimaryButton } from '../clinical-ui/ClinicalPrimaryButton.jsx'

const DOC_TYPES = [
  'strategy_pool',
  'goal_pool',
  'clinical_protocol',
  'report_style_guide',
  'neuroaffirmative_doctrine',
  'safety_rule',
  'sample_report',
  'sample_iep',
  'other',
]

export function AdminClinicalReferencesPage() {
  const [items, setItems] = useState([])
  const [title, setTitle] = useState('')
  const [documentType, setDocumentType] = useState('strategy_pool')
  const [rawText, setRawText] = useState('')
  const [message, setMessage] = useState('')

  const load = useCallback(async () => {
    const data = await apiFetch('/api/v1/admin/clinical-references')
    setItems(data.items || [])
  }, [])

  useEffect(() => { load() }, [load])

  const save = async () => {
    setMessage('')
    try {
      await apiFetch('/api/v1/admin/clinical-references', {
        method: 'POST',
        body: JSON.stringify({ title, document_type: documentType, raw_text: rawText }),
      })
      setTitle('')
      setRawText('')
      setMessage('Reference saved as draft.')
      load()
    } catch (err) {
      setMessage(err.message || 'Could not save reference.')
    }
  }

  const chunkDoc = async (id) => {
    await apiFetch(`/api/v1/admin/clinical-references/${id}/chunk`, { method: 'POST' })
    load()
  }

  const activateDoc = async (id) => {
    await apiFetch(`/api/v1/admin/clinical-references/${id}/activate`, { method: 'POST' })
    load()
  }

  return (
    <div className="admin-page" style={{ maxWidth: 900, margin: '0 auto', padding: '1rem' }}>
      <h1>Clinical References</h1>
      <p>Add reference documents for the Insights Engine retrieval layer.</p>

      <div style={{ display: 'grid', gap: '0.75rem', marginBottom: '1.5rem' }}>
        <input placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
        <select value={documentType} onChange={(e) => setDocumentType(e.target.value)}>
          {DOC_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <textarea rows={8} placeholder="Paste reference text…" value={rawText} onChange={(e) => setRawText(e.target.value)} />
        <ClinicalPrimaryButton onClick={save}>Save as draft</ClinicalPrimaryButton>
        {message ? <p>{message}</p> : null}
      </div>

      <ul style={{ listStyle: 'none', padding: 0 }}>
        {items.map((doc) => (
          <li key={doc.id} style={{ border: '1px solid #e2e8f0', borderRadius: 12, padding: '0.75rem', marginBottom: '0.5rem' }}>
            <strong>{doc.title}</strong> — {doc.document_type} — {doc.status}
            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
              <button type="button" onClick={() => chunkDoc(doc.id)}>Chunk</button>
              <button type="button" onClick={() => activateDoc(doc.id)}>Activate</button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
