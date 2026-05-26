import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { AdminEmptyState, AdminPageHeader, AdminPanel, AdminSearchInput, AdminToolbar } from './ui/index.js'

const EMPTY_FORM = { label: '', id: '', description: '', sort_order: 0 }
const EMPTY_MODULE_ROW = { id: '', label: '' }

function slugify(str) {
  return str
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '')
}

function defaultModuleRows(label, id) {
  const slug = id || slugify(label)
  return [{ id: slug, label: label || 'Module' }]
}

export function AdminServiceCategoriesPage() {
  const [categories, setCategories] = useState([])
  const [orgCapabilities, setOrgCapabilities] = useState([])
  const [products, setProducts] = useState([])
  const [productForm, setProductForm] = useState({
    name: '',
    billing_model: 'PER_SESSION',
    price_inr: '',
    active: true,
  })
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState(EMPTY_FORM)
  const [moduleRows, setModuleRows] = useState([{ ...EMPTY_MODULE_ROW }])
  const [autoSlug, setAutoSlug] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [search, setSearch] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [editingId, setEditingId] = useState(null)

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

  useEffect(() => {
    load()
    apiFetch('/api/v1/admin/rbac/catalog')
      .then((c) => setOrgCapabilities(c.org_capabilities || []))
      .catch(() => setOrgCapabilities([]))
  }, [])

  useEffect(() => {
    if (!editingId) {
      setProducts([])
      return
    }
    apiFetch(`/api/v1/admin/service-categories/${editingId}/products`)
      .then((rows) => setProducts(Array.isArray(rows) ? rows : []))
      .catch(() => setProducts([]))
  }, [editingId])

  function handleLabelChange(e) {
    const label = e.target.value
    const nextId = autoSlug ? slugify(label) : form.id
    setForm((f) => ({ ...f, label, id: nextId }))
    if (autoSlug && !editingId) {
      setModuleRows(defaultModuleRows(label, nextId))
    }
  }

  function startEdit(cat) {
    setEditingId(cat.id)
    setForm({
      label: cat.label,
      id: cat.id,
      description: cat.description || '',
      sort_order: cat.sort_order ?? 0,
    })
    setAutoSlug(false)
    const pms = cat.product_modules?.length
      ? cat.product_modules.map((pm) => ({ id: pm.id, label: pm.label }))
      : defaultModuleRows(cat.label, cat.id)
    setModuleRows(pms)
    setSuccess('')
    setError('')
  }

  function cancelEdit() {
    setEditingId(null)
    setForm(EMPTY_FORM)
    setModuleRows([{ ...EMPTY_MODULE_ROW }])
    setAutoSlug(true)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    const product_modules = moduleRows
      .filter((r) => r.id.trim() && r.label.trim())
      .map((r) => ({ id: r.id.trim().toLowerCase(), label: r.label.trim() }))
    if (!product_modules.length) {
      setError('Add at least one product module for cases and access control.')
      setSubmitting(false)
      return
    }
    try {
      if (editingId) {
        await apiFetch(`/api/v1/admin/service-categories/${editingId}`, {
          method: 'PATCH',
          body: JSON.stringify({
            label: form.label.trim(),
            description: form.description.trim() || null,
            sort_order: Number(form.sort_order) || 0,
            product_modules,
          }),
        })
        setSuccess(`Updated "${form.label}". Assign modules to users in People → module access.`)
      } else {
        await apiFetch('/api/v1/admin/service-categories', {
          method: 'POST',
          body: JSON.stringify({
            id: form.id || null,
            label: form.label.trim(),
            description: form.description.trim() || null,
            sort_order: Number(form.sort_order) || 0,
            product_modules,
          }),
        })
        setSuccess(
          `Service "${form.label}" added. Assign the new product module(s) to staff in People → module access.`,
        )
      }
      cancelEdit()
      await load()
    } catch (err) {
      setError(err.message || 'Could not save service category')
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
      if (editingId === id) cancelEdit()
      await load()
    } catch (err) {
      setError(err.message || 'Could not remove category')
    }
  }

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return categories
    return categories.filter(
      (c) =>
        c.label.toLowerCase().includes(q) ||
        c.id.includes(q) ||
        (c.product_modules || []).some((pm) => pm.id.includes(q) || pm.label.toLowerCase().includes(q)),
    )
  }, [categories, search])

  const active = filtered.filter((c) => c.is_active)
  const inactive = filtered.filter((c) => !c.is_active)

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="Settings"
        title="Service categories"
        subtitle="Define therapy service lines and the product modules used for cases, reports, and staff access. Each service can have one or more modules (like Homecare and Shadow Support)."
      />

      {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}
      {success ? <p className="admin-alert admin-alert--success">{success}</p> : null}

      <AdminPanel
        title="Org capabilities (built-in)"
        subtitle="Billing, people admin, HR, and catalog settings are configured under People → staff access — not as clinical service lines below."
      >
        {orgCapabilities.length === 0 ? (
          <p className="admin-muted">Loading org capabilities…</p>
        ) : (
          <ul className="admin-queue" style={{ margin: 0 }}>
            {orgCapabilities.map((cap) => (
              <li key={cap.id} className="admin-queue__item">
                <div>
                  <p className="admin-queue__title">{cap.label}</p>
                  <p className="admin-queue__meta">{cap.description || cap.id}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </AdminPanel>

      <AdminPanel
        title={editingId ? `Edit: ${editingId}` : 'Add service category'}
        subtitle="Clinical service lines drive therapist services, case product_module, and service access in RBAC."
      >
        <form onSubmit={handleSubmit} className="admin-form-grid" style={{ maxWidth: 560 }}>
          <label>
            Service label
            <input
              className="admin-input"
              value={form.label}
              onChange={handleLabelChange}
              placeholder="e.g. Occupational therapy"
              required
            />
          </label>
          <label>
            Service ID / slug
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <input
                className="admin-input"
                value={form.id}
                onChange={(e) => {
                  setAutoSlug(false)
                  setForm((f) => ({ ...f, id: e.target.value }))
                }}
                placeholder="auto-generated"
                disabled={Boolean(editingId)}
              />
              {!autoSlug && !editingId ? (
                <button
                  type="button"
                  className="admin-btn admin-btn--ghost admin-btn--sm"
                  onClick={() => {
                    setAutoSlug(true)
                    const nextId = slugify(form.label)
                    setForm((f) => ({ ...f, id: nextId }))
                    setModuleRows(defaultModuleRows(form.label, nextId))
                  }}
                >
                  Auto
                </button>
              ) : null}
            </div>
            <small className="admin-muted">Parent service identifier (therapist profiles).</small>
          </label>
          <label style={{ gridColumn: '1 / -1' }}>
            Description (optional)
            <input
              className="admin-input"
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              placeholder="Short description for module admin"
            />
          </label>
          <div style={{ gridColumn: '1 / -1' }}>
            <p style={{ fontWeight: 600, fontSize: '0.85rem', margin: '0 0 8px' }}>Product modules</p>
            <p className="admin-muted" style={{ margin: '0 0 10px', fontSize: '0.8rem' }}>
              Each module is a programme line for cases and RBAC (e.g. home visits vs school site).
            </p>
            {moduleRows.map((row, idx) => (
              <div
                key={idx}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr auto',
                  gap: 8,
                  marginBottom: 8,
                  alignItems: 'end',
                }}
              >
                <label>
                  Module ID
                  <input
                    className="admin-input"
                    value={row.id}
                    onChange={(e) => {
                      const v = e.target.value
                      setModuleRows((rows) => rows.map((r, i) => (i === idx ? { ...r, id: v } : r)))
                    }}
                    placeholder="e.g. ot_home"
                    required
                  />
                </label>
                <label>
                  Module label
                  <input
                    className="admin-input"
                    value={row.label}
                    onChange={(e) => {
                      const v = e.target.value
                      setModuleRows((rows) => rows.map((r, i) => (i === idx ? { ...r, label: v } : r)))
                    }}
                    placeholder="e.g. OT — Home"
                    required
                  />
                </label>
                <button
                  type="button"
                  className="admin-btn admin-btn--ghost admin-btn--sm"
                  disabled={moduleRows.length <= 1}
                  onClick={() => setModuleRows((rows) => rows.filter((_, i) => i !== idx))}
                >
                  Remove
                </button>
              </div>
            ))}
            <button
              type="button"
              className="admin-btn admin-btn--ghost admin-btn--sm"
              onClick={() =>
                setModuleRows((rows) => [...rows, { id: '', label: '' }])
              }
            >
              + Add module
            </button>
          </div>
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
          {editingId ? (
            <div style={{ gridColumn: '1 / -1' }}>
              <p style={{ fontWeight: 600, fontSize: '0.85rem', margin: '0 0 8px' }}>Commercial products</p>
              <p className="admin-muted" style={{ margin: '0 0 10px', fontSize: '0.8rem' }}>
                Pricing rules sync to the billing ledger for allotment and invoice composer.
              </p>
              {products.length > 0 ? (
                <table className="admin-table" style={{ marginBottom: 12 }}>
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Model</th>
                      <th>Price (₹)</th>
                      <th>Active</th>
                    </tr>
                  </thead>
                  <tbody>
                    {products.map((p) => (
                      <tr key={p.id}>
                        <td>{p.name}</td>
                        <td>{p.billing_model}</td>
                        <td>{p.price_inr ?? p.total_inr ?? '—'}</td>
                        <td>{p.active ? 'Yes' : 'No'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="admin-muted" style={{ marginBottom: 12 }}>No products yet for this service.</p>
              )}
              <form
                className="admin-form-grid"
                onSubmit={async (e) => {
                  e.preventDefault()
                  setError('')
                  try {
                    await apiFetch(`/api/v1/admin/service-categories/${editingId}/products`, {
                      method: 'POST',
                      body: JSON.stringify({
                        name: productForm.name.trim(),
                        billing_model: productForm.billing_model,
                        price_inr: productForm.price_inr ? Number(productForm.price_inr) : null,
                        active: productForm.active,
                      }),
                    })
                    setProductForm({ name: '', billing_model: 'PER_SESSION', price_inr: '', active: true })
                    const rows = await apiFetch(`/api/v1/admin/service-categories/${editingId}/products`)
                    setProducts(Array.isArray(rows) ? rows : [])
                    setSuccess('Product added')
                  } catch (err) {
                    setError(err.message || 'Could not add product')
                  }
                }}
              >
                <label>
                  Product name
                  <input
                    className="admin-input"
                    value={productForm.name}
                    onChange={(e) => setProductForm((f) => ({ ...f, name: e.target.value }))}
                    required
                  />
                </label>
                <label>
                  Billing model
                  <select
                    className="admin-input"
                    value={productForm.billing_model}
                    onChange={(e) => setProductForm((f) => ({ ...f, billing_model: e.target.value }))}
                  >
                    <option value="PER_SESSION">Per session</option>
                    <option value="PACKAGE">Package</option>
                    <option value="MONTHLY">Monthly fixed</option>
                  </select>
                </label>
                <label>
                  Price (₹)
                  <input
                    type="number"
                    className="admin-input"
                    value={productForm.price_inr}
                    onChange={(e) => setProductForm((f) => ({ ...f, price_inr: e.target.value }))}
                  />
                </label>
                <div style={{ alignSelf: 'end' }}>
                  <button type="submit" className="admin-btn admin-btn--secondary admin-btn--sm">
                    Add product
                  </button>
                </div>
              </form>
            </div>
          ) : null}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button type="submit" className="admin-btn admin-btn--primary" disabled={submitting || !form.label.trim()}>
              {submitting ? 'Saving…' : editingId ? 'Save changes' : 'Add service'}
            </button>
            {editingId ? (
              <button type="button" className="admin-btn admin-btn--ghost" onClick={cancelEdit}>
                Cancel
              </button>
            ) : null}
          </div>
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
                    <th>Service</th>
                    <th>Service ID</th>
                    <th>Product modules</th>
                    <th>Sort</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {active.map((cat) => (
                    <tr key={cat.id}>
                      <td>
                        <span className="admin-table__primary">{cat.label}</span>
                      </td>
                      <td>
                        <code style={{ fontSize: '0.8rem' }}>{cat.id}</code>
                      </td>
                      <td style={{ fontSize: '0.78rem' }}>
                        {(cat.product_modules || []).map((pm) => (
                          <div key={pm.id}>
                            <code>{pm.id}</code> — {pm.label}
                          </div>
                        ))}
                      </td>
                      <td>{cat.sort_order}</td>
                      <td style={{ whiteSpace: 'nowrap' }}>
                        <button
                          type="button"
                          className="admin-btn admin-btn--ghost admin-btn--sm"
                          onClick={() => startEdit(cat)}
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          className="admin-btn admin-btn--ghost admin-btn--sm"
                          style={{ color: '#b91c1c', marginLeft: 4 }}
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
                      <td>
                        <code style={{ fontSize: '0.8rem' }}>{cat.id}</code>
                      </td>
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
