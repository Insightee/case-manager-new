import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { AdminEmptyState, AdminPageHeader, AdminPanel, AdminSearchInput, AdminToolbar } from './ui/index.js'

const EMPTY_FORM = { label: '', id: '', description: '', sort_order: 0 }

function slugify(str) {
  return str
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '')
}

export function AdminServiceCategoriesPage() {
  const [categories, setCategories] = useState([])
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState(EMPTY_FORM)
  const [autoSlug, setAutoSlug] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [search, setSearch] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const rows = await apiFetch('/api/v1/admin/service-categories?include_inactive=true')
      setCategories(Array.isArray(rows) ? rows : [])
    } catch (err) {
      setError(err.message || 'Could not load service categories')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  function handleLabelChange(e) {
    const label = e.target.value
    setForm((f) => ({ ...f, label, id: autoSlug ? slugify(label) : f.id }))
  }

  async function handleCreate(e) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await apiFetch('/api/v1/admin/service-categories', {
        method: 'POST',
        body: JSON.stringify({
          id: form.id || null,
          label: form.label.trim(),
          description: form.description.trim() || null,
          sort_order: Number(form.sort_order) || 0,
        }),
      })
      setForm(EMPTY_FORM)
      setAutoSlug(true)
      setSuccess(`Service category "${form.label}" added.`)
      await load()
    } catch (err) {
      setError(err.message || 'Could not create category')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleDelete(id) {
    if (!window.confirm(`Remove service category "${id}"?`)) return
    setError('')
    try {
      await apiFetch(`/api/v1/admin/service-categories/${id}`, { method: 'DELETE' })
      setSuccess(`"${id}" removed from active categories.`)
      await load()
    } catch (err) {
      setError(err.message || 'Could not remove category')
    }
  }

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return categories
    return categories.filter((c) => c.label.toLowerCase().includes(q) || c.id.includes(q))
  }, [categories, search])

  const active = filtered.filter((c) => c.is_active)
  const inactive = filtered.filter((c) => !c.is_active)

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="Settings"
        title="Service categories"
        subtitle="Manage the therapy service types available in therapist profiles and as product modules. Adding a service here also makes it available as a module for access control."
      />

      {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}
      {success ? <p className="admin-alert admin-alert--success">{success}</p> : null}

      <AdminPanel title="Add service category" subtitle="New categories are immediately available in therapist profiles and the module picker.">
        <form onSubmit={handleCreate} className="admin-form-grid" style={{ maxWidth: 500 }}>
          <label>
            Label
            <input
              className="admin-input"
              value={form.label}
              onChange={handleLabelChange}
              placeholder="e.g. Counselling"
              required
            />
          </label>
          <label>
            ID / slug
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <input
                className="admin-input"
                value={form.id}
                onChange={(e) => { setAutoSlug(false); setForm((f) => ({ ...f, id: e.target.value })) }}
                placeholder="auto-generated"
              />
              {!autoSlug ? (
                <button
                  type="button"
                  className="admin-btn admin-btn--ghost admin-btn--sm"
                  onClick={() => { setAutoSlug(true); setForm((f) => ({ ...f, id: slugify(f.label) })) }}
                >
                  Auto
                </button>
              ) : null}
            </div>
            <small className="admin-muted">Used as the module ID and in therapist profile data.</small>
          </label>
          <label>
            Description (optional)
            <input
              className="admin-input"
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              placeholder="Short description for the module card"
            />
          </label>
          <label>
            Sort order
            <input
              type="number"
              className="admin-input"
              style={{ maxWidth: 100 }}
              value={form.sort_order}
              onChange={(e) => setForm((f) => ({ ...f, sort_order: e.target.value }))}
            />
          </label>
          <button type="submit" className="admin-btn admin-btn--primary" disabled={submitting || !form.label.trim()}>
            {submitting ? 'Adding…' : 'Add service'}
          </button>
        </form>
      </AdminPanel>

      <AdminPanel title={`Active categories (${active.length})`} padded={false}>
        <div className="admin-panel__body">
          <AdminToolbar>
            <AdminSearchInput value={search} onChange={setSearch} placeholder="Search…" />
          </AdminToolbar>
          {loading ? (
            <div className="admin-skeleton" style={{ margin: '0 18px 12px' }} />
          ) : active.length === 0 ? (
            <AdminEmptyState title="No active categories" description="Add one above." />
          ) : (
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Label</th>
                    <th>ID / slug</th>
                    <th>Description</th>
                    <th>Sort</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {active.map((cat) => (
                    <tr key={cat.id}>
                      <td><span className="admin-table__primary">{cat.label}</span></td>
                      <td><code style={{ fontSize: '0.8rem' }}>{cat.id}</code></td>
                      <td className="admin-muted" style={{ maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {cat.description || '—'}
                      </td>
                      <td>{cat.sort_order}</td>
                      <td>
                        <button
                          type="button"
                          className="admin-btn admin-btn--ghost admin-btn--sm"
                          style={{ color: '#b91c1c' }}
                          onClick={() => handleDelete(cat.id)}
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </AdminPanel>

      {inactive.length > 0 ? (
        <AdminPanel title={`Inactive / removed (${inactive.length})`} padded={false}>
          <div className="admin-panel__body">
            <div className="admin-table-wrap">
              <table className="admin-table" style={{ opacity: 0.65 }}>
                <thead>
                  <tr>
                    <th>Label</th>
                    <th>ID</th>
                  </tr>
                </thead>
                <tbody>
                  {inactive.map((cat) => (
                    <tr key={cat.id}>
                      <td>{cat.label}</td>
                      <td><code style={{ fontSize: '0.8rem' }}>{cat.id}</code></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </AdminPanel>
      ) : null}
    </div>
  )
}
