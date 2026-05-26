import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { useClinicalProductModules } from '../../hooks/useClinicalProductModules.js'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'
import { AdminPanel, AdminEmptyState, AdminToolbar } from './ui/index.js'

const EMPTY = {
  product_name: '',
  product_category: '',
  product_module: 'homecare',
  billing_model: 'POSTPAID_PER_SESSION',
  default_rate_inr: '',
  monthly_fee_inr: '',
  package_sessions: '',
  package_validity_days: '',
  gst_applicable: true,
  gst_rate_percent: '18',
  hsn_sac_code: '',
  payment_terms: '',
  client_no_show_billable: false,
  therapist_cancel_billable: false,
  active: true,
}

export function AdminProductRulesTab() {
  const { canWriteBilling } = useModuleWrite()
  const { options: clinicalOptions } = useClinicalProductModules()
  const moduleSelectOptions = clinicalOptions.filter((o) => o.value)
  const [rules, setRules] = useState([])
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState(EMPTY)
  const [editingId, setEditingId] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setRules(await apiFetch('/api/v1/admin/ledger-billing/product-rules?active_only=false'))
    } catch {
      setRules([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  function setField(k, v) {
    setForm((f) => ({ ...f, [k]: v }))
  }

  async function save(e) {
    e.preventDefault()
    if (!canWriteBilling) return
    setError('')
    const body = {
      ...form,
      default_rate_inr: form.default_rate_inr ? Number(form.default_rate_inr) : null,
      monthly_fee_inr: form.monthly_fee_inr ? Number(form.monthly_fee_inr) : null,
      package_sessions: form.package_sessions ? Number(form.package_sessions) : null,
      package_validity_days: form.package_validity_days ? Number(form.package_validity_days) : null,
      gst_rate_percent: form.gst_rate_percent ? Number(form.gst_rate_percent) : null,
    }
    try {
      if (editingId) {
        await apiFetch(`/api/v1/admin/ledger-billing/product-rules/${editingId}`, {
          method: 'PATCH',
          body: JSON.stringify(body),
        })
      } else {
        await apiFetch('/api/v1/admin/ledger-billing/product-rules', {
          method: 'POST',
          body: JSON.stringify(body),
        })
      }
      setForm(EMPTY)
      setEditingId(null)
      load()
    } catch (err) {
      setError(err.message || 'Save failed')
    }
  }

  function startEdit(r) {
    setEditingId(r.id)
    setForm({
      product_name: r.productName,
      product_category: r.productCategory,
      product_module: r.productModule,
      billing_model: r.billingModel,
      default_rate_inr: r.defaultRateInr ?? '',
      monthly_fee_inr: r.monthlyFeeInr ?? '',
      package_sessions: r.packageSessions ?? '',
      package_validity_days: r.packageValidityDays ?? '',
      gst_applicable: r.gstApplicable,
      gst_rate_percent: r.gstRatePercent ?? '',
      hsn_sac_code: r.hsnSacCode ?? '',
      payment_terms: r.paymentTerms ?? '',
      client_no_show_billable: r.clientNoShowBillable,
      therapist_cancel_billable: r.therapistCancelBillable,
      active: r.active,
    })
  }

  return (
    <div className="client-inv">
      <AdminToolbar>
        <p className="admin-drawer__subtitle" style={{ margin: 0 }}>
          Product billing rules drive ledger rows and draft invoices.
        </p>
      </AdminToolbar>

      {canWriteBilling ? (
        <AdminPanel title={editingId ? 'Edit rule' : 'New rule'}>
          <form className="admin-form-grid" onSubmit={save} style={{ maxWidth: 640 }}>
            <label>
              Product name
              <input className="admin-input" required value={form.product_name} onChange={(e) => setField('product_name', e.target.value)} />
            </label>
            <label>
              Category
              <input className="admin-input" required value={form.product_category} onChange={(e) => setField('product_category', e.target.value)} />
            </label>
            <label>
              Module
              <select className="admin-input" value={form.product_module} onChange={(e) => setField('product_module', e.target.value)}>
                {moduleSelectOptions.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Billing model
              <select className="admin-input" value={form.billing_model} onChange={(e) => setField('billing_model', e.target.value)}>
                <option value="POSTPAID_PER_SESSION">Postpaid per session</option>
                <option value="PREPAID_PACKAGE">Prepaid package</option>
                <option value="MONTHLY_FIXED">Monthly fixed</option>
              </select>
            </label>
            <label>
              Default rate (INR)
              <input className="admin-input" type="number" value={form.default_rate_inr} onChange={(e) => setField('default_rate_inr', e.target.value)} />
            </label>
            <label>
              Monthly fee (INR)
              <input className="admin-input" type="number" value={form.monthly_fee_inr} onChange={(e) => setField('monthly_fee_inr', e.target.value)} />
            </label>
            <label>
              GST %
              <input className="admin-input" type="number" value={form.gst_rate_percent} onChange={(e) => setField('gst_rate_percent', e.target.value)} />
            </label>
            <label>
              HSN/SAC
              <input className="admin-input" value={form.hsn_sac_code} onChange={(e) => setField('hsn_sac_code', e.target.value)} />
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input type="checkbox" checked={form.active} onChange={(e) => setField('active', e.target.checked)} />
              Active
            </label>
            {error ? <p style={{ color: '#b91c1c', gridColumn: '1 / -1' }}>{error}</p> : null}
            <div style={{ gridColumn: '1 / -1', display: 'flex', gap: 8 }}>
              <button type="submit" className="admin-btn admin-btn--primary admin-btn--sm">
                {editingId ? 'Update' : 'Create'}
              </button>
              {editingId ? (
                <button type="button" className="admin-btn admin-btn--sm" onClick={() => { setEditingId(null); setForm(EMPTY) }}>
                  Cancel
                </button>
              ) : null}
            </div>
          </form>
        </AdminPanel>
      ) : null}

      <AdminPanel title="Rules catalog">
        {loading ? (
          <p>Loading…</p>
        ) : rules.length === 0 ? (
          <AdminEmptyState title="No product rules" hint="Seed demo data or create rules above." />
        ) : (
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Module</th>
                  <th>Model</th>
                  <th>Rate / fee</th>
                  <th>GST</th>
                  <th>Status</th>
                  {canWriteBilling ? <th /> : null}
                </tr>
              </thead>
              <tbody>
                {rules.map((r) => (
                  <tr key={r.id}>
                    <td>{r.productName}</td>
                    <td>{r.productModule}</td>
                    <td>{r.billingModel}</td>
                    <td>
                      {r.defaultRateInr != null ? `₹${r.defaultRateInr}` : r.monthlyFeeInr != null ? `₹${r.monthlyFeeInr}/mo` : '—'}
                    </td>
                    <td>{r.gstApplicable ? `${r.gstRatePercent ?? 0}%` : 'No'}</td>
                    <td>{r.active ? 'Active' : 'Inactive'}</td>
                    {canWriteBilling ? (
                      <td>
                        <button type="button" className="admin-btn admin-btn--sm" onClick={() => startEdit(r)}>
                          Edit
                        </button>
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </AdminPanel>
    </div>
  )
}
