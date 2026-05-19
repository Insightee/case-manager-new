import { useMemo, useState } from 'react'
import { AddressFormFields, addressToPayload, emptyAddress } from '../shared/AddressFormFields.jsx'

const EMPTY = {
  case_code: '',
  child_id: '',
  service_type: '',
  product_module: 'homecare',
  billing_type: 'PER_SESSION',
  client_rate_per_session_inr: '1000',
  pay_share_pct: '60',
  package_session_count: '',
  package_amount_inr: '',
  compensation_mode: 'PERCENTAGE',
  therapist_fixed_pay_inr: '',
}

function servicePayload(addr) {
  const base = addressToPayload(addr)
  return {
    service_address_line1: base.address_line1,
    service_address_line2: base.address_line2,
    service_city: base.city,
    service_state: base.state,
    service_pincode: base.pincode,
    service_landmark: base.landmark,
    service_latitude: base.latitude,
    service_longitude: base.longitude,
  }
}

export function AdminCreateCaseForm({ cases, onCreated, onCancel }) {
  const [form, setForm] = useState(EMPTY)
  const [serviceAddr, setServiceAddr] = useState(emptyAddress())
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const children = useMemo(() => {
    const map = new Map()
    for (const c of cases) {
      if (c.child_id) map.set(c.child_id, c.child_name || `Child #${c.child_id}`)
    }
    return [...map.entries()]
  }, [cases])

  function setField(key, value) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      const payload = {
        case_code: form.case_code.trim(),
        child_id: Number(form.child_id),
        service_type: form.service_type.trim(),
        product_module: form.product_module,
        billing_type: form.billing_type,
        compensation_mode: form.compensation_mode,
        pay_share_pct: Number(form.pay_share_pct),
      }
      if (form.billing_type === 'PER_SESSION') {
        payload.client_rate_per_session_inr = Number(form.client_rate_per_session_inr)
      } else {
        payload.package_session_count = Number(form.package_session_count)
        payload.package_amount_inr = Number(form.package_amount_inr)
        if (form.compensation_mode === 'FIXED_LUMP') {
          payload.therapist_fixed_pay_inr = Number(form.therapist_fixed_pay_inr)
        }
      }
      if (form.product_module === 'homecare' && serviceAddr.address_line1) {
        Object.assign(payload, servicePayload(serviceAddr))
      }
      await onCreated(payload)
      setForm(EMPTY)
      setServiceAddr(emptyAddress())
    } catch (err) {
      setError(err.message || 'Could not create case')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="admin-form-grid" style={{ marginBottom: 20, maxWidth: 520 }} onSubmit={handleSubmit}>
      <p className="admin-drawer__subtitle">New case (billing set here)</p>
      {error ? <p style={{ color: '#b91c1c', fontSize: '0.875rem', gridColumn: '1 / -1' }}>{error}</p> : null}
      <label>
        Case code
        <input required value={form.case_code} onChange={(e) => setField('case_code', e.target.value)} placeholder="IC-2026-099" />
      </label>
      <label>
        Child
        <select required value={form.child_id} onChange={(e) => setField('child_id', e.target.value)}>
          <option value="">Select child…</option>
          {children.map(([id, name]) => (
            <option key={id} value={id}>
              {name} (ID {id})
            </option>
          ))}
        </select>
      </label>
      <label>
        Service type
        <input required value={form.service_type} onChange={(e) => setField('service_type', e.target.value)} />
      </label>
      <label>
        Module
        <select value={form.product_module} onChange={(e) => setField('product_module', e.target.value)}>
          <option value="homecare">Homecare</option>
          <option value="shadow_support">Shadow support</option>
        </select>
      </label>
      <label>
        Billing type
        <select value={form.billing_type} onChange={(e) => setField('billing_type', e.target.value)}>
          <option value="PER_SESSION">Per session</option>
          <option value="PACKAGE">Package</option>
        </select>
      </label>
      {form.product_module === 'homecare' ? (
        <div style={{ gridColumn: '1 / -1' }}>
          <p className="admin-drawer__subtitle">Service address</p>
          <AddressFormFields value={serviceAddr} onChange={setServiceAddr} idPrefix="create-svc" />
        </div>
      ) : null}
      {form.billing_type === 'PER_SESSION' ? (
        <>
          <label>
            Rate / session (INR)
            <input type="number" required value={form.client_rate_per_session_inr} onChange={(e) => setField('client_rate_per_session_inr', e.target.value)} />
          </label>
          <label>
            Therapist share %
            <input type="number" min="50" max="70" required value={form.pay_share_pct} onChange={(e) => setField('pay_share_pct', e.target.value)} />
          </label>
        </>
      ) : (
        <>
          <label>
            Package sessions
            <input type="number" required value={form.package_session_count} onChange={(e) => setField('package_session_count', e.target.value)} />
          </label>
          <label>
            Package amount (INR)
            <input type="number" required value={form.package_amount_inr} onChange={(e) => setField('package_amount_inr', e.target.value)} />
          </label>
          <label>
            Compensation
            <select value={form.compensation_mode} onChange={(e) => setField('compensation_mode', e.target.value)}>
              <option value="PERCENTAGE">Percentage</option>
              <option value="FIXED_LUMP">Fixed lump</option>
            </select>
          </label>
          {form.compensation_mode === 'PERCENTAGE' ? (
            <label>
              Therapist share %
              <input type="number" min="50" max="70" value={form.pay_share_pct} onChange={(e) => setField('pay_share_pct', e.target.value)} />
            </label>
          ) : (
            <label>
              Therapist fixed pay (INR)
              <input type="number" value={form.therapist_fixed_pay_inr} onChange={(e) => setField('therapist_fixed_pay_inr', e.target.value)} />
            </label>
          )}
        </>
      )}
      <div style={{ display: 'flex', gap: 8, gridColumn: '1 / -1' }}>
        <button type="submit" className="admin-btn admin-btn--primary admin-btn--sm" disabled={saving}>
          {saving ? 'Creating…' : 'Create case'}
        </button>
        {onCancel ? (
          <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" onClick={onCancel}>
            Cancel
          </button>
        ) : null}
      </div>
    </form>
  )
}
