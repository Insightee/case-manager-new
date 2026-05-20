import { useEffect, useState } from 'react'
import { billingSummary } from '../invoices/invoiceUtils.js'

const EMPTY = {
  billing_type: '',
  client_billing_mode: '',
  client_rate_per_session_inr: '',
  package_session_count: '',
  package_amount_inr: '',
  compensation_mode: '',
  pay_share_pct: '',
  therapist_fixed_pay_inr: '',
  billing_notes: '',
}

export function CaseBillingForm({ caseItem, onSave, readOnly }) {
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!caseItem) return
    setForm({
      billing_type: caseItem.billing_type || '',
      client_billing_mode: caseItem.client_billing_mode || '',
      client_rate_per_session_inr: caseItem.client_rate_per_session_inr ?? '',
      package_session_count: caseItem.package_session_count ?? '',
      package_amount_inr: caseItem.package_amount_inr ?? '',
      compensation_mode: caseItem.compensation_mode || '',
      pay_share_pct: caseItem.pay_share_pct ?? '',
      therapist_fixed_pay_inr: caseItem.therapist_fixed_pay_inr ?? '',
      billing_notes: caseItem.billing_notes || '',
    })
  }, [caseItem])

  if (!caseItem) return null

  function setField(key, value) {
    setForm((f) => {
      const next = { ...f, [key]: value }
      if (key === 'billing_type') {
        next.client_billing_mode = value === 'PACKAGE' ? 'PREPAID' : 'POSTPAID'
      }
      return next
    })
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (readOnly) return
    setSaving(true)
    try {
      const payload = {
        billing_type: form.billing_type || null,
        client_billing_mode: form.client_billing_mode || null,
        client_rate_per_session_inr: form.client_rate_per_session_inr ? Number(form.client_rate_per_session_inr) : null,
        package_session_count: form.package_session_count ? Number(form.package_session_count) : null,
        package_amount_inr: form.package_amount_inr ? Number(form.package_amount_inr) : null,
        compensation_mode: form.compensation_mode || null,
        pay_share_pct: form.pay_share_pct ? Number(form.pay_share_pct) : null,
        therapist_fixed_pay_inr: form.therapist_fixed_pay_inr ? Number(form.therapist_fixed_pay_inr) : null,
        billing_notes: form.billing_notes || null,
      }
      await onSave(payload)
    } finally {
      setSaving(false)
    }
  }

  const summary = billingSummary({
    billing_type: form.billing_type,
    client_rate_per_session_inr: form.client_rate_per_session_inr,
    package_session_count: form.package_session_count,
    package_amount_inr: form.package_amount_inr,
    compensation_mode: form.compensation_mode,
    pay_share_pct: form.pay_share_pct,
    therapist_fixed_pay_inr: form.therapist_fixed_pay_inr,
  })

  if (readOnly) {
    return (
      <div className="admin-form-grid" style={{ marginBottom: 16 }}>
        <p className="admin-drawer__subtitle">Billing (set at case creation — admin only)</p>
        <p style={{ fontSize: '0.875rem', color: '#475569' }}>{summary}</p>
        {caseItem.billing_notes ? <p style={{ fontSize: '0.8rem', color: '#64748b' }}>{caseItem.billing_notes}</p> : null}
      </div>
    )
  }

  return (
    <form className="admin-form-grid" style={{ marginBottom: 16, maxWidth: 480 }} onSubmit={handleSubmit}>
      <p className="admin-drawer__subtitle">Case billing</p>
      <label>
        Client billing (family invoices)
        <select value={form.client_billing_mode} onChange={(e) => setField('client_billing_mode', e.target.value)}>
          <option value="">Select…</option>
          <option value="POSTPAID">Postpaid</option>
          <option value="PREPAID">Prepaid</option>
        </select>
      </label>
      <label>
        Billing type
        <select value={form.billing_type} onChange={(e) => setField('billing_type', e.target.value)} required>
          <option value="">Select…</option>
          <option value="PER_SESSION">Per session</option>
          <option value="PACKAGE">Package</option>
        </select>
      </label>

      {form.billing_type === 'PER_SESSION' ? (
        <>
          <label>
            Client rate per session (INR)
            <input type="number" min="0" value={form.client_rate_per_session_inr} onChange={(e) => setField('client_rate_per_session_inr', e.target.value)} />
          </label>
          <label>
            Therapist share % (50–70)
            <input type="number" min="50" max="70" value={form.pay_share_pct} onChange={(e) => setField('pay_share_pct', e.target.value)} />
          </label>
        </>
      ) : null}

      {form.billing_type === 'PACKAGE' ? (
        <>
          <label>
            Package sessions
            <input type="number" min="1" value={form.package_session_count} onChange={(e) => setField('package_session_count', e.target.value)} />
          </label>
          <label>
            Package amount (INR, client)
            <input type="number" min="0" value={form.package_amount_inr} onChange={(e) => setField('package_amount_inr', e.target.value)} />
          </label>
          <label>
            Compensation mode
            <select value={form.compensation_mode} onChange={(e) => setField('compensation_mode', e.target.value)}>
              <option value="">Select…</option>
              <option value="PERCENTAGE">Percentage of package</option>
              <option value="FIXED_LUMP">Fixed lump to therapist</option>
            </select>
          </label>
          {form.compensation_mode === 'PERCENTAGE' ? (
            <label>
              Therapist share % (50–70)
              <input type="number" min="50" max="70" value={form.pay_share_pct} onChange={(e) => setField('pay_share_pct', e.target.value)} />
            </label>
          ) : null}
          {form.compensation_mode === 'FIXED_LUMP' ? (
            <label>
              Therapist fixed pay (INR)
              <input type="number" min="0" value={form.therapist_fixed_pay_inr} onChange={(e) => setField('therapist_fixed_pay_inr', e.target.value)} />
            </label>
          ) : null}
        </>
      ) : null}

      <label>
        Billing notes
        <textarea rows={2} value={form.billing_notes} onChange={(e) => setField('billing_notes', e.target.value)} />
      </label>

      <p style={{ fontSize: '0.8rem', color: '#64748b', gridColumn: '1 / -1' }}>{summary}</p>

      <button type="submit" className="admin-btn admin-btn--primary admin-btn--sm" disabled={saving}>
        {saving ? 'Saving…' : 'Save billing'}
      </button>
    </form>
  )
}
